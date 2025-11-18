"""Service layer orchestrating Stay Effective v5 topic lifecycle.

References: Section 3 Initialization, Section 6 Formula Updates, Section 8 Revision
Execution, Section 9 Scheduler from Stay_Effective_v5_Complete.md.
"""
from __future__ import annotations

import csv
import math
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from . import models
from .constants import (
    ALPHA_PI,
    AS_INDEX_TABLE,
    DIFFICULTY_INDEX_TABLE,
    EF_MIN,
    MAX_BUBBLE_DAY,
    MAX_REVISIONS_DAY,
    RT_INDEX_TABLE,
    TMIN_DEFAULTS,
    TOTAL_DAYS,
)
from .formulas import (
    compute_crs_initial,
    compute_pi,
    update_crs,
    update_ef,
)
from .scheduler import DeterministicScheduler, generate_adaptive_schedule


@dataclass(frozen=True)
class BubbleTemplate:
    """Container describing a registered bubble schedule template."""

    values: Tuple[int, ...]
    relative: bool = False


@dataclass
class TopicState:
    """Internal topic state container matching Section 2 schema."""

    id: str
    subject_tag: str
    difficulty: float
    accuracy: float
    rt_ratio: float
    add_day: int
    exam_day: int
    bubble_id: Optional[str]
    is_hard: bool
    base_ef: float
    ef: float
    pi: float
    crs: float
    schedule: List[int] = field(default_factory=list)
    bubble_days: List[int] = field(default_factory=list)
    bubble_day_set: Set[int] = field(default_factory=set)
    template_bubble_days: Set[int] = field(default_factory=set)
    revision_count: int = 0
    history: List[Tuple[int, bool, float, float, float, Optional[int]]] = field(default_factory=list)
    nd: int = 0
    ns: int = 0
    tmin: float = 0.0


_topics: Dict[str, TopicState] = {}
_scheduler = DeterministicScheduler()
_bubble_templates: Dict[str, BubbleTemplate] = {}


def _exam_limit(exam_day: int) -> int:
    """Return the inclusive last revision day before the exam."""

    return max(0, min(TOTAL_DAYS, exam_day - 1))


def _state_exam_limit(state: TopicState) -> int:
    return _exam_limit(state.exam_day)


def _clamp_schedule_to_exam(state: TopicState) -> None:
    """Ensure planned revisions and bubbles do not extend beyond the exam."""

    limit = _state_exam_limit(state)
    state.schedule = sorted(day for day in state.schedule if day <= limit)
    if state.bubble_day_set:
        state.bubble_day_set = {day for day in state.bubble_day_set if day <= limit}
        state.bubble_days = sorted(state.bubble_day_set)
    else:
        state.bubble_day_set = set()
        state.bubble_days = []



def _lookup_index(table: List[Tuple[float, float, float]], value: float) -> float:
    for lower, upper, mapped in table:
        upper_ok = True if math.isinf(upper) else value <= upper
        if lower <= value and upper_ok:
            return mapped
    return table[-1][2]


def _difficulty_index(difficulty: float) -> float:
    bands = {
        "easy": 0.34,
        "moderate": 0.67,
    }
    if difficulty < bands["easy"]:
        return DIFFICULTY_INDEX_TABLE["easy"]
    if difficulty < bands["moderate"]:
        return DIFFICULTY_INDEX_TABLE["moderate"]
    return DIFFICULTY_INDEX_TABLE["hard"]


def _resolve_tmin(payload: models.TopicCreate) -> float:
    if payload.tmin_override is not None:
        return payload.tmin_override
    if payload.tmin_label not in TMIN_DEFAULTS:
        raise ValueError(f"Unknown Tmin label '{payload.tmin_label}'")
    return TMIN_DEFAULTS[payload.tmin_label]


def _resolve_bubble_days(bubble_id: Optional[str], add_day: int) -> Optional[List[int]]:
    if not bubble_id:
        return None
    template = _bubble_templates.get(bubble_id)
    if template is None:
        raise ValueError(f"Bubble '{bubble_id}' has not been registered")

    if template.relative:
        resolved = [add_day + offset for offset in template.values]
    else:
        resolved = list(template.values)

    normalized = sorted({day for day in resolved if 0 <= day <= TOTAL_DAYS})
    return normalized if normalized else None


