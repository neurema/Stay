from __future__ import annotations

from fastapi import FastAPI, HTTPException

from .scheduler import store
from .schemas import ScheduleRequest, ScheduleResponse, ScheduleUpdate

app = FastAPI(
    title="Study Planner API",
    description="Generate adaptive study schedules informed by spaced repetition and active recall.",
    version="1.0.0",
)


@app.post("/schedule", response_model=ScheduleResponse)
def create_schedule(request: ScheduleRequest) -> ScheduleResponse:
    try:
        return store.create_plan(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.patch("/schedule/{schedule_id}", response_model=ScheduleResponse)
def update_schedule(schedule_id: str, update: ScheduleUpdate) -> ScheduleResponse:
    try:
        return store.update_plan(schedule_id, update)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/schedule/{schedule_id}", response_model=ScheduleResponse)
def get_schedule(schedule_id: str) -> ScheduleResponse:
    try:
        return store.get_plan(schedule_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
