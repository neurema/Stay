"""Deterministic scheduler utilities for Stay Effective v5 topics.

References: Section 4 Base Schedule, Section 5 Bubble Revisions, Section 9 Daily
Scheduler & PendingPool in Stay_Effective_v5_Complete.md.
"""
from __future__ import annotations

from collections import defaultdict
from typing import DefaultDict, Dict, Iterable, List, Optional

from .constants import (
    HARD_BUBBLE_OFFSETS,
    HARD_REVISION_OFFSETS,
    SOFT_BUBBLE_OFFSETS,
    SOFT_REVISION_OFFSETS,
    TOTAL_DAYS,
)


def build_topic_schedule(
    add_day: int,
    is_hard: bool,
    *,
    bubble_days: Optional[Iterable[int]] = None,
    revision_offsets: Optional[Iterable[int]] = None,
) -> List[int]:
    """Build the initial deterministic schedule including bubble events."""

    offsets = list(revision_offsets) if revision_offsets is not None else (
        HARD_REVISION_OFFSETS if is_hard else SOFT_REVISION_OFFSETS
    )
    base_days = [add_day + offset for offset in offsets if add_day + offset <= TOTAL_DAYS]

    if bubble_days is None:
        bubble_offsets = HARD_BUBBLE_OFFSETS if is_hard else SOFT_BUBBLE_OFFSETS
        resolved_bubbles = [
            add_day + offset for offset in bubble_offsets if 0 <= add_day + offset <= TOTAL_DAYS
        ]
    else:
        resolved_bubbles = [day for day in bubble_days if 0 <= day <= TOTAL_DAYS]

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
