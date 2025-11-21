import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import lancedb
import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables
model = None
db = None
table = None

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
    global model, db, table
    # Determine device
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    logger.info(f"Starting up... Selected device: {device}")
    
    # Initialize the model
    logger.info("Loading sentence-transformers/all-MiniLM-L6-v2...")
    model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', device=device)
    logger.info(f"Model loaded on {device}")
    
    # Initialize LanceDB
    logger.info("Initializing LanceDB...")
    db = lancedb.connect("../data/lancedb")
    
    # Create or open table
    table_name = "memories"
    try:
        if table_name in db.table_names():
            table = db.open_table(table_name)
            logger.info(f"Opened existing table: {table_name}")
        else:
            # Define schema by creating a dummy Pydantic object or using pyarrow
            # LanceDB can infer from Pydantic model schema
            # We create the table with mode="create" and schema from the Pydantic model
            # However, creating an empty table often requires a schema definition.
            # Easier way: create with data or explicit schema.
            # We'll use the Pydantic model to define schema if supported or PyArrow.
            # LanceDB python API allows creating table from pydantic model class since recent versions?
            # Or we can just check on first upsert. But "Create a table ... (if not exist)" implies initialization.
            # We'll create an empty table using PyArrow schema derived from Pydantic or just empty list with schema.
            import pyarrow as pa

            # 384 is the dimension for all-MiniLM-L6-v2
            schema = pa.schema([
                pa.field("id", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), 384)),
                pa.field("text", pa.string()),
                pa.field("user_id", pa.string()),
                pa.field("timestamp", pa.float64()),
            ])
            table = db.create_table(table_name, schema=schema)
            logger.info(f"Created new table: {table_name}")
            
    except Exception as e:
        logger.error(f"Failed to initialize LanceDB table: {e}")
        raise e

    yield
    
    logger.info("Shutting down...")

# Initialize FastAPI app
app = FastAPI(lifespan=lifespan)

@app.get("/")
def read_root():
    is_gpu = False
    if model:
        is_gpu = model.device.type == 'cuda'
    return {"status": "online", "gpu": is_gpu}

@app.post("/upsert")
async def upsert_memory(request: UpsertRequest):
    if not model or not table:
        raise HTTPException(status_code=503, detail="Server not fully initialized")
    
    try:
        # Generate embedding
        embedding = model.encode(request.text)
        
        # Prepare record
        record = {
            "id": str(uuid.uuid4()),
            "vector": embedding.tolist(),
            "text": request.text,
            "user_id": request.user_id,
            "timestamp": time.time()
        }
        
        # Add to LanceDB
        table.add([record])
        
        return {"status": "success", "id": record["id"]}
        
    except Exception as e:
        logger.error(f"Upsert failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search")
async def search_memories(request: SearchRequest):
    if not model or not table:
        raise HTTPException(status_code=503, detail="Server not fully initialized")
        
    try:
        # Generate query embedding
        query_embedding = model.encode(request.query)
        
        # Search
        results = table.search(query_embedding).limit(request.limit).to_list()
        
        return {"results": results}
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
