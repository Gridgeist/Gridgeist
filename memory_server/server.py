import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import lancedb
import torch
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic Models
class UpsertRequest(BaseModel):
    text: str
    user_id: str
    metadata: Optional[Dict[str, Any]] = None

class SearchRequest(BaseModel):
    query: str
    limit: int = 5

class Memory(BaseModel):
    id: str
    vector: List[float]
    text: str
    user_id: str
    timestamp: float

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize the model and database
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    logger.info(f"Starting up... Selected device: {device}")
    
    # Initialize the model
    logger.info("Loading sentence-transformers/all-MiniLM-L6-v2...")
    app.state.model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', device=device)
    logger.info(f"Model loaded on {device}")
    
    # Initialize LanceDB
    logger.info("Initializing LanceDB...")
    app.state.db = lancedb.connect("../data/lancedb")
    
    # Create or open table
    table_name = "memories"
    try:
        if table_name in app.state.db.table_names():
            app.state.table = app.state.db.open_table(table_name)
            logger.info(f"Opened existing table: {table_name}")
        else:
            # Create new table with schema
            import pyarrow as pa
            schema = pa.schema([
                pa.field("id", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), 384)),
                pa.field("text", pa.string()),
                pa.field("user_id", pa.string()),
                pa.field("timestamp", pa.float64()),
            ])
            app.state.table = app.state.db.create_table(table_name, schema=schema)
            logger.info(f"Created new table: {table_name}")
            
    except Exception as e:
        logger.error(f"Failed to initialize LanceDB table: {e}")
        raise e

    logger.info("Startup complete! All systems ready.")
    yield
    
    # Shutdown
    logger.info("Shutting down...")

# Initialize FastAPI app
app = FastAPI(lifespan=lifespan)

@app.get("/")
def read_root():
    is_gpu = False
    model_ready = hasattr(app.state, "model") and app.state.model is not None
    table_ready = hasattr(app.state, "table") and app.state.table is not None
    if hasattr(app.state, "model") and app.state.model:
        is_gpu = app.state.model.device.type == 'cuda'
    return {"status": "online", "gpu": is_gpu, "model": model_ready, "table": table_ready}

@app.post("/upsert")
async def upsert_memory(req: UpsertRequest, request: Request):
    req_id = request.headers.get("X-Request-ID", "unknown")
    
    is_initialized = (hasattr(app.state, "model") and app.state.model is not None and hasattr(app.state, "table") and app.state.table is not None)
    
    if not is_initialized:
        logger.warning(f"Upsert requested but server not initialized (ReqID: {req_id})")
        raise HTTPException(status_code=503, detail="Server not fully initialized")
    
    try:
        logger.info(f"Processing upsert (ReqID: {req_id})")
        # Generate embedding
        embedding = app.state.model.encode(req.text)
        
        # Prepare record
        record = {
            "id": str(uuid.uuid4()),
            "vector": embedding.tolist(),
            "text": req.text,
            "user_id": req.user_id,
            "timestamp": time.time()
        }
        
        # Add to LanceDB
        app.state.table.add([record])
        
        return {"status": "success", "id": record["id"]}
        
    except Exception as e:
        logger.error(f"Upsert failed: {e} (ReqID: {req_id})")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search")
async def search_memories(req: SearchRequest, request: Request):
    req_id = request.headers.get("X-Request-ID", "unknown")
    
    model_ready = hasattr(app.state, "model") and app.state.model is not None
    table_ready = hasattr(app.state, "table") and app.state.table is not None
    logger.info(f"Search requested. Model ready: {model_ready}, Table ready: {table_ready} (ReqID: {req_id})")
    
    if not (model_ready and table_ready):
        logger.warning(f"Search requested but server not initialized (ReqID: {req_id})")
        raise HTTPException(status_code=503, detail="Server not fully initialized")
        
    try:
        # Generate query embedding
        query_embedding = app.state.model.encode(req.query)
        
        # Search
        results = app.state.table.search(query_embedding).limit(req.limit).to_list()
        
        return {"results": results}
        
    except Exception as e:
        logger.error(f"Search failed: {e} (ReqID: {req_id})")
        raise HTTPException(status_code=500, detail=str(e))
