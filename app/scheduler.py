from __future__ import annotations

import math
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Deque, Dict, List, Optional, Sequence, Tuple

from .schemas import (
    AvailabilityChanges,
    CompletedSession,
    DaySchedule,
    ReviewSession,
    ScheduleRequest,
    ScheduleResponse,
    ScheduleUpdate,
    StudyMode,
    TopicContribution,
    TopicInput,
    TopicPerformance,
)

STARTING_EF = 2.3
MIN_EF = 1.3
MAX_EF = 3.0
MIN_INTERVAL_DAYS = 0.3
BUBBLE_AGGRESSIVENESS = 0.4
BUBBLE_MAX_TOPICS = 5
SCHEDULE_WINDOW_DAYS = 14
DEFAULT_PERFORMANCE = 0.75
DEFAULT_INTERLEAVING = 0.7
MAX_ALERTS = 12

DIFFICULTY_MAP = {
    "easy": 0.8,
    "medium": 1.0,
    "normal": 1.0,
    "hard": 1.3,
    "difficult": 1.3,
}

CONFIDENCE_MAP = {
    "Easy": 1.0,
    "Medium": None,  # Use MCQ score
    "Hard": 0.0,
}


def parse_topic(topic: TopicInput | str) -> TopicInput:
    if isinstance(topic, TopicInput):
        return topic
    return TopicInput(name=topic)


def importance_from_topic(topic: TopicInput) -> int:
    if topic.importance is not None:
        return topic.importance
    return 3


def difficulty_from_topic(topic: TopicInput, performance: Optional[TopicPerformance]) -> float:
    if isinstance(topic.difficulty, (int, float)):
        return max(0.5, min(float(topic.difficulty), 2.0))
    if isinstance(topic.difficulty, str):
        return DIFFICULTY_MAP.get(topic.difficulty.lower(), 1.0)
    if performance:
        if performance.score is not None:
            return max(0.5, min(1.5 - performance.score, 2.0))
        mastery = performance.masteryLevel
        if isinstance(mastery, (int, float)):
            return max(0.5, min(1.5 - float(mastery), 2.0))
        if isinstance(mastery, str):
            mapped = DIFFICULTY_MAP.get(mastery.lower())
            if mapped:
                return mapped
    return 1.0


def normalize_tags(raw_tags: Optional[Sequence[str]]) -> Tuple[str, ...]:
    if not raw_tags:
        return tuple()
    cleaned = sorted({tag.strip().lower() for tag in raw_tags if tag and tag.strip()})
    return tuple(cleaned)


def confidence_modifier(confidence: str, mcq_score: float) -> float:
    modifier = CONFIDENCE_MAP.get(confidence, None)
    if modifier is None:
        return mcq_score
    return modifier


def time_ratio(planned_minutes: int, actual_minutes: int) -> float:
    planned = max(planned_minutes, 1)
    actual = max(actual_minutes, 1)
    return actual / planned


def time_bonus(planned_minutes: int, actual_minutes: int) -> float:
    if actual_minutes > 3 * max(planned_minutes, 1):
        return 0.0
    ratio = max(planned_minutes, 1) / max(actual_minutes, 1)
    bonus = ratio * 1.2
    return max(0.0, min(1.0, bonus))


def aggressiveness_factor(days_until_exam: int) -> float:
    if days_until_exam <= 7:
        return 0.5
    if days_until_exam <= 21:
        return 0.35
    if days_until_exam <= 42:
        return 0.25
    return 0.15