def _serialize_state(state: TopicState) -> models.Topic:
    return models.Topic(
        id=state.id,
        subject_tag=state.subject_tag,
        difficulty=state.difficulty,
        accuracy=state.accuracy,
        rt_ratio=state.rt_ratio,
        add_day=state.add_day,
        bubble_id=state.bubble_id,
        is_hard=state.is_hard,
        base_ef=state.base_ef,
        ef=state.ef,
        pi=state.pi,
        crs=state.crs,
        nd=state.nd,
        ns=state.ns,
        tmin=state.tmin,
        schedule=sorted(state.schedule),
        revision_count=state.revision_count,
        history=list(state.history),
    )


def _resolve_time_inputs(state: TopicState) -> Tuple[float, float]:
    """Derive time_taken/time_expected inputs for adaptive scheduling."""

    time_expected = 1.0
    ratio = state.rt_ratio if state.rt_ratio > 0 else 1.0
    time_taken = max(0.05, ratio * time_expected)
    return time_taken, time_expected


def _rebuild_schedule(state: TopicState, anchor_day: int) -> None:
    """Recompute the forward-looking schedule using adaptive spacing."""

    limit = _state_exam_limit(state)
    if limit <= anchor_day:
        state.schedule = []
        state.bubble_day_set = set()
        state.bubble_days = []
        _scheduler.register_topic(state.id, [])
        return

    time_taken, time_expected = _resolve_time_inputs(state)
    adaptive_days, adaptive_bubbles = generate_adaptive_schedule(
        start_day=anchor_day,
        revision_count=state.revision_count,
        difficulty=state.difficulty,
        time_taken=time_taken,
        time_expected=time_expected,
        exam_day=state.exam_day,
        limit=limit,
    )

    executed_days = {day for day, *_ in state.history}
    executed_days.add(anchor_day)

    future_days = {
        day
        for day in adaptive_days
        if anchor_day < day <= limit and day not in executed_days
    }
    adaptive_bubble_set = {
        day for day in adaptive_bubbles if day in future_days
    }

    template_future = {
        day
        for day in state.template_bubble_days
        if anchor_day < day <= TOTAL_DAYS and day not in executed_days
    }

    combined_days = sorted(future_days | template_future)
    bubble_set = adaptive_bubble_set | template_future

    state.schedule = combined_days
    state.bubble_day_set = bubble_set
    state.bubble_days = sorted(bubble_set)
    _scheduler.register_topic(state.id, state.schedule)


def _recompute_base_ef(state: TopicState) -> None:
    """Recalculate the base EF using the latest RT/AS/D inputs."""

    rt_index = _lookup_index(RT_INDEX_TABLE, state.rt_ratio)
    as_index = _lookup_index(AS_INDEX_TABLE, state.accuracy)
    d_index = _difficulty_index(state.difficulty)
    state.base_ef = rt_index + d_index + as_index
    state.ef = max(EF_MIN, state.ef)


def create_topic(payload: models.TopicCreate) -> models.Topic:
    """Create a topic following Sections 3 & 6 initialization rules."""

    topic_id = str(uuid.uuid4())

    rt_index = _lookup_index(RT_INDEX_TABLE, payload.rt_ratio)
    as_index = _lookup_index(AS_INDEX_TABLE, payload.accuracy)
    d_index = _difficulty_index(payload.difficulty)

    base_ef = rt_index + d_index + as_index
    ef = max(EF_MIN, base_ef)

    tmin = _resolve_tmin(payload)
    pi = payload.initial_pi if payload.initial_pi else compute_pi(payload.nd, payload.ns, tmin)
    crs = compute_crs_initial(ef, pi)

    is_hard = payload.difficulty >= 0.7
    bubble_id = payload.bubble_id

    exam_day = payload.add_day + payload.nd
    limit = _exam_limit(exam_day)

    explicit_bubbles: Optional[List[int]] = None
    if bubble_id is not None:
        explicit_bubbles = _resolve_bubble_days(bubble_id, payload.add_day)

    template_bubble_days = (
        {day for day in explicit_bubbles if 0 <= day <= TOTAL_DAYS} if explicit_bubbles else set()
    )

    state = TopicState(
        id=topic_id,
        subject_tag=payload.subject_tag,
        difficulty=payload.difficulty,
        accuracy=payload.accuracy,
        rt_ratio=payload.rt_ratio,
        add_day=payload.add_day,
        exam_day=exam_day,
        bubble_id=bubble_id,
        is_hard=is_hard,
        base_ef=base_ef,
        ef=ef,
        pi=pi,
        crs=crs,
        schedule=[],
        bubble_days=[],
        bubble_day_set=set(),
        template_bubble_days=template_bubble_days,
        revision_count=0,
        nd=payload.nd,
        ns=payload.ns,
        tmin=tmin,
    )
    _topics[topic_id] = state
    _rebuild_schedule(state, payload.add_day)

    return _serialize_state(state)


