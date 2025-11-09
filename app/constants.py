"""Core constants for Stay Effective v5 deterministic implementation.

References: Section 1 Parameters, Section 6 Canonical Formulas, Section 11 Worked Example
from Stay_Effective_v5_Complete.md.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

TOTAL_DAYS: int = 270
REVISION_INTERVALS: List[int] = [0, 1, 3, 7, 14]
HARD_REVISION_OFFSETS: List[int] = [0, 1, 3, 7, 14]
SOFT_REVISION_OFFSETS: List[int] = [0, 1, 3, 7]
HARD_BUBBLE_OFFSETS: List[int] = [30, 45]
SOFT_BUBBLE_OFFSETS: List[int] = [14, 30]
MAX_REVISIONS_DAY: int = 10
MAX_BUBBLE_DAY: int = 10

EF_MIN: float = 1.3
ALPHA_PI: float = 0.85
GAMMA_CRS: float = 0.05
P_REF: float = 0.9
P_NEXT: float = 0.75
KAPPA: float = 1.5
SIGMOID_GAMMA: float = 3.0
SIGMOID_MU: float = 2.8

BASE_INTERVALS: List[int] = [1, 3, 7, 14, 30]

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
    "ND": 180.0,
    "NS": 50.0,
    "Tmin": 0.10,
    "RT": 1.1,
    "AS": 1.1,
    "D": 0.9,
    "Base_EF": 3.1,
    "EF": 3.1,
    "PI": 1.568,
    "CRS": 3.2405,
    "alphaM": 1.21,
    "I_eff": 19.6,
    "S": 186.1,
    "delta": 53.9,
}
