"""Revision endpoints for Stay Effective v5 FastAPI app.

References: Section 8 Revision Execution, Section 9 Scheduler in
Stay_Effective_v5_Complete.md.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import models, services

router = APIRouter(prefix="/revision", tags=["revision"])


@router.post("/", response_model=models.Topic)
async def execute_revision(payload: models.SessionResult) -> models.Topic:
    """Execute a deterministic revision session."""

    try:
        return services.execute_revision(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/schedule/day/{day}")
async def get_schedule(day: int) -> dict:
    """Retrieve scheduled topics for a given day (Section 9)."""

    try:
        summary = services.get_schedule_for_day(day)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return summary