def create_topics(payloads: Iterable[models.TopicCreate]) -> List[models.Topic]:
    """Create multiple topics while preserving request order."""

    results: List[models.Topic] = []
    for payload in payloads:
        results.append(create_topic(payload))
    return results


def execute_revision(result: models.SessionResult) -> models.Topic:
    """Execute a revision deterministically (Section 8)."""

    if result.topic_id not in _topics:
        raise KeyError(f"Topic {result.topic_id} not found")

    state = _topics[result.topic_id]

    if result.day > TOTAL_DAYS:
        raise ValueError("Day exceeds TOTAL_DAYS from Section 1")

    if result.day in state.schedule:
        state.schedule = [day for day in state.schedule if day != result.day]
    _scheduler.remove_day(state.id, result.day)

    if result.day in state.bubble_day_set:
        state.bubble_day_set.discard(result.day)
        state.bubble_days = [day for day in state.bubble_days if day != result.day]

    state.ef = update_ef(state.ef, result.success)

    if result.nd is not None:
        state.nd = result.nd
        state.exam_day = result.day + result.nd
    if result.ns is not None:
        state.ns = result.ns
    if result.tmin_override is not None:
        state.tmin = result.tmin_override
    elif result.tmin_label is not None:
        if result.tmin_label not in TMIN_DEFAULTS:
            raise ValueError(f"Unknown Tmin label '{result.tmin_label}'")
        state.tmin = TMIN_DEFAULTS[result.tmin_label]

    if result.accuracy is not None:
        state.accuracy = result.accuracy
    if result.rt_ratio is not None:
        state.rt_ratio = result.rt_ratio

    if result.day in state.template_bubble_days:
        state.template_bubble_days.discard(result.day)

    if result.difficulty is not None:
        state.difficulty = result.difficulty

    state.is_hard = state.difficulty >= 0.7

    _recompute_base_ef(state)

    recomputed_pi = compute_pi(state.nd, state.ns, state.tmin)
    state.pi = ALPHA_PI * state.pi + (1.0 - ALPHA_PI) * recomputed_pi
    state.crs = update_crs(state.crs, state.ef, state.pi)

    state.revision_count += 1
    state.history.append((result.day, result.success, state.ef, state.pi, state.crs, None))

    _rebuild_schedule(state, result.day)

    next_day_value = state.schedule[0] if state.schedule else None
    state.history[-1] = (
        result.day,
        result.success,
        state.ef,
        state.pi,
        state.crs,
        next_day_value,
    )

    return _serialize_state(state)


def get_topic(topic_id: str) -> models.Topic:
    if topic_id not in _topics:
        raise KeyError(f"Topic {topic_id} not found")
    return _serialize_state(_topics[topic_id])


def get_schedule_for_day(day: int) -> Dict[str, Any]:
    if day > TOTAL_DAYS:
        raise ValueError("Requested day exceeds TOTAL_DAYS")
    scheduled_topics: List[Tuple[str, bool]] = []
    for topic_id in _scheduler.get_schedule_for_day(day):
        state = _topics.get(topic_id)
        if state is None:
            continue
        is_bubble_day = day in state.bubble_day_set
        scheduled_topics.append((topic_id, is_bubble_day))

    total_count = len(scheduled_topics)
    bubble_total_count = sum(1 for _topic_id, is_bubble_day in scheduled_topics if is_bubble_day)

    limited_topics: List[str] = []
    bubble_capped_count = 0

    for topic_id, is_bubble_day in scheduled_topics:
        if is_bubble_day and bubble_capped_count >= MAX_BUBBLE_DAY:
            continue

        if len(limited_topics) >= MAX_REVISIONS_DAY:
            break

        limited_topics.append(topic_id)
        if is_bubble_day:
            bubble_capped_count += 1

    return {
        "day": day,
        "topics": limited_topics,
        "total_count": total_count,
        "capped_count": len(limited_topics),
        "overflow_count": max(0, total_count - len(limited_topics)),
        "bubble_total_count": bubble_total_count,
        "bubble_capped_count": bubble_capped_count,
        "bubble_overflow_count": max(0, bubble_total_count - bubble_capped_count),
    }


