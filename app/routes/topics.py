"""Topic endpoints for Stay Effective v5 FastAPI app.

References: Section 2 Topic Structure, Section 3 Initialization from
Stay_Effective_v5_Complete.md.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status

from .. import models, services

router = APIRouter(prefix="/topics", tags=["topics"])


@router.post("/", response_model=models.Topic)
async def create_topic(payload: models.TopicCreate) -> models.Topic:
    """Create a new topic deterministically."""

    try:
        return services.create_topic(payload)
    except ValueError as exc:  # invalid Tmin label, etc.
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/bulk", response_model=models.TopicBulkCreateResponse)
async def create_topics_bulk(
    payload: models.TopicBulkCreateRequest,
) -> models.TopicBulkCreateResponse:
    """Create multiple topics deterministically in a single call."""

    try:
        topics = services.create_topics(payload.topics)
        return models.TopicBulkCreateResponse(topics=topics)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{topic_id}", response_model=models.Topic)
async def get_topic(topic_id: str) -> models.Topic:
    """Fetch a topic by identifier."""

    try:
        return services.get_topic(topic_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/bubbles", status_code=status.HTTP_204_NO_CONTENT)
async def register_bubble(payload: models.BubbleTemplatePayload) -> Response:
    """Register or overwrite a bubble template used for scheduling."""

    services.register_bubble_template(
        payload.bubble_id.strip(),
        payload.values,
        relative=payload.relative,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
