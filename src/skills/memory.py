from typing import Literal
from src.core.registry import tool
from src.memory.manager import MemoryManager


# Helper to get memory manager
def get_manager(session_id: str, user_id: str) -> MemoryManager:
    return MemoryManager(session_id, user_id)


@tool
def save_memory(
    user_id: str,
    content: str,
    session_id: str,
    memory_type: Literal["core", "episodic"] = "episodic",
    category: str = "general",
):
    """
    Save information to Long-Term Memory.

    Use this tool to persist important information. Memory is divided into two types:
    1. 'core': Vital facts about the user (e.g., name, preferences). These are ALWAYS loaded into context.
    2. 'episodic': General events or discussions. These are ONLY retrieved when you specifically search for them.

    Args:
        user_id: The ID of the user.
        content: The content to remember.
        session_id: The current session ID.
        memory_type: 'core' for permanent facts, 'episodic' for general history.
        category: A tag for organization (e.g. 'personal', 'tech', 'work').
    """
    try:
        manager = get_manager(session_id, user_id)

        meta = {
            "user_id": user_id,
            "category": category,
        }

        internal_type = "core_fact" if memory_type == "core" else "episodic"

        manager.long_term.save_memory(
            text=content,
            memory_type=internal_type,
            importance=10 if memory_type == "core" else 5,
            **meta,
        )

        return f"✅ Saved ({memory_type}): {content}"
    except Exception as e:
        return f"❌ Failed to save memory: {str(e)}"


@tool
def search_memory(
    user_id: str,
    query: str,
    session_id: str,
    memory_type: Literal["core_fact", "episodic", "general", "summary", "all"] = "all",
):
    """
    Search through Long-Term Memory for specific details.

    Args:
        user_id: The ID of the user.
        query: The semantic search query.
        session_id: The current session ID.
        memory_type: Filter by type.
    """
    try:
        manager = get_manager(session_id, user_id)
        filter_type = None if memory_type == "all" else memory_type
        results = manager.long_term.search_memories(
            query, limit=5, memory_type=filter_type
        )

        if not results:
            return "No relevant memories found in long-term storage."

        return "Found these memories:\n" + "\n".join([f"- {r}" for r in results])
    except Exception as e:
        return f"❌ Failed to search memory: {str(e)}"


@tool
def forget_recent_conversation(user_id: str, session_id: str):
    """
    Clears the Short-Term conversation window for this session.

    Args:
        user_id: The ID of the user.
        session_id: The current session ID.
    """
    try:
        manager = get_manager(session_id, user_id)
        manager.short_term.clear_history(session_id)
        return "✅ Short-term memory wiped for this channel. Starting fresh."
    except Exception as e:
        return f"❌ Failed to clear memory: {str(e)}"


@tool
def delete_memory_by_content(user_id: str, search_query: str, session_id: str):
    """
    Delete a memory from Long-Term storage.

    Args:
        user_id: The ID of the user.
        search_query: Query to find the memory to delete.
        session_id: The current session ID.
    """
    try:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        manager = get_manager(session_id, user_id)

        vector = manager.long_term._embed(search_query)

        results = manager.long_term.client.query_points(
            collection_name=manager.long_term.collection_name,
            query=vector,
            limit=1,
            query_filter=Filter(
                must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
            ),
        )

        if not results.points:
            return "❌ No matching memory found to delete."

        memory_id = results.points[0].id
        memory_text = results.points[0].payload.get("text", "")

        manager.long_term.delete_memory(memory_id)

        return f"✅ Deleted memory: {memory_text[:100]}..."
    except Exception as e:
        return f"❌ Failed to delete memory: {str(e)}"


@tool
def get_memory_status(user_id: str, session_id: str):
    """
    Get statistics about the user's memory storage.

    Args:
        user_id: The ID of the user.
        session_id: The current session ID.
    """
    try:
        manager = get_manager(session_id, user_id)

        lt_stats = manager.long_term.get_memory_stats(user_id)
        st_count = manager.short_term.get_message_count(session_id)

        status = f"""📊 Memory Status:

**Long-Term Storage:**
- Core Facts: {lt_stats["core_facts"]} (always loaded)
- Episodic Memories: {lt_stats["episodic"]} (searchable)
- General Memories: {lt_stats["general"]} (searchable)

**Short-Term Buffer:**
- Recent Messages: {st_count} (in this channel)
"""
        return status
    except Exception as e:
        return f"❌ Failed to get memory status: {str(e)}"


@tool
def browse_diary(user_id: str, session_id: str, date: str = None, query: str = None):
    """
    Browse or search the bot's 'diary' (accumulated session summaries).
    Use this to answer questions about the past, specific days, or recurring topics.

    Args:
        user_id: The ID of the user.
        session_id: The current session ID.
        date: Optional. Specific date to look up in YYYY-MM-DD format.
        query: Optional. Semantic search query to find relevant past summaries.
    """
    try:
        manager = get_manager(session_id, user_id)

        if date:
            # Exact date lookup
            results = manager.long_term.get_by_filter(
                {"user_id": user_id, "type": "summary", "date": date}, limit=10
            )
            if not results:
                return f"I don't have any diary entries for {date}."
            return f"Diary entries for {date}:\n" + "\n".join(
                [f"- {r}" for r in results]
            )

        elif query:
            # Semantic search for summaries
            results = manager.long_term.search_memories(
                query, limit=5, memory_type="summary"
            )
            if not results:
                return f"No diary entries found matching '{query}'."
            return "Relevant diary entries:\n" + "\n".join([f"- {r}" for r in results])

        else:
            # Get latest summaries
            # Note: get_by_filter doesn't guarantee order, but we can't easily sort without more Qdrant logic here
            # For now, just return a few recent ones
            results = manager.long_term.get_by_filter(
                {"user_id": user_id, "type": "summary"}, limit=5
            )
            if not results:
                return "I haven't written any diary entries yet."
            return "Here are some recent entries from my diary:\n" + "\n".join(
                [f"- {r}" for r in results]
            )

    except Exception as e:
        return f"❌ Failed to browse diary: {str(e)}"
