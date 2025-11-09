"""Core constants for the deterministic Stay API."""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

TOTAL_DAYS: int = 270
REVISION_INTERVALS: List[int] = [0, 1, 3, 7, 14]
HARD_REVISION_OFFSETS: List[int] = [0, 1, 3, 7, 14]
SOFT_REVISION_OFFSETS: List[int] = [0, 1, 3, 7]
HARD_BUBBLE_OFFSETS: List[int] = [30, 45]
SOFT_BUBBLE_OFFSETS: List[int] = [14, 30]
MAX_REVISIONS_DAY: int = 10
MAX_BUBBLE_DAY: int = 10

FORGETTING_RATE_MIN: float = 1.0
FORGETTING_RATE_MAX: float = 120.0
RECALL_THRESHOLD: float = 0.35
SHORT_HORIZON_DAYS: float = 60.0
HARD_INTERVAL_SCALE: float = 0.85
SOFT_INTERVAL_SCALE: float = 1.0
MIN_INTERVAL_DAYS: float = 1.0

TMIN_DEFAULTS: Dict[str, float] = {
    "Major": 0.10,
    "Medium": 0.06,
    "Minor": 0.03,
}

RT_INDEX_TABLE: List[Tuple[float, float, float]] = [
    (1.2, float("inf"), 1.1),
    (1.0, 1.2, 1.0),
    (0.8, 1.0, 0.9),
    (0.6, 0.8, 0.8),
    (0.0, 0.6, 0.7),
]

AS_INDEX_TABLE: List[Tuple[float, float, float]] = [
    (0.9, 1.0, 1.2),
    (0.8, 0.9, 1.1),
    (0.7, 0.8, 1.0),
    (0.6, 0.7, 0.9),
    (0.0, 0.6, 0.8),
]

DIFFICULTY_INDEX_TABLE: Dict[str, float] = {
    "easy": 1.2,
    "moderate": 0.9,
    "hard": 0.6,
}

WORKED_EXAMPLE: Dict[str, float] = {
    "forgetting_rate": 3.0,
    "threshold": RECALL_THRESHOLD,
    "elapsed": 5.0,
    "recall_probability": math.exp(-5.0 / 3.0),
    "raw_interval": -3.0 * math.log(RECALL_THRESHOLD),
    "remaining_days": 30.0,
    "difficulty": 0.8,
    "compressed_interval": (-3.0 * math.log(RECALL_THRESHOLD)) * (30.0 / SHORT_HORIZON_DAYS),
    "difficulty_interval": (
        (-3.0 * math.log(RECALL_THRESHOLD)) * (30.0 / SHORT_HORIZON_DAYS) * HARD_INTERVAL_SCALE
    ),
}