@dataclass
class TopicState:
    name: str
    importance: int
    difficulty: float
    tags: Tuple[str, ...] = field(default_factory=tuple)
    ef: float = STARTING_EF
    interval: float = 0.0
    next_review: Optional[date] = None
    revision_count: int = 0
    last_review: Optional[date] = None
    performance_history: Deque[float] = field(default_factory=lambda: deque(maxlen=5))
    bubble_id: Optional[str] = None

    def clone(self) -> "TopicState":
        clone_history = deque(self.performance_history, maxlen=self.performance_history.maxlen)
        return TopicState(
            name=self.name,
            importance=self.importance,
            difficulty=self.difficulty,
            tags=self.tags,
            ef=self.ef,
            interval=self.interval,
            next_review=self.next_review,
            revision_count=self.revision_count,
            last_review=self.last_review,
            performance_history=clone_history,
            bubble_id=self.bubble_id,
        )


@dataclass
class BubbleState:
    bubble_id: str
    topics: List[str]
    coherence_factor: float
    interval: float = 0.0
    next_review: Optional[date] = None
    recent_scores: Deque[float] = field(default_factory=lambda: deque(maxlen=2))
    last_session: Optional[date] = None

    def clone(self) -> "BubbleState":
        return BubbleState(
            bubble_id=self.bubble_id,
            topics=list(self.topics),
            coherence_factor=self.coherence_factor,
            interval=self.interval,
            next_review=self.next_review,
            recent_scores=deque(self.recent_scores, maxlen=self.recent_scores.maxlen),
            last_session=self.last_session,
        )


@dataclass
class SchedulePlan:
    schedule_id: str
    mode: StudyMode
    exam_date: date
    start_date: date
    topic_states: Dict[str, TopicState]
    availability: AvailabilityChanges = field(default_factory=AvailabilityChanges)
    bubbles: Dict[str, BubbleState] = field(default_factory=dict)
    alerts: List[str] = field(default_factory=list)


def compute_performance_score(session: CompletedSession) -> Tuple[float, float, float]:
    ratio = time_ratio(session.plannedMinutes, session.actualMinutes)
    bonus = time_bonus(session.plannedMinutes, session.actualMinutes)
    modifier = confidence_modifier(session.confidence, session.mcqScore)
    performance = (session.mcqScore + modifier + bonus) / 3.0
    if session.mcqScore >= 1.0 and ratio < 0.5:
        performance *= 0.8
    return performance, ratio, bonus


def compute_topic_interval(
    topic: TopicState,
    performance: float,
    session_date: date,
    days_until_exam: int,
    ratio: float,
    missed_days: float,
) -> float:
    ef_delta = 0.12 - (1.0 - performance) * (0.1 + (ratio - 1.0))
    topic.ef = max(MIN_EF, min(MAX_EF, topic.ef + ef_delta))

    if topic.revision_count == 0 or topic.interval == 0.0:
        if performance >= 0.85:
            interval = 2.0
        elif performance >= 0.65:
            interval = 1.0
        else:
            interval = MIN_INTERVAL_DAYS
    else:
        interval = max(MIN_INTERVAL_DAYS, topic.interval * topic.ef)

    interval = min(interval, max(days_until_exam, 0) * aggressiveness_factor(days_until_exam))
    interval = max(MIN_INTERVAL_DAYS, interval)

    if missed_days > 0:
        previous = max(topic.interval, MIN_INTERVAL_DAYS)
        decay = math.exp(-missed_days / (previous * 2.0))
        interval *= 0.7 + 0.3 * decay

    topic.interval = interval
    topic.revision_count += 1
    topic.last_review = session_date
    topic.performance_history.append(performance)
    topic.next_review = session_date + timedelta(days=math.ceil(interval))
    return interval


def compute_bubble_interval(
    bubble: BubbleState,
    topics: Sequence[TopicState],
    session_date: date,
    days_until_exam: int,
) -> float:
    topic_components = [max(t.interval, 1.0) for t in topics]
    if not topic_components:
        return bubble.interval
    strength_numerator = 0.0
    for topic in topics:
        last_score = topic.performance_history[-1] if topic.performance_history else DEFAULT_PERFORMANCE
        strength_numerator += topic.ef * last_score
    strength = (strength_numerator / len(topics)) * bubble.coherence_factor
    avg_interval = sum(topic_components) / len(topic_components)
    interval = avg_interval * strength * BUBBLE_AGGRESSIVENESS
    interval = min(interval, max(days_until_exam, 0) * 0.25)
    interval = max(MIN_INTERVAL_DAYS, interval)
    bubble.interval = interval
    bubble.next_review = session_date + timedelta(days=math.ceil(interval))
    return interval


