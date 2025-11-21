import logging
import time
import uuid
from pathlib import Path
from typing import Dict, List
from datetime import timedelta

from fastapi import HTTPException
import modal

APP_NAME = "gridgeist-memory"
MODEL_NAME = "BAAI/bge-small-en-v1.5"
VECTOR_DIM = 384
VOLUME_PATH = Path("/data")
DB_PATH = VOLUME_PATH / "lancedb_store"
HF_CACHE_DIR = Path("/root/.cache/huggingface")

logger = logging.getLogger(__name__)

app = modal.App(APP_NAME)
volume = modal.Volume.from_name("discord-bot-memory", create_if_missing=True)

def download_model():
    from sentence_transformers import SentenceTransformer
    import os
    # Ensure we use the baked-in cache path
    os.environ["HF_HOME"] = str(HF_CACHE_DIR)
    SentenceTransformer(MODEL_NAME)

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "lancedb",
        "numpy",
        "sentence-transformers",
        "pyarrow",
        "fastapi[standard]",
    )
    .env({"HF_HOME": str(HF_CACHE_DIR)})
    .run_function(download_model)
)

with image.imports():
    import pyarrow as pa
    from sentence_transformers import SentenceTransformer

@app.cls(
    image=image, 
    volumes={str(VOLUME_PATH): volume}, 
    scaledown_window=300,
    max_containers=1, # Prevent multiple containers from corrupting the DB
    enable_memory_snapshot=True,
)
@modal.concurrent(max_inputs=10)
class MemoryBackend:
    @modal.enter(snap=True)
    def load_model_snapshot(self):
        # This runs ONCE during snapshot creation.
        # We load the heavy model into memory here.
        # The process memory (including self.model) is then saved to disk.
        # When a container starts, it restores this memory instantly.
        logger.info("Loading model for snapshot...")
        self.model = SentenceTransformer(MODEL_NAME)
        logger.info("Model loaded!")

    @modal.enter(snap=False)
    def connect_db(self):
        # This runs AFTER restore (and on every fresh container start).
        # Connections to external systems (like Volumes/LanceDB) 
        # cannot be snapshotted reliably, so we reconnect here.
        logger.info("Connecting to database...")
        
        import os
        # Force LanceDB to use the Volume for temp files to allow atomic renames
        # This fixes "Generic LocalFileSystem error: Unable to rename file"
        tmp_path = VOLUME_PATH / "tmp"
        tmp_path.mkdir(parents=True, exist_ok=True)
        os.environ["TMPDIR"] = str(tmp_path)
        
        # Lazy import to ensure it picks up the new TMPDIR env var
        import lancedb
        
        # Use read-consistency-interval=0 to ensure strong consistency for single-writer
        # And force storage_options to avoid lock file issues if possible
        self.db = lancedb.connect(
            str(DB_PATH),
            read_consistency_interval=timedelta(seconds=0)
        )

        schema = pa.schema(
            [
                pa.field("id", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), VECTOR_DIM)),
                pa.field("text", pa.string()),
                pa.field("user_id", pa.string()),
                pa.field("timestamp", pa.float64()),
            ]
        )

        self.table = self.db.create_table("memories", schema=schema, exist_ok=True)
        logger.info("Database connected!")

    @modal.fastapi_endpoint(method="POST", label="add")
    def add(self, data: Dict[str, str]) -> Dict[str, str]:
        text = data.get("text")
        user_id = data.get("user_id")

        if not text or not user_id:
            raise HTTPException(status_code=422, detail="text and user_id are required")

        vector = self.model.encode(text, normalize_embeddings=True).tolist()

        record_id = str(uuid.uuid4())
        record = {
            "id": record_id,
            "vector": vector,
            "text": text,
            "user_id": user_id,
            "timestamp": time.time(),
        }

        self.table.add([record])
        # Explicitly commit to ensure data durability on the volume
        # LanceDB usually auto-commits, but explicit commit on volume is safer
        # self.table.commit() # API might differ, usually add() handles it.
        
        # Force volume commit if needed, but lancedb writes files directly.
        # The issue "Generic LocalFileSystem error" usually means lock/rename failure.
        # Setting TMPDIR to volume path should have fixed it.
        # If it persists, it might be due to Modal Volume rename semantics.
        
        return {"status": "success", "id": record_id}

    @modal.fastapi_endpoint(method="POST", label="search")
    def search(self, data: Dict[str, str]) -> Dict[str, List[str]]:
        query = data.get("query")
        if not query:
            raise HTTPException(status_code=422, detail="query is required")

        vector = self.model.encode(query, normalize_embeddings=True).tolist()
        results = self.table.search(vector).limit(5).to_list()
        return {"results": [r["text"] for r in results]}
