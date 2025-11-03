from datetime import date
from pathlib import Path
import sys
import types

# Ensure repository root is on sys.path
sys.path.append(str(Path(__file__).resolve().parents[1]))


# Provide lightweight stand-ins for third-party dependencies that are unavailable

pydantic_stub = types.ModuleType("pydantic")


class FieldInfo:
    def __init__(self, default=None, **kwargs):
        self.default = default
        self.metadata = kwargs


def Field(*, default=None, **kwargs):
    return FieldInfo(default=default, **kwargs)


class BaseModelMeta(type):
    def __new__(mcls, name, bases, namespace):
        validators = []
        for attr_name, attr_value in namespace.items():
            fields = getattr(attr_value, "__validator_fields__", None)
            if fields:
                validators.append((fields, attr_value))
        namespace.setdefault("__validators__", validators)
        return super().__new__(mcls, name, bases, namespace)


class BaseModel(metaclass=BaseModelMeta):
    __validators__ = []

    def __init__(self, **data):
        annotations = getattr(self, "__annotations__", {})
        for key in data.keys():
            if key not in annotations:
                raise TypeError(f"Unexpected field '{key}' for {self.__class__.__name__}")
        for field in annotations:
            value = self._resolve_value(field, data)
            setattr(self, field, value)
        for fields, validator in self.__validators__:
            values = [getattr(self, field) for field in fields]
            result = validator(self.__class__, *values)
            if len(fields) == 1:
                setattr(self, fields[0], result)
        self.__post_init__()

    def _resolve_value(self, field, data):
        if field in data:
            return data[field]
        default = getattr(self.__class__, field, None)
        if isinstance(default, FieldInfo):
            return default.default
        return default

    def __post_init__(self):
        pass

    def dict(self):
        annotations = getattr(self, "__annotations__", {})
        return {field: getattr(self, field) for field in annotations}

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.dict() == other.dict()


def validator(*fields):
    def decorator(func):
        func.__validator_fields__ = fields
        return func

    return decorator


pydantic_stub.BaseModel = BaseModel
pydantic_stub.Field = Field
pydantic_stub.validator = validator
sys.modules.setdefault("pydantic", pydantic_stub)

import pytest

from app.scheduler import MemoryStore
from app.schemas import (
    CompletedSession,
    ScheduleRequest,
    ScheduleUpdate,
    TopicInput,
    TopicPerformance,
)


@pytest.fixture
def store() -> MemoryStore:
    return MemoryStore()


def test_create_plan_generates_academic_schedule(store: MemoryStore) -> None:
    request = ScheduleRequest(
        mode="Academic",
        examDate=date(2025, 11, 30),
        startDate=date(2025, 11, 1),
        topics=[
            TopicInput(name="Biology Basics", lastCovered=date(2025, 10, 28), importance=4)
        ],
    )

    response = store.create_plan(request)

    assert response.scheduleId
    assert response.schedule
    first_day = response.schedule[0]
    assert first_day.date == date(2025, 11, 2)
    assert first_day.sessions[0].topic == "Biology Basics"
    assert first_day.sessions[0].reviewMethod == "summarize"


def test_update_plan_schedules_follow_up_for_failures(store: MemoryStore) -> None:
    request = ScheduleRequest(
        mode="Effective",
        examDate=date(2025, 12, 1),
        startDate=date(2025, 11, 1),
        topics=[TopicInput(name="Organic Chemistry", importance=5, difficulty="hard")],
    )
    created = store.create_plan(request)

    update = ScheduleUpdate(
        completedSessions=[
            CompletedSession(topic="Organic Chemistry", date=date(2025, 11, 4), result="failure")
        ]
    )

    updated = store.update_plan(created.scheduleId, update)

    target_dates = [
        day.date
        for day in updated.schedule
        for session in day.sessions
        if session.topic == "Organic Chemistry" and day.date >= date(2025, 11, 4)
    ]

    assert target_dates, "Expected follow-up sessions for the failed topic"
    assert min(target_dates) <= date(2025, 11, 6)


def test_get_plan_returns_latest_schedule(store: MemoryStore) -> None:
    request = ScheduleRequest(
        mode="Crunch",
        examDate=date(2025, 11, 20),
        startDate=date(2025, 11, 1),
        topics=[
            TopicInput(name="Calculus", importance=5),
            TopicInput(name="Physics", importance=4),
        ],
        pastPerformance={"Calculus": TopicPerformance(score=0.9)},
    )
    created = store.create_plan(request)

    fetched = store.get_plan(created.scheduleId)

    assert fetched.scheduleId == created.scheduleId
    assert fetched.schedule == created.schedule