def choose_review_method(
    mode: StudyMode,
    session_type: str,
    position: int,
    total: int,
    days_until_exam: int,
) -> str:
    if session_type == "bubble":
        if mode == "Academic":
            return "bubbleSynthesis" if position == 0 else "bubbleDrill"
        if mode == "Effective":
            return "bubbleInterleaving" if position == 0 else "bubbleMixedReview"
        if days_until_exam <= 3:
            return "bubbleSprint"
        return "bubblePastPapers"

    if mode == "Academic":
        if position == 0:
            return "summarize"
        if position == 1:
            return "teachBack"
        if position == 2:
            return "flashcards"
        return "practiceQuiz"
    if mode == "Effective":
        if position == 0:
            return "diagnosticQuiz"
        if position == total - 1:
            return "pastQuestions"
        return "mixedReview"

    if days_until_exam <= 1:
        return "quickRefresh"
    if days_until_exam <= 3:
        return "speedFlashcards"
    if position == total - 1:
        return "pastExamQuiz"
    if position == 0:
        return "diagnosticQuiz"
    return "practiceTest"


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
            topic_states[topic.name] = TopicState(
                name=topic.name,
                importance=importance_from_topic(topic),
                difficulty=difficulty_from_topic(topic, perf),
                tags=normalize_tags(topic.tags),
                ef=STARTING_EF,
                interval=0.0,
                next_review=start_date,
                revision_count=0,
            )

        plan = SchedulePlan(
            schedule_id=schedule_id,
            mode=request.mode,
            exam_date=request.examDate,
            start_date=start_date,
            topic_states=topic_states,
        )

        self._reevaluate_bubbles(plan, start_date)
        schedule = self._generate_schedule(plan, start_date)
        self._plans[schedule_id] = plan
        return ScheduleResponse(scheduleId=schedule_id, schedule=schedule, alerts=list(plan.alerts))

    def update_plan(self, schedule_id: str, update: ScheduleUpdate) -> ScheduleResponse:
        plan = self._plans.get(schedule_id)
        if not plan:
            raise KeyError("Schedule not found")

        for session in update.completedSessions:
            if session.sessionType == "bubble":
                self._apply_bubble_session(plan, session)
            else:
                self._apply_individual_session(plan, session)

        if update.newTopics:
            for topic_item in update.newTopics:
                topic = parse_topic(topic_item)
                if topic.name in plan.topic_states:
                    continue
                plan.topic_states[topic.name] = TopicState(
                    name=topic.name,
                    importance=importance_from_topic(topic),
                    difficulty=difficulty_from_topic(topic, None),
                    tags=normalize_tags(topic.tags),
                    ef=STARTING_EF,
                    interval=0.0,
                    next_review=date.today(),
                    revision_count=0,
                )

        if update.availabilityChanges:
            availability = plan.availability
            if update.availabilityChanges.noStudyDays is not None:
                availability.noStudyDays = update.availabilityChanges.noStudyDays
            if update.availabilityChanges.maxSessionsPerDay is not None:
                availability.maxSessionsPerDay = update.availabilityChanges.maxSessionsPerDay

        reference_date = max(date.today(), plan.start_date)
        self._reevaluate_bubbles(plan, reference_date)
        schedule = self._generate_schedule(plan, reference_date)
        plan.alerts = plan.alerts[-MAX_ALERTS:]
        return ScheduleResponse(scheduleId=schedule_id, schedule=schedule, alerts=list(plan.alerts))

    def get_plan(self, schedule_id: str) -> ScheduleResponse:
        plan = self._plans.get(schedule_id)
        if not plan:
            raise KeyError("Schedule not found")
        reference_date = max(date.today(), plan.start_date)
        self._reevaluate_bubbles(plan, reference_date)
        schedule = self._generate_schedule(plan, reference_date)
        plan.alerts = plan.alerts[-MAX_ALERTS:]
        return ScheduleResponse(scheduleId=schedule_id, schedule=schedule, alerts=list(plan.alerts))

    def _apply_individual_session(self, plan: SchedulePlan, session: CompletedSession) -> None:
        topic = plan.topic_states.get(session.topic or "")
        if not topic:
            return

        performance, ratio, bonus = compute_performance_score(session)
        if session.actualMinutes > 3 * max(session.plannedMinutes, 1):
            plan.alerts.append(
                f"Focus warning for {topic.name} on {session.date.isoformat()}: exceeded planned time."
            )

        missed_days = 0.0
        if topic.next_review and session.date > topic.next_review:
            missed_days = float((session.date - topic.next_review).days)

        days_until_exam = max((plan.exam_date - session.date).days, 0)
        compute_topic_interval(topic, performance, session.date, days_until_exam, ratio, missed_days)

        plan.alerts = plan.alerts[-MAX_ALERTS:]

    def _apply_bubble_session(self, plan: SchedulePlan, session: CompletedSession) -> None:
        bubble = plan.bubbles.get(session.bubbleId or "")
        if not bubble:
            return

        efficiency = time_bonus(session.plannedMinutes, session.actualMinutes)
        if session.actualMinutes > 3 * max(session.plannedMinutes, 1):
            efficiency = 0.0
            plan.alerts.append(
                f"Focus warning for bubble {bubble.bubble_id} on {session.date.isoformat()}: session overran."
            )

        interleaving = session.interleavingScore if session.interleavingScore is not None else DEFAULT_INTERLEAVING
        bubble_p = (session.mcqScore + efficiency + interleaving) / 3.0

        bubble.recent_scores.append(bubble_p)
        bubble.last_session = session.date

        topic_contrib_map: Dict[str, TopicContribution] = {}
        if session.topicsCovered:
            for contrib in session.topicsCovered:
                topic_contrib_map[contrib.topic] = contrib

        days_until_exam = max((plan.exam_date - session.date).days, 0)

        for topic_name in bubble.topics:
            topic = plan.topic_states.get(topic_name)
            if not topic:
                continue
            contrib = topic_contrib_map.get(topic_name)
            ratio = 1.0
            if session.plannedMinutes > 0:
                ratio = time_ratio(session.plannedMinutes, session.actualMinutes)
            topic_ratio = contrib.correct / contrib.total if contrib and contrib.total else 0.0
            topic_adjusted = bubble_p * (0.7 + 0.3 * topic_ratio)

            if topic.next_review and session.date > topic.next_review:
                missed_days = float((session.date - topic.next_review).days)
            else:
                missed_days = 0.0

            compute_topic_interval(topic, topic_adjusted, session.date, days_until_exam, ratio, missed_days)

        compute_bubble_interval(
            bubble,
            [plan.topic_states[name] for name in bubble.topics if name in plan.topic_states],
            session.date,
            days_until_exam,
        )

        plan.alerts = plan.alerts[-MAX_ALERTS:]

    def _generate_schedule(self, plan: SchedulePlan, reference_date: date) -> List[DaySchedule]:
        reference_date = max(reference_date, plan.start_date)
        projected_topics = {name: topic.clone() for name, topic in plan.topic_states.items()}
        projected_bubbles = {bid: bubble.clone() for bid, bubble in plan.bubbles.items()}
        schedule: List[DaySchedule] = []
        current_day = reference_date
        end_day = min(plan.exam_date, reference_date + timedelta(days=SCHEDULE_WINDOW_DAYS - 1))
        blocked_days = set(plan.availability.noStudyDays or [])
        max_per_day_setting = plan.availability.maxSessionsPerDay

        while current_day <= end_day:
            if current_day in blocked_days:
                current_day += timedelta(days=1)
                continue

            day_schedule = self._build_daily_queue(plan, projected_topics, projected_bubbles, current_day, max_per_day_setting)
            if day_schedule.sessions:
                schedule.append(day_schedule)

            current_day += timedelta(days=1)
        return schedule

    def _build_daily_queue(
        self,
        plan: SchedulePlan,
        projected_topics: Dict[str, TopicState],
        projected_bubbles: Dict[str, BubbleState],
        current_day: date,
        max_per_day_setting: Optional[int],
    ) -> DaySchedule:
        days_until_exam = max((plan.exam_date - current_day).days, 0)
        max_daily = min(12, math.ceil(max(days_until_exam, 1) * 0.4))
        if max_per_day_setting is not None:
            max_daily = min(max_daily, max_per_day_setting)
        max_daily = max(1, max_daily)

        overdue_topics: List[TopicState] = []
        due_topics: List[TopicState] = []

        for topic in projected_topics.values():
            if not topic.next_review:
                topic.next_review = current_day
            if topic.next_review < current_day:
                overdue_topics.append(topic)
            elif topic.next_review == current_day:
                due_topics.append(topic)

        overdue_topics.sort(key=lambda t: (t.next_review or current_day))
        due_topics.sort(
            key=lambda t: (
                t.ef,
                (t.interval or 1.0) / max(days_until_exam, 1),
            )
        )

        bubble_queue: List[BubbleState] = []
        for bubble in projected_bubbles.values():
            if not bubble.next_review:
                bubble.next_review = current_day
            if bubble.next_review <= current_day:
                bubble_queue.append(bubble)
        bubble_queue.sort(key=lambda b: (b.next_review or current_day))

        selected_topics: List[TopicState] = []
        selected_bubbles: List[BubbleState] = []

        for topic in overdue_topics:
            if len(selected_topics) + len(selected_bubbles) >= max_daily:
                break
            selected_topics.append(topic)

        remaining_capacity = max_daily - (len(selected_topics) + len(selected_bubbles))

        desired_bubble = min(len(bubble_queue), int(round(max_daily * 0.7)))
        while bubble_queue and remaining_capacity > 0 and len(selected_bubbles) < desired_bubble:
            selected_bubbles.append(bubble_queue.pop(0))
            remaining_capacity -= 1

        while due_topics and remaining_capacity > 0:
            selected_topics.append(due_topics.pop(0))
            remaining_capacity -= 1

        sessions: List[ReviewSession] = []

        total_individual = len(selected_topics)
        total_bubble = len(selected_bubbles)

        for index, topic in enumerate(selected_topics):
            method = choose_review_method(plan.mode, "individual", index, total_individual, days_until_exam)
            sessions.append(
                ReviewSession(
                    sessionType="individual",
                    reviewMethod=method,
                    topic=topic.name,
                )
            )
            self._simulate_topic_session(topic, current_day, plan.exam_date)

        for index, bubble in enumerate(selected_bubbles):
            method = choose_review_method(plan.mode, "bubble", index, total_bubble, days_until_exam)
            sessions.append(
                ReviewSession(
                    sessionType="bubble",
                    reviewMethod=method,
                    bubbleId=bubble.bubble_id,
                    topics=list(bubble.topics),
                )
            )
            self._simulate_bubble_session(bubble, projected_topics, current_day, plan.exam_date)

        return DaySchedule(date=current_day, sessions=sessions)

    def _simulate_topic_session(self, topic: TopicState, session_date: date, exam_date: date) -> None:
        baseline = topic.performance_history[-1] if topic.performance_history else DEFAULT_PERFORMANCE
        missed_days = 0.0
        if topic.next_review and session_date > topic.next_review:
            missed_days = float((session_date - topic.next_review).days)
        days_until_exam = max((exam_date - session_date).days, 0)
        compute_topic_interval(
            topic,
            baseline,
            session_date,
            days_until_exam,
            1.0,
            missed_days,
        )

    def _simulate_bubble_session(
        self,
        bubble: BubbleState,
        projected_topics: Dict[str, TopicState],
        session_date: date,
        exam_date: date,
    ) -> None:
        for topic_name in bubble.topics:
            topic = projected_topics.get(topic_name)
            if not topic:
                continue
            self._simulate_topic_session(topic, session_date, exam_date)
        days_until_exam = max((exam_date - session_date).days, 0)
        compute_bubble_interval(
            bubble,
            [projected_topics[name] for name in bubble.topics if name in projected_topics],
            session_date,
            days_until_exam,
        )

    def _reevaluate_bubbles(self, plan: SchedulePlan, reference_date: date) -> None:
        days_until_exam = max((plan.exam_date - reference_date).days, 0)
        if days_until_exam < 5:
            for bubble in plan.bubbles.values():
                for topic_name in bubble.topics:
                    topic = plan.topic_states.get(topic_name)
                    if topic and topic.bubble_id == bubble.bubble_id:
                        topic.bubble_id = None
            plan.bubbles.clear()
            return

        dissolve: List[str] = []
        for bubble_id, bubble in plan.bubbles.items():
            if len(bubble.recent_scores) == 2 and all(score < 0.5 for score in bubble.recent_scores):
                dissolve.append(bubble_id)
                continue
            drop = False
            for topic_name in bubble.topics:
                topic = plan.topic_states.get(topic_name)
                if topic and topic.ef < 1.8:
                    drop = True
                    break
            if drop:
                dissolve.append(bubble_id)

        for bubble_id in dissolve:
            bubble = plan.bubbles.pop(bubble_id, None)
            if not bubble:
                continue
            for topic_name in bubble.topics:
                topic = plan.topic_states.get(topic_name)
                if topic and topic.bubble_id == bubble_id:
                    topic.bubble_id = None

        existing_sets = {tuple(sorted(bubble.topics)): bubble_id for bubble_id, bubble in plan.bubbles.items()}

        eligible_by_tag: Dict[str, List[TopicState]] = defaultdict(list)
        for topic in plan.topic_states.values():
            if topic.revision_count < 3:
                continue
            if topic.ef <= 2.0:
                continue
            if len(topic.performance_history) < 2:
                continue
            avg_last_two = sum(list(topic.performance_history)[-2:]) / 2.0
            if avg_last_two <= 0.7:
                continue
            threshold = max(3.0, days_until_exam * 0.15)
            if topic.interval <= threshold:
                continue
            if not topic.tags:
                continue
            primary_tag = topic.tags[0]
            eligible_by_tag[primary_tag].append(topic)

        for tag, topics in eligible_by_tag.items():
            if len(topics) < 2:
                continue
            selected = sorted(topics, key=lambda t: t.interval, reverse=True)[:BUBBLE_MAX_TOPICS]
            topic_names = tuple(sorted(topic.name for topic in selected))
            bubble_id = existing_sets.get(topic_names)

            if bubble_id and bubble_id in plan.bubbles:
                bubble = plan.bubbles[bubble_id]
                bubble.topics = list(topic_names)
                bubble.coherence_factor = 1.1
            else:
                bubble_id = uuid.uuid4().hex[:8]
                bubble = BubbleState(
                    bubble_id=bubble_id,
                    topics=list(topic_names),
                    coherence_factor=1.1,
                )
                plan.bubbles[bubble_id] = bubble

            for topic_name in topic_names:
                if topic_name in plan.topic_states:
                    plan.topic_states[topic_name].bubble_id = bubble.bubble_id

            compute_bubble_interval(
                bubble,
                [plan.topic_states[name] for name in bubble.topics if name in plan.topic_states],
                reference_date,
                days_until_exam,
            )


store = MemoryStore()