def export_topic_schedule_csv(output_path: Path) -> Path:
    """Export per-topic timeline rows capturing intro, revisions, and bubble entry."""

    if not _topics:
        raise ValueError("No topics have been registered")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "topic_id",
        "subject_tag",
        "is_hard",
        "bubble_topic",
        "event_type",
        "status",
        "sequence",
        "day",
        "bubble_entry_day",
        "success",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()

        for state in sorted(_topics.values(), key=lambda item: (item.add_day, item.subject_tag)):
            bubble_days = sorted(state.bubble_days)
            bubble_day_set = state.bubble_day_set
            bubble_entry_day = bubble_days[0] if bubble_days else None

            def classify(day: int) -> str:
                if day in bubble_day_set:
                    return "bubble_entry" if bubble_entry_day is not None and day == bubble_entry_day else "bubble_review"
                return "normal_review"

            writer.writerow(
                {
                    "topic_id": state.id,
                    "subject_tag": state.subject_tag,
                    "is_hard": state.is_hard,
                    "bubble_topic": state.bubble_id is not None,
                    "event_type": "intro",
                    "status": "fixed",
                    "sequence": 0,
                    "day": state.add_day,
                    "bubble_entry_day": bubble_entry_day if bubble_entry_day is not None else "",
                    "success": "",
                }
            )

            for seq, (day, success, *_rest) in enumerate(state.history, start=1):
                writer.writerow(
                    {
                        "topic_id": state.id,
                        "subject_tag": state.subject_tag,
                        "is_hard": state.is_hard,
                        "bubble_topic": state.bubble_id is not None,
                        "event_type": classify(day),
                        "status": "completed",
                        "sequence": seq,
                        "day": day,
                        "bubble_entry_day": bubble_entry_day if bubble_entry_day is not None else "",
                        "success": success,
                    }
                )

            next_seq = len(state.history) + 1
            completed_days = {day for day, *_ in state.history}
            for day in sorted(state.schedule):
                if day in completed_days:
                    continue
                writer.writerow(
                    {
                        "topic_id": state.id,
                        "subject_tag": state.subject_tag,
                        "is_hard": state.is_hard,
                        "bubble_topic": state.bubble_id is not None,
                        "event_type": classify(day),
                        "status": "planned",
                        "sequence": next_seq,
                        "day": day,
                        "bubble_entry_day": bubble_entry_day if bubble_entry_day is not None else "",
                        "success": "",
                    }
                )
                next_seq += 1

    return output_path



def register_bubble_template(
    bubble_id: str,
    bubble_days: Iterable[int],
    *,
    relative: bool = False,
) -> None:
    """Register or overwrite a bubble schedule template."""

    if not bubble_id:
        raise ValueError("Bubble id must be a non-empty string")

    raw_values = {int(day) for day in bubble_days}
    if relative:
        normalized = sorted(day for day in raw_values if day >= 0)
        if not normalized:
            raise ValueError("Relative bubble schedule must include non-negative offsets")
    else:
        normalized = sorted(day for day in raw_values if 0 <= day <= TOTAL_DAYS)
        if not normalized:
            raise ValueError("Bubble schedule must include at least one day within TOTAL_DAYS")

    _bubble_templates[bubble_id] = BubbleTemplate(tuple(normalized), relative)


def configure_bubble_templates(templates: Dict[str, Any]) -> None:
    """Replace all registered bubble templates with the provided mapping."""

    _bubble_templates.clear()
    for bubble_id, definition in templates.items():
        if isinstance(definition, dict):
            values = definition.get("values")
            if values is None:
                raise ValueError(f"Bubble template '{bubble_id}' must include 'values'")
            relative = bool(definition.get("relative", False))
            register_bubble_template(bubble_id, values, relative=relative)
        else:
            register_bubble_template(bubble_id, definition)


def get_bubble_template(bubble_id: str) -> Optional[Dict[str, Any]]:
    """Return a copy of the registered bubble template for inspection."""

    template = _bubble_templates.get(bubble_id)
    if template is None:
        return None
    return {"values": list(template.values), "relative": template.relative}
