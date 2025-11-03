from __future__ import annotations

import itertools
import math
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .schemas import (
    AvailabilityChanges,
    DaySchedule,
    ReviewSession,
    ScheduleRequest,
    ScheduleResponse,
    ScheduleUpdate,
    StudyMode,
    TopicInput,
    TopicPerformance,
)


@dataclass
class TopicState:
    name: str
    importance: int = 3
    difficulty_score: float = 1.0
    ease: float = 1.0
    last_covered: Optional[date] = None
    last_review: Optional[date] = None
    recent_result: Optional[str] = None

    def boost_after_success(self) -> None:
        self.ease = min(self.ease + 0.2, 2.6)
        self.recent_result = "success"

    def penalize_after_failure(self) -> None:
        self.ease = max(self.ease - 0.3, 0.5)
        self.recent_result = "failure"


@dataclass
class SchedulePlan:
    schedule_id: str
    mode: StudyMode
    exam_date: date
    start_date: date
    topic_states: Dict[str, TopicState]
    availability: AvailabilityChanges = field(default_factory=AvailabilityChanges)


def parse_topic(topic: TopicInput | str) -> TopicInput:
    if isinstance(topic, TopicInput):
        return topic
    return TopicInput(name=topic)


DIFFICULTY_MAP = {
    "easy": 0.8,
    "medium": 1.0,
    "normal": 1.0,
    "hard": 1.3,
    "difficult": 1.3,
}


def importance_from_topic(topic: TopicInput) -> int:
    if topic.importance is not None:
        return topic.importance
    return 4 if topic.name else 3


def difficulty_from_topic(topic: TopicInput, performance: Optional[TopicPerformance]) -> float:
    if isinstance(topic.difficulty, (int, float)):
        value = float(topic.difficulty)
        return max(0.5, min(value, 2.0))
    if isinstance(topic.difficulty, str):
        return DIFFICULTY_MAP.get(topic.difficulty.lower(), 1.0)
    if performance:
        if performance.score is not None:
            return float(1.5 - performance.score)
        mastery = performance.masteryLevel
        if isinstance(mastery, (int, float)):
            return float(1.5 - min(max(mastery, 0.0), 1.0))
        if isinstance(mastery, str):
            mapped = DIFFICULTY_MAP.get(mastery.lower())
            if mapped:
                return mapped
    return 1.0


def initial_ease(performance: Optional[TopicPerformance]) -> float:
    if performance:
        if performance.score is not None:
            return 1.0 + (performance.score - 0.5)
        mastery = performance.masteryLevel
        if isinstance(mastery, (int, float)):
            return 1.0 + (float(mastery) - 0.5)
        if isinstance(mastery, str):
            if mastery.lower() in {"easy", "high", "strong"}:
                return 1.2
            if mastery.lower() in {"hard", "low", "weak"}:
                return 0.8
    return 1.0


def clamp_date_range(target_date: date, start: date, end: date) -> Optional[date]:
    if target_date < start or target_date > end:
        return None
    return target_date


def spaced_intervals_academic(topic: TopicState, base_date: date, exam_date: date) -> List[Tuple[date, int]]:
    base_intervals = [1, 3, 7, 14, 28, 42, 56]
    factor = max(0.5, min(topic.difficulty_score * (2.0 - topic.ease), 2.5))
    sessions: List[Tuple[date, int]] = []
    for index, days in enumerate(base_intervals):
        offset = max(1, int(round(days * factor)))
        review_date = base_date + timedelta(days=offset)
        clamped = clamp_date_range(review_date, base_date, exam_date)
        if clamped is None:
            break
        sessions.append((clamped, index))
        base_date = clamped
    return sessions


def spaced_intervals_effective(topic: TopicState, base_date: date, exam_date: date) -> List[Tuple[date, int]]:
    sessions: List[Tuple[date, int]] = []
    gap = 2 if topic.difficulty_score >= 1.2 or topic.ease < 1.0 else 5
    current_date = base_date + timedelta(days=gap)
    index = 0
    while current_date <= exam_date:
        sessions.append((current_date, index))
        growth = 1.6 + (topic.ease - 1.0) * 0.6
        gap = int(round(max(gap * growth, gap + 2)))
        gap = min(gap, 45)
        current_date += timedelta(days=gap)
        index += 1
    return sessions


def spaced_intervals_crunch(topic: TopicState, start_date: date, exam_date: date) -> List[Tuple[date, int]]:
    days_before = [1, 2, 3, 5, 7, 10, 14]
    if topic.importance >= 4 or topic.difficulty_score >= 1.2:
        sequence = days_before
    else:
        sequence = days_before[:4]
    sessions: List[Tuple[date, int]] = []
    index = 0
    for days in sequence:
        review_date = exam_date - timedelta(days=days)
        if review_date < start_date:
            continue
        if review_date > exam_date:
            continue
        sessions.append((review_date, index))
        index += 1
    sessions.sort(key=lambda x: x[0])
    return sessions


def choose_review_method(mode: StudyMode, position: int, total: int, days_until_exam: int) -> str:
    if mode == "Academic":
        if position == 0:
            return "summarize"
        if position == 1:
            return "teach-back"
        if position == 2:
            return "flashcards"
        return "practiceQuiz"
    if mode == "Effective":
        if position == 0:
            return "flashcards"
        if position == 1:
            return "practiceQuiz"
        if position == 2:
            return "mixedReview"
        return "pastQuestions"
    # Crunch mode
    if days_until_exam <= 1:
        return "quickRefresh"
    if days_until_exam <= 3:
        return "speedFlashcards"
    if position == total - 1:
        return "pastExamQuiz"
    if position == 0:
        return "diagnosticQuiz"
    return "practiceTest"


