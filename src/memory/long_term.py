"""
Long-Term Memory Module

Manages persistent semantic memories using Qdrant vector database.
Stores information indefinitely, organized by type and importance.

Memory Types:
- Core Facts: Permanent user details (name, preferences, etc.) - Always injected into context
- Episodic: Significant events or conversations - Retrieved via explicit search
- General: Other important information - Retrieved via explicit search

The agent must EXPLICITLY save information here using tools.
Nothing is automatically promoted from short-term memory.
"""

import logging
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

from src.config import QDRANT_API_KEY, QDRANT_COLLECTION, QDRANT_URL


# Global singleton for the model to prevent reloading
_GLOBAL_EMBEDDING_MODEL = None


def _get_embedding_model():
    """Lazy-load the embedding model as a singleton."""
    global _GLOBAL_EMBEDDING_MODEL
    if _GLOBAL_EMBEDDING_MODEL is None:
        logging.info("Loading SentenceTransformer model (Singleton)...")
        _GLOBAL_EMBEDDING_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return _GLOBAL_EMBEDDING_MODEL


class LongTermMemory:
    """
    Persistent semantic memory storage using vector embeddings.

    Designed for:
    - Storing important facts indefinitely
    - Semantic search across memories
    - Filtering by type/importance/metadata
    - Separating "always-active" core facts from "search-only" episodic memories
    """

    def __init__(self):
        self.client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        self.embedding_model = _get_embedding_model()
        self.collection_name = QDRANT_COLLECTION
        self._ensure_collection()

    def _ensure_collection(self):
        """Create the Qdrant collection if it doesn't exist."""
        collections = self.client.get_collections()
        exists = any(c.name == self.collection_name for c in collections.collections)

        if not exists:
            logging.info(f"Creating Qdrant collection: {self.collection_name}")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )

    def _embed(self, text: str):
        """Convert text to vector embedding."""
        return self.embedding_model.encode(text).tolist()

    def save_memory(
        self, text: str, memory_type: str = "general", importance: int = 5, **metadata
    ):
        """
        Save a memory to long-term storage.

        Args:
            text: The memory content to store
            memory_type: Type of memory ("core_fact", "episodic", or "general")
            importance: Importance rating 1-10 (higher = more important)
            **metadata: Additional metadata (user_id, timestamp, category, etc.)

        Memory Types:
        - "core_fact": Always retrieved and injected into system prompt
        - "episodic": Significant events, retrieved via search
        - "general": Other information, retrieved via search
        """
        vector = self._embed(text)
        point_id = str(uuid.uuid4())

        if "date" not in metadata:
            from datetime import datetime

            metadata["date"] = datetime.now().strftime("%Y-%m-%d")

        payload = {
            "text": text,
            "type": memory_type,
            "importance": importance,
        }
        payload.update(metadata)

        self.client.upsert(
            collection_name=self.collection_name,
            points=[PointStruct(id=point_id, vector=vector, payload=payload)],
        )

        logging.info(f"Saved {memory_type} memory: {text[:50]}...")

    def search_memories(self, query: str, limit: int = 5, memory_type: str = None):
        """
        Semantic search across long-term memories.

        Args:
            query: Search query
            limit: Maximum results to return
            memory_type: Optional filter by type ("core_fact", "episodic", "general")

        Returns:
            List of memory text strings, ranked by semantic relevance
        """
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        vector = self._embed(query)

        # Build filter if memory_type is specified
        query_filter = None
        if memory_type:
            query_filter = Filter(
                must=[FieldCondition(key="type", match=MatchValue(value=memory_type))]
            )

        results = self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            limit=limit,
            query_filter=query_filter,
        )

        return [hit.payload["text"] for hit in results.points]

    def get_core_facts(self, user_id: str, limit: int = 15):
        """
        Retrieve all core facts for a user.

        Core facts are permanent, high-signal memories that should ALWAYS
        be injected into the system prompt (e.g., user's name, preferences).

        Args:
            user_id: The user to retrieve facts for
            limit: Maximum number of core facts to retrieve

        Returns:
            List of core fact text strings
        """
        return self.get_by_filter(
            {"user_id": user_id, "type": "core_fact"}, limit=limit
        )

    def get_by_filter(self, filters: dict, limit: int = 100):
        """
        Retrieve memories based on exact metadata matches (no vector search).

        Useful for:
        - Getting all core facts for a user
        - Finding memories from a specific date
        - Retrieving memories with specific tags/categories

        Args:
            filters: Dict of field:value pairs to match
            limit: Maximum results to return

        Returns:
            List of memory text strings matching the filters
        """
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        conditions = []
        for key, value in filters.items():
            conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))

        # Use scroll to list points matching the filter
        results, _ = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=Filter(must=conditions),
            limit=limit,
            with_payload=True,
        )

        return [p.payload.get("text", "") for p in results]

    def delete_memory(self, memory_id: str):
        """
        Delete a specific memory by its ID.

        Note: This requires tracking/storing memory IDs when saving.
        Could be enhanced to support deletion by content or filters.
        """
        self.client.delete(
            collection_name=self.collection_name, points_selector=[memory_id]
        )
        logging.info(f"Deleted memory: {memory_id}")

    def get_memory_stats(self, user_id: str = None):
        """
        Get statistics about stored memories.

        Returns count of each memory type, optionally filtered by user.
        """
        # This is a simplified version - could be expanded
        filters = {"user_id": user_id} if user_id else {}

        stats = {
            "core_facts": len(self.get_by_filter({**filters, "type": "core_fact"})),
            "episodic": len(self.get_by_filter({**filters, "type": "episodic"})),
            "general": len(self.get_by_filter({**filters, "type": "general"})),
        }

        return stats
