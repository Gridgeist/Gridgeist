import pytest
from unittest.mock import MagicMock, patch, ANY
import sys
import os
from contextlib import asynccontextmanager

# MOCK EXTERNAL HEAVY DEPENDENCIES BEFORE IMPORTING SERVER
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
MOCK_ID = "mem_123"

@pytest.fixture
def mock_dependencies():
    # Reset mocks completely
    mock_lancedb.reset_mock()
    mock_torch.reset_mock()
    mock_sentence_transformers.reset_mock()
    
    # Clear side effects
    mock_lancedb.connect.side_effect = None
    
    # Setup default behaviors
    mock_torch.cuda.is_available.return_value = False
    
    # Mock Sentence Transformer instance
    mock_model = MagicMock()
    mock_embedding_result = MagicMock()
    mock_embedding_result.tolist.return_value = MOCK_EMBEDDING
    mock_model.encode.return_value = mock_embedding_result
    mock_model.encode.side_effect = None
    mock_model.device.type = 'cpu'
    
    mock_sentence_transformers.SentenceTransformer.return_value = mock_model
    
    # Mock LanceDB
    mock_db = MagicMock()
    mock_table = MagicMock()
    mock_db.open_table.return_value = mock_table
    mock_db.create_table.return_value = mock_table
    mock_db.table_names.return_value = []
    mock_lancedb.connect.return_value = mock_db
    
    # Mock search result for update/fetch
    # search() -> where() -> limit() -> to_list()
    mock_search_builder = MagicMock()
    mock_where_builder = MagicMock()
    mock_limit_builder = MagicMock()
    
    mock_table.search.return_value = mock_search_builder
    mock_search_builder.where.return_value = mock_where_builder
    # If where is not called (like in basic search sometimes depending on impl), handle search().limit()
    mock_search_builder.limit.return_value = mock_limit_builder
    mock_where_builder.limit.return_value = mock_limit_builder
    
    # Default return a record
    mock_limit_builder.to_list.return_value = [{
        "id": MOCK_ID, 
        "text": MOCK_TEXT, 
        "user_id": MOCK_USER,
        "created_at": 1000.0,
        "last_modified": 1000.0
    }]
    
    return {
        "torch": mock_torch,
        "st": mock_sentence_transformers.SentenceTransformer,
        "model": mock_model,
        "lancedb": mock_lancedb,
        "db": mock_db,
        "table": mock_table,
        "limit_builder": mock_limit_builder
    }

def test_startup_cpu_new_table(mock_dependencies):
    """Test startup with CPU and creating a new table."""
    mock_dependencies["torch"].cuda.is_available.return_value = False
    mock_dependencies["db"].table_names.return_value = []
    
    with TestClient(app) as client:
        # Check if state is populated
        assert hasattr(app.state, "model")
        assert app.state.model is not None
        
        response = client.get("/")
        assert response.status_code == 200
        # The endpoint checks app.state
        assert response.json() == {"status": "online", "gpu": False, "model": True, "table": True}
        
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
        assert response.json() == {"status": "online", "gpu": True, "model": True, "table": True}
        
        mock_dependencies["db"].open_table.assert_called_with("memories")

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

def test_delete_success(mock_dependencies):
    """Test successful delete."""
    with TestClient(app) as client:
        payload = {"memory_id": MOCK_ID}
        response = client.post("/delete", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        
        mock_dependencies["table"].delete.assert_called_with(f"id = '{MOCK_ID}'")

def test_update_success(mock_dependencies):
    """Test successful update."""
    # Mock fetch existing
    mock_dependencies["limit_builder"].to_list.return_value = [{
        "id": MOCK_ID,
        "text": "Old Text",
        "user_id": MOCK_USER,
        "created_at": 12345.0,
        "timestamp": 12345.0  # Simulate old record
    }]
    
    with TestClient(app) as client:
        payload = {"memory_id": MOCK_ID, "new_text": "New Text"}
        response = client.post("/update", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        
        # Should fetch first
        mock_dependencies["table"].search.assert_called()
        
        # Should delete old
        mock_dependencies["table"].delete.assert_called_with(f"id = '{MOCK_ID}'")
        
        # Should insert new
        mock_dependencies["table"].add.assert_called_once()
        # Verify added record has correct fields
        args, _ = mock_dependencies["table"].add.call_args
        record = args[0][0]
        assert record["id"] == MOCK_ID
        assert record["text"] == "New Text"
        assert record["created_at"] == 12345.0
        assert record["last_modified"] is not None

def test_update_not_found(mock_dependencies):
    """Test update when memory not found."""
    mock_dependencies["limit_builder"].to_list.return_value = []
    
    with TestClient(app) as client:
        payload = {"memory_id": MOCK_ID, "new_text": "New Text"}
        response = client.post("/update", json=payload)
        assert response.status_code == 404

def test_fetch_by_ids_success(mock_dependencies):
    """Test successful fetch by IDs."""
    mock_dependencies["limit_builder"].to_list.return_value = [
        {"id": "1", "text": "A"},
        {"id": "2", "text": "B"}
    ]
    
    with TestClient(app) as client:
        payload = {"memory_ids": ["1", "2"]}
        response = client.post("/fetch_by_ids", json=payload)
        assert response.status_code == 200
        results = response.json()["results"]
        assert len(results) == 2
        
        # Check filter string
        # The mock setup for search chaining is a bit simple, but we can check calls if needed
        pass

def test_not_initialized():
    """Test endpoints when server not initialized."""
    # Override lifespan to do nothing
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def dummy_lifespan(app):
        # Don't set app.state.model or app.state.table
        yield

    app.router.lifespan_context = dummy_lifespan
    
    try:
        with TestClient(app) as client:
            # Ensure state is clean (TestClient creates a new app instance copy or uses the one provided?)
            # TestClient(app) uses the app provided.
            # But state might persist if not cleared?
            # Explicitly clear state if needed, but dummy_lifespan should handle it for the new context.
            # However, app.state is persistent on the app object.
            # We might need to clear it manually if previous tests set it on the same 'app' object.
            if hasattr(app.state, "model"): del app.state.model
            if hasattr(app.state, "table"): del app.state.table
            
            response = client.post("/upsert", json={"text": "t", "user_id": "u"})
            assert response.status_code == 503
            
            response = client.post("/search", json={"query": "t"})
            assert response.status_code == 503
            
            response = client.post("/delete", json={"memory_id": "1"})
            assert response.status_code == 503
    finally:
        app.router.lifespan_context = original_lifespan
