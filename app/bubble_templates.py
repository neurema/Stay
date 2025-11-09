"""Bubble schedule templates and configuration helpers.

Provides default bubble templates derived from revision indices and a loader
that can optionally pull overrides from a JSON file referenced by the
``STAY_BUBBLE_TEMPLATES_FILE`` environment variable.
"""
from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Dict, List

from .constants import HARD_BUBBLE_OFFSETS, SOFT_BUBBLE_OFFSETS, TOTAL_DAYS

logger = logging.getLogger(__name__)


def _normalize_template(days: Iterable[int], *, relative: bool) -> List[int]:
    normalized = sorted({int(day) for day in days})
    if relative:
        normalized = [day for day in normalized if day >= 0]
        if not normalized:
            raise ValueError("Relative bubble template must contain non-negative offsets")
    else:
        normalized = [day for day in normalized if 0 <= day <= TOTAL_DAYS]
        if not normalized:
            raise ValueError("Bubble template must contain at least one valid day within TOTAL_DAYS")
    return normalized


def _load_overrides(path: Path) -> Dict[str, Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Bubble template override file must contain a JSON object")

    overrides: Dict[str, Dict[str, Any]] = {}
    for key, value in data.items():
        if not isinstance(key, str):
            raise ValueError("Bubble template keys must be strings")
        relative = False
        raw_values: Iterable[int]
        if isinstance(value, dict):
            if "values" not in value:
                raise ValueError(f"Bubble template '{key}' must supply a 'values' field")
            raw_values = value["values"]
            relative = bool(value.get("relative", False))
        else:
            raw_values = value

        if not isinstance(raw_values, Iterable):
            raise ValueError(f"Bubble template '{key}' must map to an iterable of integers")

        overrides[key] = {
            "values": _normalize_template(raw_values, relative=relative),
            "relative": relative,
        }
    return overrides


def default_templates() -> Dict[str, Dict[str, Any]]:
    """Return the baked-in default bubble templates."""

    defaults: Dict[str, Dict[str, Any]] = {
        "default-soft": {"values": _normalize_template(SOFT_BUBBLE_OFFSETS, relative=True), "relative": True},
        "default-hard": {"values": _normalize_template(HARD_BUBBLE_OFFSETS, relative=True), "relative": True},
        "default-balanced": {"values": _normalize_template(SOFT_BUBBLE_OFFSETS, relative=True), "relative": True},
    }
    return defaults


def resolve_templates() -> Dict[str, Dict[str, Any]]:
    """Resolve bubble templates from environment overrides or defaults."""

    env_value = os.environ.get("STAY_BUBBLE_TEMPLATES_FILE")
    if not env_value:
        return default_templates()

    file_path = Path(env_value)
    if not file_path.exists():
        logger.warning(
            "Bubble template override file '%s' not found; falling back to defaults", file_path
        )
        return default_templates()

    try:
        overrides = _load_overrides(file_path)
    except Exception as exc:  # pragma: no cover - defensive logging path
        logger.error("Failed to load bubble template overrides from %s: %s", file_path, exc)
        return default_templates()

    logger.info("Loaded %d bubble templates from %s", len(overrides), file_path)
    return overrides


__all__ = ["resolve_templates", "default_templates"]