def distribute_sessions(
    sessions: List[Tuple[date, str, int, int]],
    availability: AvailabilityChanges,
    exam_date: date,
) -> Dict[date, List[Tuple[str, int, int]]]:
    max_per_day = availability.maxSessionsPerDay or 5
    blocked = set(availability.noStudyDays or [])

    day_map: Dict[date, List[Tuple[str, int, int]]] = defaultdict(list)

    for session_date, topic, index, total in sorted(sessions, key=lambda x: (x[0], x[1])):
        target_date = session_date
        direction = 1
        while target_date in blocked or len(day_map[target_date]) >= max_per_day:
            # Alternate moving forward/backward by one day to find a slot
            target_date += timedelta(days=direction)
            if target_date > exam_date:
                target_date = session_date - timedelta(days=1)
                direction = -1
            if target_date < session_date - timedelta(days=7):
                break
        day_map[target_date].append((topic, index, total))
    return day_map


def build_schedule_response(
    day_map: Dict[date, List[Tuple[str, int, int]]],
    mode: StudyMode,
    exam_date: date,
) -> List[DaySchedule]:
    days = sorted(day_map.keys())
    schedule: List[DaySchedule] = []
    for scheduled_day in days:
        if scheduled_day > exam_date:
            continue
        sessions = []
        for topic, index, total in sorted(day_map[scheduled_day], key=lambda x: x[0]):
            days_until_exam = (exam_date - scheduled_day).days
            method = choose_review_method(mode, index, total, days_until_exam)
            sessions.append(ReviewSession(topic=topic, reviewMethod=method))
        schedule.append(DaySchedule(date=scheduled_day, sessions=sessions))
    return schedule


class MemoryStore:
    def __init__(self) -> None:
        self._plans: Dict[str, SchedulePlan] = {}

    def create_plan(self, request: ScheduleRequest) -> ScheduleResponse:
        schedule_id = uuid.uuid4().hex
        start_date = request.startDate or date.today()
        topic_states: Dict[str, TopicState] = {}

        performance_map = request.pastPerformance or {}

        for topic_item in request.topics:
            topic = parse_topic(topic_item)
            perf = performance_map.get(topic.name)
            state = TopicState(
                name=topic.name,
                importance=importance_from_topic(topic),
                difficulty_score=difficulty_from_topic(topic, perf),
                ease=initial_ease(perf),
                last_covered=topic.lastCovered,
            )
            topic_states[state.name] = state

        plan = SchedulePlan(
            schedule_id=schedule_id,
            mode=request.mode,
            exam_date=request.examDate,
            start_date=start_date,
            topic_states=topic_states,
            availability=AvailabilityChanges(),
        )

        schedule = self._generate_schedule(plan)
        self._plans[schedule_id] = plan
        return ScheduleResponse(scheduleId=schedule_id, schedule=schedule)

    def update_plan(self, schedule_id: str, update: ScheduleUpdate) -> ScheduleResponse:
        plan = self._plans.get(schedule_id)
        if not plan:
            raise KeyError("Schedule not found")

        for session in update.completedSessions:
            topic_state = plan.topic_states.get(session.topic)
            if not topic_state:
                continue
            if isinstance(session.result, str) and session.result.lower() in {"success", "easy", "pass"}:
                topic_state.boost_after_success()
            elif isinstance(session.result, (int, float)) and float(session.result) >= 0.7:
                topic_state.boost_after_success()
            else:
                topic_state.penalize_after_failure()
            topic_state.last_review = session.date

        if update.newTopics:
            for topic_item in update.newTopics:
                topic = parse_topic(topic_item)
                if topic.name in plan.topic_states:
                    continue
                state = TopicState(
                    name=topic.name,
                    importance=importance_from_topic(topic),
                    difficulty_score=difficulty_from_topic(topic, None),
                    ease=initial_ease(None),
                    last_covered=topic.lastCovered,
                )
                plan.topic_states[state.name] = state

        if update.availabilityChanges:
            availability = plan.availability
            if update.availabilityChanges.noStudyDays is not None:
                availability.noStudyDays = update.availabilityChanges.noStudyDays
            if update.availabilityChanges.maxSessionsPerDay is not None:
                availability.maxSessionsPerDay = update.availabilityChanges.maxSessionsPerDay

        schedule = self._generate_schedule(plan, from_date=date.today())
        return ScheduleResponse(scheduleId=schedule_id, schedule=schedule)

    def get_plan(self, schedule_id: str) -> ScheduleResponse:
        plan = self._plans.get(schedule_id)
        if not plan:
            raise KeyError("Schedule not found")
        schedule = self._generate_schedule(plan)
        return ScheduleResponse(scheduleId=schedule_id, schedule=schedule)

    # Internal helpers
    def _generate_schedule(self, plan: SchedulePlan, from_date: Optional[date] = None) -> List[DaySchedule]:
        start_date = max(plan.start_date, from_date or plan.start_date)
        sessions: List[Tuple[date, str, int, int]] = []

        for topic in plan.topic_states.values():
            base_date = topic.last_review or topic.last_covered or start_date
            if base_date < start_date:
                base_date = start_date

            if plan.mode == "Academic":
                scheduled = spaced_intervals_academic(topic, base_date, plan.exam_date)
            elif plan.mode == "Effective":
                scheduled = spaced_intervals_effective(topic, base_date, plan.exam_date)
            else:
                scheduled = spaced_intervals_crunch(topic, start_date, plan.exam_date)

            total = len(scheduled) if scheduled else 1
            for review_date, index in scheduled:
                if review_date < start_date:
                    continue
                sessions.append((review_date, topic.name, index, total))

        day_map = distribute_sessions(sessions, plan.availability, plan.exam_date)
        return build_schedule_response(day_map, plan.mode, plan.exam_date)


store = MemoryStore()
