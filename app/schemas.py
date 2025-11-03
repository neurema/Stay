from __future__ import annotations

from datetime import date
from typing import Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, validator

StudyMode = Literal["Academic", "Effective", "Crunch"]


class TopicPerformance(BaseModel):
    score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    masteryLevel: Optional[Union[float, str]] = None


class TopicInput(BaseModel):
    name: str
    lastCovered: Optional[date] = None
    importance: Optional[int] = Field(default=None, ge=1, le=5)
    difficulty: Optional[Union[str, float, int]] = None


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
    topic: str
    date: date
    result: Union[str, float, int]
    notes: Optional[str] = None


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
    topic: str
    reviewMethod: str


class DaySchedule(BaseModel):
    date: date
    sessions: List[ReviewSession]


class ScheduleResponse(BaseModel):
    scheduleId: str
    schedule: List[DaySchedule]
