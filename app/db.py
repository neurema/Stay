"""Database layer for persistent storage using SQLite."""
from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional, List, Any

from .models import TopicState

logger = logging.getLogger(__name__)

DB_PATH = Path("stay_effective.db")


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Provide a transactional scope around a series of operations."""
    conn = sqlite3.connect(DB_PATH)
    # Enable accessing columns by name
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Initialize the database schema."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS topics (
                id TEXT PRIMARY KEY,
                subject_tag TEXT NOT NULL,
                difficulty REAL NOT NULL,
                accuracy REAL NOT NULL,
                rt_ratio REAL NOT NULL,
                add_day INTEGER NOT NULL,
                exam_day INTEGER NOT NULL,
                bubble_id TEXT,
                is_hard BOOLEAN NOT NULL,
                base_ef REAL NOT NULL,
                ef REAL NOT NULL,
                pi REAL NOT NULL,
                crs REAL NOT NULL,
                schedule TEXT NOT NULL,         -- JSON list of ints
                bubble_days TEXT NOT NULL,      -- JSON list of ints
                template_bubble_days TEXT NOT NULL, -- JSON list of ints
                revision_count INTEGER NOT NULL,
                history TEXT NOT NULL,          -- JSON list of tuples
                nd INTEGER NOT NULL,
                ns INTEGER NOT NULL,
                tmin REAL NOT NULL
            )
            """
        )
    logger.info("Database initialized at %s", DB_PATH.absolute())


def _adapt_topic_state(state: TopicState) -> dict[str, Any]:
    """Convert TopicState to a dictionary suitable for DB insertion."""
    return {
        "id": state.id,
        "subject_tag": state.subject_tag,
        "difficulty": state.difficulty,
        "accuracy": state.accuracy,
        "rt_ratio": state.rt_ratio,
        "add_day": state.add_day,
        "exam_day": state.exam_day,
        "bubble_id": state.bubble_id,
        "is_hard": 1 if state.is_hard else 0,
        "base_ef": state.base_ef,
        "ef": state.ef,
        "pi": state.pi,
        "crs": state.crs,
        "schedule": json.dumps(state.schedule),
        "bubble_days": json.dumps(state.bubble_days),
        # Convert set to list for JSON serialization
        "template_bubble_days": json.dumps(list(state.template_bubble_days)),
        "revision_count": state.revision_count,
        "history": json.dumps(state.history),
        "nd": state.nd,
        "ns": state.ns,
        "tmin": state.tmin,
    }


def _convert_row_to_state(row: sqlite3.Row) -> TopicState:
    """Convert a DB row back to a TopicState object."""
    return TopicState(
        id=row["id"],
        subject_tag=row["subject_tag"],
        difficulty=row["difficulty"],
        accuracy=row["accuracy"],
        rt_ratio=row["rt_ratio"],
        add_day=row["add_day"],
        exam_day=row["exam_day"],
        bubble_id=row["bubble_id"],
        is_hard=bool(row["is_hard"]),
        base_ef=row["base_ef"],
        ef=row["ef"],
        pi=row["pi"],
        crs=row["crs"],
        schedule=json.loads(row["schedule"]),
        bubble_days=json.loads(row["bubble_days"]),
        bubble_day_set=set(json.loads(row["bubble_days"])),
        template_bubble_days=set(json.loads(row["template_bubble_days"])),
        revision_count=row["revision_count"],
        # History needs to be a list of tuples, json loads as list of lists
        history=[tuple(item) for item in json.loads(row["history"])],
        nd=row["nd"],
        ns=row["ns"],
        tmin=row["tmin"],
    )


def upsert_topic(state: TopicState) -> None:
    """Insert or update a topic in the database."""
    data = _adapt_topic_state(state)
    query = """
        INSERT INTO topics (
            id, subject_tag, difficulty, accuracy, rt_ratio, add_day, exam_day,
            bubble_id, is_hard, base_ef, ef, pi, crs, schedule, bubble_days,
            template_bubble_days, revision_count, history, nd, ns, tmin
        ) VALUES (
            :id, :subject_tag, :difficulty, :accuracy, :rt_ratio, :add_day, :exam_day,
            :bubble_id, :is_hard, :base_ef, :ef, :pi, :crs, :schedule, :bubble_days,
            :template_bubble_days, :revision_count, :history, :nd, :ns, :tmin
        )
        ON CONFLICT(id) DO UPDATE SET
            subject_tag=excluded.subject_tag,
            difficulty=excluded.difficulty,
            accuracy=excluded.accuracy,
            rt_ratio=excluded.rt_ratio,
            add_day=excluded.add_day,
            exam_day=excluded.exam_day,
            bubble_id=excluded.bubble_id,
            is_hard=excluded.is_hard,
            base_ef=excluded.base_ef,
            ef=excluded.ef,
            pi=excluded.pi,
            crs=excluded.crs,
            schedule=excluded.schedule,
            bubble_days=excluded.bubble_days,
            template_bubble_days=excluded.template_bubble_days,
            revision_count=excluded.revision_count,
            history=excluded.history,
            nd=excluded.nd,
            ns=excluded.ns,
            tmin=excluded.tmin
    """
    with get_connection() as conn:
        conn.execute(query, data)


def get_topic(topic_id: str) -> Optional[TopicState]:
    """Retrieve a topic by ID."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM topics WHERE id = ?", (topic_id,)).fetchone()
        if row:
            return _convert_row_to_state(row)
    return None


def get_all_topics() -> Iterator[TopicState]:
    """Retrieve all topics from the database."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM topics")
        for row in cursor:
            yield _convert_row_to_state(row)
