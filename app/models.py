"""Pydantic models encapsulating the Stay Effective v5 topic schema.

References: Section 2 Topic Structure, Section 3 Initialization, Section 8 Revision Execution
from Stay_Effective_v5_Complete.md.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


class TopicCreate(BaseModel):
    """Incoming payload for creating a topic (Sections 2 & 3)."""

    subject_tag: str = Field(..., description="Taxonomy label for the topic")
    difficulty: float = Field(..., ge=0.0, le=1.0, description="Normalized difficulty ∈ [0,1]")
    add_day: int = Field(..., ge=0, description="Day the topic is introduced")
    rt_ratio: float = Field(..., gt=0.0, description="Time ratio TE/TT for RT index (Section 10a)")
    accuracy: float = Field(..., ge=0.0, le=1.0, description="Accuracy fraction for AS index (Section 10b)")
    nd: int = Field(..., gt=0, description="Days until target exam (Section 6.3)")
    ns: int = Field(..., gt=0, description="Available sessions count (Section 6.3)")
    tmin_label: str = Field(
        "Major",
        description="Key into Tmin defaults (Section 6.3)",
    )
    tmin_override: Optional[float] = Field(
        None,
        gt=0.0,
        description="Optional Tmin override in days (Section 6.3)",
    )
    initial_pi: Optional[float] = Field(
        None,
        gt=0.0,
        description="Optional explicit PI to use instead of computed value (Section 6.3)",
    )
    bubble_id: Optional[str] = Field(
        None,
        description="Optional identifier for tying the topic to a precomputed bubble",
    )


class Topic(BaseModel):
    """Persisted topic state exposed through the API (Sections 2 & 8)."""

    id: str
    subject_tag: str
    difficulty: float
    accuracy: float
    rt_ratio: float
    add_day: int
    bubble_id: Optional[str]
    is_hard: bool
    base_ef: float
    ef: float
    pi: float
    crs: float
    nd: int
    ns: int
    tmin: float
    schedule: List[int]
    revision_count: int
    history: List[Tuple[int, bool, float, float, float, Optional[int]]]


class SessionResult(BaseModel):
    """Payload for executing a revision session (Section 8)."""

    topic_id: str = Field(..., description="Identifier of the topic to revise")
    day: int = Field(..., ge=0, description="Current deterministic day")
    success: bool = Field(..., description="Deterministic success outcome")
    nd: Optional[int] = Field(None, gt=0, description="Optional updated ND for PI recompute")
    ns: Optional[int] = Field(None, gt=0, description="Optional updated NS for PI recompute")
    tmin_label: Optional[str] = Field(
        None,
        description="Optional Tmin key for recompute",
    )
    tmin_override: Optional[float] = Field(
        None,
        gt=0.0,
        description="Optional Tmin override when recomputing PI",
    )
    accuracy: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Optional updated accuracy fraction",
    )
    rt_ratio: Optional[float] = Field(
        None,
        gt=0.0,
        description="Optional updated time ratio (TE/TT) for RT index",
    )
    difficulty: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Optional updated difficulty score",
    )


class MonteCarloScenario(BaseModel):
    """Configuration for a single Monte Carlo analysis scenario."""

    label: Optional[str] = Field(
        None,
        description="Human readable label that will tag the scenario output",
    )
    topic_count: int = Field(..., gt=0, description="Number of topics in the simulated cohort")
    bubble_count: Optional[int] = Field(
        None,
        ge=0,
        description="Optional number of hardest topics that receive bubble priority",
    )
    trials: Optional[int] = Field(
        None,
        gt=0,
        description="Override for the number of Monte Carlo trials for this scenario",
    )
    csv_name: Optional[str] = Field(
        None,
        description="Optional custom filename for persisted trial data",
    )


class MonteCarloRequest(BaseModel):
    """Batch Monte Carlo analysis request payload."""

    scenarios: List[MonteCarloScenario] = Field(
        ..., min_items=1, description="Collection of scenarios to evaluate"
    )
    default_trials: Optional[int] = Field(
        None,
        gt=0,
        description="Fallback number of trials when a scenario omits the override",
    )
    return_trial_records: bool = Field(
        False,
        description="Return the full set of trial records in the response",
    )
    save_csv: bool = Field(False, description="Persist raw trial data to CSV on disk")
    disable_progress: bool = Field(
        True,
        description="Disable tqdm progress bars when running inside the API",
    )
    output_dir: Optional[str] = Field(
        None,
        description="Optional override directory for CSV outputs; defaults to working directory",
    )


class MonteCarloScenarioResult(BaseModel):
    """Serialized response payload for a single scenario."""

    label: str
    topic_count: int
    bubble_count: Optional[int]
    trial_count: int
    summary: Dict[str, Dict[str, float]]
    csv_path: Optional[str] = None
    trial_records: Optional[List[Dict[str, float]]] = None


class MonteCarloBatchResponse(BaseModel):
    """Response wrapper for batch Monte Carlo analysis."""

    scenarios: List[MonteCarloScenarioResult]
