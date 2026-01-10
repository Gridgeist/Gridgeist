"""
Short-Term Memory Module

Manages temporary conversation history using SQLite.
This is a rolling window of the most recent ~20 messages per user.
Messages outside this window are effectively "forgotten" to reduce noise.

Messages are NOT automatically promoted to long-term storage.
The agent must explicitly use tools to save important information.
"""

import sqlite3
from typing import List, Dict


class ShortTermMemory:
    """
    Persistent short-term memory storage for recent conversation history.

    Maintains a rolling window of recent messages to provide immediate context
    without cluttering the bot's working memory with ancient history.
    """

    def __init__(self, db_path="chat_history.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Create the messages table if it doesn't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Index for faster retrieval by session
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_session_id ON messages(session_id)"
        )
        conn.commit()
        conn.close()

    def add_message(self, session_id: str, user_id: str, role: str, content: str):
        """Store a single message in short-term history."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (session_id, user_id, role, content) VALUES (?, ?, ?, ?)",
            (session_id, user_id, role, content),
        )
        conn.commit()
        conn.close()

    def get_recent_messages(
        self, session_id: str, limit: int = 20
    ) -> List[Dict[str, str]]:
        """
        Retrieve the last N messages for a session, ordered chronologically.

        Returns:
            List of dicts: [{'role': 'user', 'content': '...'}, ...]
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get the last N messages in chronological order (oldest -> newest)
        query = """
            SELECT role, content FROM (
                SELECT role, content, created_at 
                FROM messages 
                WHERE session_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            ) ORDER BY created_at ASC
        """

        cursor.execute(query, (session_id, limit))
        rows = cursor.fetchall()
        conn.close()

        return [{"role": row["role"], "content": row["content"]} for row in rows]

    def clear_history(self, session_id: str):
        """Clear all short-term memory for a session (channel or DM)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()

    def get_message_count(self, session_id: str) -> int:
        """Get the total number of messages stored for a session."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM messages WHERE session_id = ?", (session_id,)
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def trim_to_limit(self, session_id: str, limit: int = 20):
        """Physically delete old messages beyond the limit to save space."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            DELETE FROM messages 
            WHERE session_id = ? 
            AND id NOT IN (
                SELECT id FROM messages 
                WHERE session_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            )
        """,
            (session_id, session_id, limit),
        )

        conn.commit()
        conn.close()
