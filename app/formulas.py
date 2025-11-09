"""Decay-based scheduling formulas derived from Abstract.docx.

The abstract prescribes modelling each topic's recall probability as
    R_i(t) = exp(-(t - t_last,i) / S_i)
with S_i updated in the same spirit as SuperMemo's ease-factor rule. The next
review is scheduled when the probability falls to a threshold T, i.e.
    Δt = -S_i * ln(T).
Short horizons (< 60 days) compress Δt linearly and hard topics receive an
additional multiplier so they recur sooner.
"""
from __future__ import annotations

import math

from .constants import (
    FORGETTING_RATE_MAX,
    FORGETTING_RATE_MIN,
    HARD_INTERVAL_SCALE,
    MIN_INTERVAL_DAYS,
    RECALL_THRESHOLD,
    SHORT_HORIZON_DAYS,
    SOFT_INTERVAL_SCALE,
    WORKED_EXAMPLE,
)


def clip(value: float, lo: float, hi: float) -> float:
    """Clamp *value* to [lo, hi]."""

    return max(lo, min(hi, value))


def update_forgetting_rate(forgetting_rate: float, success: bool) -> float:
    """SuperMemo-style update applied to the per-topic forgetting rate."""

    q = 5 if success else 1
    delta = 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)
    updated = forgetting_rate + delta
    return clip(updated, FORGETTING_RATE_MIN, FORGETTING_RATE_MAX)


def recall_probability(elapsed_days: float, forgetting_rate: float) -> float:
    """Return R_i(t) = exp(-Δt / S_i)."""

    if forgetting_rate <= 0:
        raise ValueError("Forgetting rate must be positive")
    if elapsed_days <= 0:
        return 1.0
    return math.exp(-elapsed_days / forgetting_rate)


def interval_for_threshold(
    forgetting_rate: float,
    *,
    threshold: float = RECALL_THRESHOLD,
) -> float:
    """Solve Δt = -S_i * ln(T)."""

    if forgetting_rate <= 0:
        raise ValueError("Forgetting rate must be positive")
    if not 0 < threshold < 1:
        raise ValueError("Threshold must be between 0 and 1")
    return -forgetting_rate * math.log(threshold)


def apply_short_horizon(interval: float, remaining_days: float) -> float:
    """Compress intervals when the learner has < 60 days remaining."""

    if remaining_days <= 0:
        # Already in crunch mode, cap at quarter of the base interval.
        return max(MIN_INTERVAL_DAYS, interval * 0.25)
    if remaining_days >= SHORT_HORIZON_DAYS:
        return interval
    scale = remaining_days / SHORT_HORIZON_DAYS
    return max(MIN_INTERVAL_DAYS, interval * scale)


def apply_difficulty_focus(interval: float, difficulty: float, is_hard: bool) -> float:
    """Shorten intervals for high-difficulty topics."""

    scale = HARD_INTERVAL_SCALE if (is_hard or difficulty >= 0.7) else SOFT_INTERVAL_SCALE
    return max(MIN_INTERVAL_DAYS, interval * scale)


def compute_interval(
    forgetting_rate: float,
    *,
    remaining_days: float,
    difficulty: float,
    is_hard: bool,
    threshold: float = RECALL_THRESHOLD,
) -> float:
    """Full interval computation described in the abstract."""

    base = interval_for_threshold(forgetting_rate, threshold=threshold)
    compressed = apply_short_horizon(base, remaining_days)
    adjusted = apply_difficulty_focus(compressed, difficulty, is_hard)
    return max(MIN_INTERVAL_DAYS, adjusted)


# ---------------------------------------------------------------------------
# Inline checks using the abstract's worked values.
# ---------------------------------------------------------------------------


_EX = WORKED_EXAMPLE
_S = _EX["forgetting_rate"]
_threshold = _EX["threshold"]
_elapsed = _EX["elapsed"]
_rem = _EX["remaining_days"]
_difficulty = _EX["difficulty"]

_raw_interval = interval_for_threshold(_S, threshold=_threshold)
if not math.isclose(_raw_interval, _EX["raw_interval"], rel_tol=1e-6):
    raise AssertionError("interval_for_threshold mismatch with worked example")

_recall = recall_probability(_elapsed, _S)
if not math.isclose(_recall, _EX["recall_probability"], rel_tol=1e-6):
    raise AssertionError("recall_probability mismatch with worked example")

_compressed = apply_short_horizon(_raw_interval, _rem)
if not math.isclose(_compressed, _EX["compressed_interval"], rel_tol=1e-6):
    raise AssertionError("apply_short_horizon mismatch with worked example")

_difficulty_interval = apply_difficulty_focus(_compressed, _difficulty, True)
if not math.isclose(_difficulty_interval, _EX["difficulty_interval"], rel_tol=1e-6):
    raise AssertionError("apply_difficulty_focus mismatch with worked example")

_full_interval = compute_interval(
    _S,
    remaining_days=_rem,
    difficulty=_difficulty,
    is_hard=True,
    threshold=_threshold,
)
if not math.isclose(_full_interval, _EX["difficulty_interval"], rel_tol=1e-6):
    raise AssertionError("compute_interval mismatch with worked example")
