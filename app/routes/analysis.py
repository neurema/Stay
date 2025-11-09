"""Analysis endpoints exposing Monte Carlo simulations for Stay Effective v5.

References: Section 11 Adaptive Analysis addendum in Stay_Effective_v5_Complete.md.
"""
from __future__ import annotations

from fastapi import APIRouter

from .. import models, services

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/monte-carlo", response_model=models.MonteCarloBatchResponse)
async def run_monte_carlo(request: models.MonteCarloRequest) -> models.MonteCarloBatchResponse:
    """Run one or more Monte Carlo scenarios and return their aggregated results."""

    return services.run_monte_carlo_batch(request)
