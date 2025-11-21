import pytest
from unittest.mock import MagicMock, patch
import sys
import os
from contextlib import asynccontextmanager

# MOCK EXTERNAL HEAVY DEPENDENCIES BEFORE IMPORTING SERVER
# This allows running tests without installing torch/lancedb/sentence-transformers
mock_lancedb = MagicMock()
mock_torch = MagicMock()
mock_sentence_transformers = MagicMock()

sys.modules["lancedb"] = mock_lancedb
sys.modules["torch"] = mock_torch
sys.modules["sentence_transformers"] = mock_sentence_transformers

# Add parent directory to path to import server
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import app

from fastapi.testclient import TestClient

# Mock data
MOCK_EMBEDDING = [0.1] * 384
MOCK_TEXT = "test memory"
MOCK_USER = "user_123"

@pytest.fixture
def mock_dependencies():
    # Reset mocks completely
    mock_lancedb.reset_mock()
    mock_torch.reset_mock()
    mock_sentence_transformers.reset_mock()
    
    # Clear side effects from previous tests
    mock_lancedb.connect.side_effect = None
    
    # Setup default behaviors
    mock_torch.cuda.is_available.return_value = False
    
    # Mock Sentence Transformer instance
    mock_model = MagicMock()
    # encode() return value must have .tolist()
    mock_embedding_result = MagicMock()
    mock_embedding_result.tolist.return_value = MOCK_EMBEDDING
    mock_model.encode.return_value = mock_embedding_result
    mock_model.encode.side_effect = None # Ensure no side effect
    mock_model.device.type = 'cpu'
    
    # When SentenceTransformer() is called, return our mock_model
    mock_sentence_transformers.SentenceTransformer.return_value = mock_model
    
    # Mock LanceDB
    mock_db = MagicMock()
    mock_table = MagicMock()
    mock_db.open_table.return_value = mock_table
    mock_db.create_table.return_value = mock_table
    mock_db.table_names.return_value = [] # Default to no tables
    mock_lancedb.connect.return_value = mock_db
    
    # Mock search result
    mock_search_builder = MagicMock()
    mock_search_builder.limit.return_value = mock_search_builder
    mock_search_builder.to_list.return_value = [{"text": MOCK_TEXT}]
    # Ensure search doesn't have side effect
    mock_table.search.return_value = mock_search_builder
    mock_table.search.side_effect = None
    
    return {
        "torch": mock_torch,
        "st": mock_sentence_transformers.SentenceTransformer,
        "model": mock_model,
        "lancedb": mock_lancedb,
        "db": mock_db,
        "table": mock_table
    }

def test_startup_cpu_new_table(mock_dependencies):
    """Test startup with CPU and creating a new table."""
    mock_dependencies["torch"].cuda.is_available.return_value = False
    mock_dependencies["db"].table_names.return_value = []
    
    with TestClient(app) as client:
        import server
        assert server.model is not None
        
        # Check root endpoint
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"status": "online", "gpu": False}
        
        # Verify interactions
        mock_dependencies["lancedb"].connect.assert_called_once()
        mock_dependencies["db"].create_table.assert_called_once()

def test_startup_gpu_existing_table(mock_dependencies):
    """Test startup with GPU and existing table."""
    mock_dependencies["torch"].cuda.is_available.return_value = True
    mock_dependencies["model"].device.type = 'cuda'
    mock_dependencies["db"].table_names.return_value = ["memories"]
    
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"status": "online", "gpu": True}
        
        mock_dependencies["db"].open_table.assert_called_with("memories")

def test_startup_failure(mock_dependencies):
    """Test startup failure raises exception."""
    # We need to make connect fail or something inside the lifespan try block fail.
    # Note: TestClient calls lifespan startup. If it fails, it raises RuntimeError or the exception.
    # To cover the exception handler in lifespan, we need to fail inside the try block, e.g. table_names
    mock_dependencies["db"].table_names.side_effect = Exception("DB Initialization Failed")
    
    with pytest.raises(Exception) as exc:
        with TestClient(app) as client:
            pass  # pragma: no cover
    assert "DB Initialization Failed" in str(exc.value)

def test_upsert_success(mock_dependencies):
    """Test successful upsert."""
    with TestClient(app) as client:
        payload = {
            "text": MOCK_TEXT,
            "user_id": MOCK_USER,
            "metadata": {"key": "value"}
        }
        response = client.post("/upsert", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        
        mock_dependencies["table"].add.assert_called_once()

def test_upsert_not_initialized():
    """Test upsert when server globals are None."""
    import server
    # We need to ensure globals are None. 
    # Since other tests might have run and set them, we force them to None.
    # We can't easily prevent startup in TestClient unless we disable lifespan?
    # server.app = FastAPI(lifespan=None) ? No.
    # simpler: use patch on the globals.
    
    with patch.object(server, 'model', None), patch.object(server, 'table', None):
        # We construct a client that doesn't run lifespan?
        # Or we just rely on the patch overriding whatever lifespan set?
        # If lifespan runs, it sets server.model. If we patch server.model, our patch wins inside the with block?
        # But lifespan runs *inside* the TestClient __enter__.
        # If we wrap TestClient with patch, patch starts, then TestClient starts (lifespan runs and sets global), 
        # then we are inside.
        # Wait, 'server.model' is a variable in server module.
        # If lifespan sets 'server.model = ...', it overwrites the patch if patch was just on the attribute?
        # No, patch replaces the object in the namespace.
        
        # Let's try disabling the lifespan in the app for this test.
        original_lifespan = app.router.lifespan_context

        @asynccontextmanager
        async def dummy_lifespan(app):
            yield

        app.router.lifespan_context = dummy_lifespan
        
        try:
            # Also ensure globals are None (they might be set from previous tests)
            server.model = None
            server.table = None
            
            with TestClient(app) as client:
                response = client.post("/upsert", json={"text": "t", "user_id": "u"})
                assert response.status_code == 503
        finally:
            app.router.lifespan_context = original_lifespan

def test_upsert_exception(mock_dependencies):
    """Test upsert handling exceptions."""
    mock_dependencies["model"].encode.side_effect = Exception("Embedding Error")
    
    with TestClient(app) as client:
        response = client.post("/upsert", json={"text": "t", "user_id": "u"})
        assert response.status_code == 500
        assert "Embedding Error" in response.json()["detail"]

def test_search_success(mock_dependencies):
    """Test successful search."""
    with TestClient(app) as client:
        response = client.post("/search", json={"query": "test", "limit": 3})
        assert response.status_code == 200
        
        mock_dependencies["table"].search.assert_called_once()

def test_search_not_initialized():
    """Test search when server globals are None."""
    import server
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def dummy_lifespan(app):
        yield

    app.router.lifespan_context = dummy_lifespan
    
    try:
        server.model = None
        server.table = None
        with TestClient(app) as client:
            response = client.post("/search", json={"query": "test"})
            assert response.status_code == 503
    finally:
        app.router.lifespan_context = original_lifespan

def test_search_exception(mock_dependencies):
    """Test search handling exceptions."""
    mock_dependencies["table"].search.side_effect = Exception("Search Error")
    
    with TestClient(app) as client:
        response = client.post("/search", json={"query": "test"})
        assert response.status_code == 500

