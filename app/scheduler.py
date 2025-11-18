"""Deterministic scheduler utilities for Stay Effective v5 topics.

References: Section 4 Base Schedule, Section 5 Bubble Revisions, Section 9 Daily
Scheduler & PendingPool in Stay_Effective_v5_Complete.md.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from enum import Enum, auto
from typing import DefaultDict, Dict, Iterable, List, Optional, Set, Tuple

from .constants import (
    HARD_BUBBLE_OFFSETS,
    HARD_REVISION_OFFSETS,
    SOFT_BUBBLE_OFFSETS,
    SOFT_REVISION_OFFSETS,
    TOTAL_DAYS,
)

# Topics receive at most five adaptive revisions after the initial learning pass.
MAX_REVIEWS_PER_TOPIC: int = 5


def build_topic_schedule(
    add_day: int,
    is_hard: bool,
    *,
    bubble_days: Optional[Iterable[int]] = None,
    revision_offsets: Optional[Iterable[int]] = None,
    max_day: Optional[int] = None,
) -> List[int]:
    """Build the initial deterministic schedule including bubble events."""

    limit = TOTAL_DAYS if max_day is None else max(0, min(TOTAL_DAYS, max_day))

    offsets = list(revision_offsets) if revision_offsets is not None else (
        HARD_REVISION_OFFSETS if is_hard else SOFT_REVISION_OFFSETS
    )
    base_days = [add_day + offset for offset in offsets if add_day + offset <= limit]

    if bubble_days is None:
        bubble_offsets = HARD_BUBBLE_OFFSETS if is_hard else SOFT_BUBBLE_OFFSETS
        resolved_bubbles = [
            add_day + offset for offset in bubble_offsets if 0 <= add_day + offset <= limit
        ]
    else:
        resolved_bubbles = [day for day in bubble_days if 0 <= day <= limit]

    schedule = sorted({*(base_days), *resolved_bubbles})
    return schedule


class DeterministicScheduler:
    """In-memory deterministic scheduler store (Section 9)."""

    def __init__(self) -> None:
        self._topics_by_day: DefaultDict[int, List[str]] = defaultdict(list)

    def register_topic(self, topic_id: str, schedule: Iterable[int]) -> None:
        """Register or update a topic schedule deterministically."""

        self._remove_topic(topic_id)
        for day in schedule:
            self._topics_by_day[day].append(topic_id)
            self._topics_by_day[day].sort()

    def _remove_topic(self, topic_id: str) -> None:
        """Remove a topic from every scheduled bucket."""

        for day, topics in list(self._topics_by_day.items()):
            if topic_id in topics:
                topics[:] = [tid for tid in topics if tid != topic_id]
            if not topics:
                del self._topics_by_day[day]

    def remove_day(self, topic_id: str, day: int) -> None:
        """Remove a scheduled revision for a topic on a given day."""

        topics = self._topics_by_day.get(day)
        if not topics:
            return
        self._topics_by_day[day] = [tid for tid in topics if tid != topic_id]
        if not self._topics_by_day[day]:
            del self._topics_by_day[day]

    def get_schedule_for_day(self, day: int) -> List[str]:
        """Return topic ids scheduled for the specified day."""

        return list(self._topics_by_day.get(day, []))

    def as_dict(self) -> Dict[int, List[str]]:
        """Expose the internal mapping for diagnostics and tests."""

        return {day: list(topics) for day, topics in self._topics_by_day.items()}


class RevisionStage(Enum):
    NEW = auto()
    SHORT_TERM = auto()
    TRANSITION = auto()
    LONG_TERM = auto()


@dataclass
class ScheduleResult:
    interval_days: Optional[int]
    stage: RevisionStage
    is_bubble: bool

    def to_dict(self) -> Dict[str, object]:
        return {
            "interval_days": self.interval_days,
            "stage": self.stage.name,
            "is_bubble": self.is_bubble,
        }


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _infer_stage(revision_count: int, days_left: int) -> RevisionStage:
    if days_left <= 5:
        return RevisionStage.SHORT_TERM

    if revision_count <= 0:
        return RevisionStage.NEW
    if revision_count in (1, 2):
        return RevisionStage.SHORT_TERM
    if revision_count == 3:
        return RevisionStage.TRANSITION
    return RevisionStage.LONG_TERM


def _is_bubble_revision(revision_count: int) -> bool:
    next_rev_no = revision_count + 1
    return 3 <= next_rev_no <= 5


def _compute_performance_multiplier(
    difficulty: float, time_taken: float, time_expected: float
) -> float:
    difficulty = _clamp(difficulty, 0.0, 1.0)

    if time_expected <= 0:
        time_ratio = 1.0
    else:
        time_ratio = time_taken / time_expected
    time_ratio = _clamp(time_ratio, 0.25, 3.0)

    strain = 0.6 * difficulty + 0.4 * max(0.0, time_ratio - 1.0)

    if strain <= 0.0:
        return 1.6
    if strain >= 2.0:
        return 0.5
    return 1.6 - 0.55 * strain


def _base_interval_for_revision(revision_count: int) -> int:
    next_rev_no = revision_count + 1
    if next_rev_no == 1:
        return 1
    if next_rev_no == 2:
        return 3
    if next_rev_no == 3:
        return 7
    if next_rev_no == 4:
        return 14
    return 21


def _respect_exam_horizon(
    proposed_interval: int, revision_count: int, days_left: int
) -> Optional[int]:
    if days_left <= 1:
        return None

    remaining_after_next = max(0, MAX_REVIEWS_PER_TOPIC - (revision_count + 1))
    free_days = max(1, days_left - 1)

    if remaining_after_next == 0:
        max_interval = free_days
    else:
        max_interval = max(1, free_days - remaining_after_next)

    interval = max(1, proposed_interval)
    interval = min(interval, max_interval)

    return interval if interval >= 1 else None


def schedule_next_revision(
    revision_count: int,
    difficulty: float,
    time_taken: float,
    time_expected: float,
    days_left: int,
) -> Dict[str, object]:
    if revision_count < 0:
        raise ValueError("revision_count must be non-negative")
    if days_left < 0:
        raise ValueError("days_left must be non-negative")

    if revision_count >= MAX_REVIEWS_PER_TOPIC:
        return ScheduleResult(
            interval_days=None,
            stage=_infer_stage(revision_count, days_left),
            is_bubble=False,
        ).to_dict()

    stage = _infer_stage(revision_count, days_left)
    is_bubble = _is_bubble_revision(revision_count)

    base_interval = _base_interval_for_revision(revision_count)
    perf_mult = _compute_performance_multiplier(difficulty, time_taken, time_expected)

    raw_interval = int(round(base_interval * perf_mult))
    if raw_interval < 1:
        raw_interval = 1

    interval = _respect_exam_horizon(raw_interval, revision_count, days_left)

    return ScheduleResult(
        interval_days=interval,
        stage=stage,
        is_bubble=is_bubble,
    ).to_dict()


def generate_adaptive_schedule(
    *,
    start_day: int,
    revision_count: int,
    difficulty: float,
    time_taken: float,
    time_expected: float,
    exam_day: int,
    limit: Optional[int] = None,
) -> Tuple[List[int], Set[int]]:
    """Iteratively project future revision days using adaptive spacing logic."""

    horizon_cap = TOTAL_DAYS if limit is None else max(0, min(TOTAL_DAYS, limit))
    if start_day >= horizon_cap:
        return [], set()

    planned_days: List[int] = []
    bubble_days: Set[int] = set()
    current_day = start_day
    current_revision = revision_count
    safety_iters = MAX_REVIEWS_PER_TOPIC + 5

    while safety_iters > 0:
        safety_iters -= 1

        effective_exam_day = min(exam_day, horizon_cap + 1)
        days_left = max(0, effective_exam_day - current_day)

        result = schedule_next_revision(
            revision_count=current_revision,
            difficulty=difficulty,
            time_taken=time_taken,
            time_expected=time_expected,
            days_left=days_left,
        )

        interval = result.get("interval_days")
        if interval is None:
            break

        next_day = current_day + int(interval)
        if next_day > horizon_cap:
            break
        if next_day >= exam_day:
            break
        if next_day <= current_day:
            next_day = current_day + 1
            if next_day > horizon_cap or next_day >= exam_day:
                break

        planned_days.append(next_day)
        if result.get("is_bubble"):
            bubble_days.add(next_day)

        current_day = next_day
        current_revision += 1

    return planned_days, bubble_days
