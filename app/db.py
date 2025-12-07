"""Database layer for persistent SQLite storage of topics."""
import json
import sqlite3
from dataclasses import asdict
from typing import Any, Dict, List, Optional
import os

from . import models

# Use a default DB path, but allow override via environment variable for testing
DB_PATH = os.getenv("STAY_CRUNCH_DB", "stay_crunch.db")

def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    """Initialize the database schema."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS topics (
                id TEXT PRIMARY KEY,
                subject_tag TEXT NOT NULL,
                data TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()

def upsert_topic(state: 'models.TopicState') -> None:
    """Insert or update a topic."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        # Serialize the dataclass to a dictionary, then to JSON
        # We need to handle set serialization manually if TopicState has sets
        # TopicState has bubble_day_set (Set[int]), which is not JSON serializable by default.
        # However, we should probably store the serializable version or handle it here.
        # Let's assume we convert sets to lists for storage.
        
        data_dict = asdict(state)
        # Convert set to list for JSON serialization
        if "bubble_day_set" in data_dict:
            data_dict["bubble_day_set"] = list(data_dict["bubble_day_set"])
        
        json_data = json.dumps(data_dict)
        
        cur.execute(
            """
            INSERT INTO topics (id, subject_tag, data)
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                subject_tag=excluded.subject_tag,
                data=excluded.data
            """,
            (state.id, state.subject_tag, json_data),
        )
        conn.commit()
    finally:
        conn.close()

def get_topic(topic_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a topic by ID (returns dictionary data)."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT data FROM topics WHERE id = ?", (topic_id,))
        row = cur.fetchone()
        if row is None:
            return None
        return json.loads(row["data"])
    finally:
        conn.close()

def get_all_topics() -> List[Dict[str, Any]]:
    """Retrieve all topics (returns list of dictionary data)."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT data FROM topics")
        rows = cur.fetchall()
        return [json.loads(row["data"]) for row in rows]
    finally:
        conn.close()

def delete_topic(topic_id: str) -> None:
    """Delete a topic by ID."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
        conn.commit()
    finally:
        conn.close()
