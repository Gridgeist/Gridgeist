from src.config import SUMMARY_MODEL
import logging
from src.memory.long_term import LongTermMemory
from src.memory.short_term import ShortTermMemory
from src.utils.llm import GroqClient

logger = logging.getLogger("MemoryManager")


class MemoryManager:
    def __init__(self, session_id: str, user_id: str):
        self.session_id = session_id
        self.user_id = user_id
        # Short-term: Rolling window for this specific session
        self.short_term = ShortTermMemory()
        # Long-term: Persistent semantic facts for this specific user
        self.long_term = LongTermMemory()
        self.llm = GroqClient()

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
        return self.short_term.get_recent_messages(self.session_id, limit=25)

    async def add_interaction(self, user_msg: str, bot_msg: str):
        """Save interaction to the current session."""
        self.short_term.add_message(self.session_id, self.user_id, "user", user_msg)
        self.short_term.add_message(self.session_id, self.user_id, "assistant", bot_msg)

        # Trigger diary maintenance if we exceed the milestone
        count = self.short_term.get_message_count(self.session_id)
        if count > 50:
            await self.maintain_temporal_diary(reason="milestone_reached")

    async def maintain_temporal_diary(self, reason: str = "scheduled"):
        """
        Unified maintenance task that generates a Diary Entry from recent history
        and trims the short-term buffer.
        """
        messages = self.short_term.get_recent_messages(self.session_id, limit=50)
        if not messages:
            return

        # Format conversation for the LLM
        conversation_text = "\n".join(
            [f"{m['role'].upper()}: {m['content']}" for m in messages]
        )

        prompt = (
            "Write a high-quality, reflective 'Diary Entry' for this conversation session. "
            "Focus on significant key topics, user preferences, decisions made, and any "
            "important emotional context or project progress discussed. "
            "Ignore trivial greet-bot chatter. Style: Concise but observationally rich.\n\n"
            f"CONVERSATION TRACE:\n{conversation_text}"
        )

        try:
            logger.info(
                f"💾 Performing diary maintenance ({reason}) for session {self.session_id}..."
            )
            response = await self.llm.chat_completion(
                messages=[
                    {"role": "system", "content": "You are a meticulous biographer."},
                    {"role": "user", "content": prompt},
                ],
                model=SUMMARY_MODEL,
            )
            diary_entry = response.choices[0].message.content

            if diary_entry:
                self.long_term.save_memory(
                    text=diary_entry,
                    memory_type="summary",
                    importance=7,
                    session_id=self.session_id,
                    maintenance_reason=reason,
                )

                # We keep a healthy buffer of 35 messages to ensure 'current topics'
                # are preserved for the agent's immediate short-term memory.
                self.short_term.trim_to_limit(self.session_id, limit=35)
                logger.info(
                    f"📖 Diary updated & history trimmed to 35: {diary_entry[:60]}..."
                )
        except Exception as e:
            logger.error(f"❌ Failed diary maintenance: {e}")
