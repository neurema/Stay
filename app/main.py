"""FastAPI application entrypoint for Stay Effective v5 backend.

References: Section 2 Topic Structure, Section 8 Revision Execution, Section 9
Scheduler integration in Stay_Effective_v5_Complete.md.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI

from . import services
from .bubble_templates import resolve_templates
from .routes import analysis, revision, topics

logger = logging.getLogger(__name__)

app = FastAPI(title="Stay Effective v5", version="5.0.0")
app.include_router(topics.router)
app.include_router(revision.router)
app.include_router(analysis.router)

services.configure_bubble_templates(resolve_templates())

logger.info("Stay Effective v5 deterministic backend initialized per specification")


@app.get("/health", tags=["health"])
async def health() -> dict:
    """Simple health endpoint exposing spec version."""

    return {"status": "ok", "spec": "Stay Effective v5"}
