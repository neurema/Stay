from __future__ import annotations

from datetime import date
from typing import Dict, List, Literal, Optional, Sequence, Union

from pydantic import BaseModel, Field, validator

StudyMode = Literal["Academic", "Effective", "Crunch"]
ConfidenceLevel = Literal["Easy", "Medium", "Hard"]
SessionType = Literal["individual", "bubble"]


class TopicPerformance(BaseModel):
    score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    masteryLevel: Optional[Union[float, str]] = None


class TopicInput(BaseModel):
    name: str
    lastCovered: Optional[date] = None
    importance: Optional[int] = Field(default=None, ge=1, le=5)
    difficulty: Optional[Union[str, float, int]] = None
    tags: Optional[List[str]] = None


class ScheduleRequest(BaseModel):
    mode: StudyMode
    examDate: date
    topics: List[Union[str, TopicInput]]
    pastPerformance: Optional[Dict[str, TopicPerformance]] = None
    startDate: Optional[date] = None

    @validator("topics")
    def ensure_topics(cls, value: List[Union[str, TopicInput]]) -> List[Union[str, TopicInput]]:
        if not value:
            raise ValueError("At least one topic must be provided")
        return value


class CompletedSession(BaseModel):
    sessionType: SessionType
    date: date
    topic: Optional[str] = None
    bubbleId: Optional[str] = None
    mcqScore: float = Field(ge=0.0, le=1.0)
    confidence: ConfidenceLevel
    plannedMinutes: int = Field(ge=1)
    actualMinutes: int = Field(ge=1)
    interleavingScore: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    topicsCovered: Optional[Sequence["TopicContribution"]] = None
    notes: Optional[str] = None

    @validator("topic", always=True)
    def ensure_topic_for_individual(
        cls, value: Optional[str], values: Optional[Dict[str, object]] = None, **kwargs
    ) -> Optional[str]:
        if values and values.get("sessionType") == "individual" and not value:
            raise ValueError("Individual sessions must specify a topic")
        return value

    @validator("topicsCovered", always=True)
    def ensure_topics_for_bubble(
        cls, value: Optional[Sequence["TopicContribution"]], values: Optional[Dict[str, object]] = None, **kwargs
    ) -> Optional[Sequence["TopicContribution"]]:
        if values and values.get("sessionType") == "bubble":
            if not values.get("bubbleId"):
                raise ValueError("Bubble sessions must include a bubbleId")
            if not value:
                raise ValueError("Bubble sessions must include topicsCovered")
        return value

    def __post_init__(self) -> None:
        session_type = getattr(self, "sessionType", None)
        if session_type == "individual" and not getattr(self, "topic", None):
            raise ValueError("Individual sessions must specify a topic")
        if session_type == "bubble":
            if not getattr(self, "bubbleId", None):
                raise ValueError("Bubble sessions must include a bubbleId")
            if not getattr(self, "topicsCovered", None):
                raise ValueError("Bubble sessions must include topicsCovered")


class TopicContribution(BaseModel):
    topic: str
    correct: int = Field(ge=0)
    total: int = Field(gt=0)


class AvailabilityChanges(BaseModel):
    noStudyDays: Optional[List[date]] = None
    maxSessionsPerDay: Optional[int] = Field(default=None, ge=1)


class ScheduleUpdate(BaseModel):
    completedSessions: List[CompletedSession]
    newTopics: Optional[List[Union[str, TopicInput]]] = None
    availabilityChanges: Optional[AvailabilityChanges] = None

    @validator("completedSessions")
    def ensure_sessions(cls, value: List[CompletedSession]) -> List[CompletedSession]:
        if not value:
            raise ValueError("At least one completed session must be provided")
        return value


class ReviewSession(BaseModel):
    sessionType: SessionType
    reviewMethod: str
    topic: Optional[str] = None
    bubbleId: Optional[str] = None
    topics: Optional[List[str]] = None


class DaySchedule(BaseModel):
    date: date
    sessions: List[ReviewSession]


class ScheduleResponse(BaseModel):
    scheduleId: str
    schedule: List[DaySchedule]
    alerts: Optional[List[str]] = None
