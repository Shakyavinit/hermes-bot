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

        # Incident & Self-Healing Knowledge Base
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                error_pattern TEXT NOT NULL,
                solution TEXT NOT NULL,
                context TEXT,
                success_count INTEGER DEFAULT 1,
                updated_at REAL NOT NULL
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_error_pattern ON incidents (error_pattern)"
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


def save_incident(error_pattern: str, solution: str, context: str = "") -> None:
    """Store or increment a verified incident resolution in the self-healing database."""
    pattern_clean = error_pattern.strip().lower()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, success_count FROM incidents WHERE error_pattern = ?",
            (pattern_clean,),
        )
        row = cursor.fetchone()
        if row:
            cursor.execute(
                "UPDATE incidents SET solution = ?, context = ?, success_count = success_count + 1, updated_at = ? WHERE id = ?",
                (solution, context, time.time(), row[0]),
            )
        else:
            cursor.execute(
                "INSERT INTO incidents (error_pattern, solution, context, success_count, updated_at) VALUES (?, ?, ?, 1, ?)",
                (pattern_clean, solution, context, time.time()),
            )
        conn.commit()


def get_incident_solutions(error_text: str) -> List[str]:
    """Search for proven solutions to an observed error pattern."""
    error_clean = error_text.strip().lower()
    solutions = []
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT error_pattern, solution FROM incidents ORDER BY success_count DESC")
        for pattern, solution in cursor.fetchall():
            if pattern in error_clean or any(word in error_clean for word in pattern.split() if len(word) > 4):
                solutions.append(f"• Pattern '{pattern}': {solution}")
    return solutions[:3]


def seed_known_incidents() -> None:
    """Seed foundational Linux & cloud incident solutions."""
    known = [
        ("render sleep 15m spin down", "Use external 5m keep-alive cron ping to https://hermes-bot-kqv8.onrender.com/health via cron-job.org or uptimerobot."),
        ("wayland xdotool xwayland display", "Ensure DISPLAY=:0, WAYLAND_DISPLAY=wayland-0, and dynamic /run/user/1000/.mutter-Xwaylandauth is loaded in environment."),
        ("pactl set-sink-volume default_sink", "Use pactl set-sink-volume @DEFAULT_SINK@ <percentage>% or check pamixer --set-volume."),
        ("credit_balance_exhausted 429", "Switch to Google Gemini Flash (1500 RPD) or Groq LPU (14400 RPD) or OpenRouter free models."),
        ("direct ip access is not allowed 7777", "Access through local network LAN IP (e.g. 192.168.x.x:7777) or specify correct Host header."),
    ]
    for pattern, sol in known:
        save_incident(pattern, sol, context="System Seed")


seed_known_incidents()
