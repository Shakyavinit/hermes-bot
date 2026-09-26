"""
Hermes Agent Persistent Memory Module
Manages session history, chat transcripts, and persistent facts in SQLite.
"""

import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional

from config import BASE_DIR

DB_PATH = BASE_DIR / "data" / "memory.db"


def init_db() -> None:
    """Initialize SQLite database tables."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        # Message history table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_session_id ON messages (session_id)"
        )

        # Persistent user facts & guidelines
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS facts (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        conn.commit()


init_db()


def add_message(session_id: str, role: str, content: str) -> None:
    """Save a single conversation turn into memory."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, content, time.time()),
        )
        conn.commit()


def get_history(session_id: str, limit: int = 15) -> List[Dict[str, str]]:
    """Retrieve the most recent messages for a session."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        )
        rows = cursor.fetchall()
        # Return in chronological order
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]


def clear_history(session_id: str) -> None:
    """Clear conversational history for a session."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.commit()


def save_fact(key: str, value: str) -> None:
    """Save or update a persistent fact/preference."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO facts (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, time.time()),
        )
        conn.commit()


def get_all_facts() -> Dict[str, str]:
    """Retrieve all persistent facts as a dictionary."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM facts")
        return dict(cursor.fetchall())
