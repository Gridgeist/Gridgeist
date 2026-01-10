import logging
from src.memory.long_term import LongTermMemory
from src.memory.short_term import ShortTermMemory

logger = logging.getLogger("MemoryManager")


class MemoryManager:
    def __init__(self, session_id: str, user_id: str):
        self.session_id = session_id
        self.user_id = user_id
        # Short-term: Rolling window for this specific session
        self.short_term = ShortTermMemory()
        # Long-term: Persistent semantic facts for this specific user
        self.long_term = LongTermMemory()

    async def get_context(self, user_input: str = None) -> str:
        """
        Fetch context for the specific user.
        1. Core Facts (Always present)
        2. Relevant Memories (Passive RAG based on user_input)
        """
        parts = []

        # 1. CORE FACTS
        core_facts = self.long_term.get_core_facts(self.user_id, limit=15)
        if core_facts:
            parts.append("## CORE FACTS (Permanent User Data):")
            parts.extend([f"- {f}" for f in core_facts])

        # 2. RELEVANT MEMORIES (Passive RAG)
        if user_input:
            # Search long-term memory for conceptually similar items
            hits = self.long_term.search_memories(query=user_input, limit=5)

            # Simple deduplication (don't show a fact if it's already in Core Facts)
            unique_hits = [h for h in hits if h not in core_facts]

            if unique_hits:
                parts.append("\n## RELEVANT PAST MEMORIES (Contextual):")
                parts.extend([f"- {m}" for m in unique_hits])

        return "\n".join(parts)

    def get_short_term_memory(self):
        """Retrieve recent messages for THIS session."""
        return self.short_term.get_recent_messages(self.session_id, limit=20)

    async def add_interaction(self, user_msg: str, bot_msg: str):
        """Save interaction to the current session."""
        self.short_term.add_message(self.session_id, self.user_id, "user", user_msg)
        self.short_term.add_message(self.session_id, self.user_id, "assistant", bot_msg)

        # Trim history for this session
        count = self.short_term.get_message_count(self.session_id)
        if count > 50:
            self.short_term.trim_to_limit(self.session_id, limit=30)
            logger.info(f"Trimmed session {self.session_id} to 30 messages")
