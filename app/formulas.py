"""Deterministic Stay Effective v5 formula implementations.

References: Section 6 (EF/PI/CRS/S), Section 7 (Effective Interval Mapping), Section 11
Worked Example in Stay_Effective_v5_Complete.md.
"""
from __future__ import annotations

import math
from typing import Tuple

from .constants import (
    ALPHA_PI,
    BASE_INTERVALS,
    EF_MIN,
    GAMMA_CRS,
    KAPPA,
    P_NEXT,
    P_REF,
    SIGMOID_GAMMA,
    SIGMOID_MU,
    WORKED_EXAMPLE,
)


def clip(value: float, lo: float, hi: float) -> float:
    """Clamp *value* to [lo, hi] (Section 6.1)."""

    return max(lo, min(hi, value))


def update_ef(ef: float, success: bool) -> float:
    """SM-2 EF update per Section 6.2."""

    q = 5 if success else 1
    delta = 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)
    new_ef = ef + delta
    return max(EF_MIN, new_ef)


def compute_pi(nd: float, ns: float, t_min: float) -> float:
    """Compute PI using Section 6.3 definition."""

    if ns <= 0 or t_min <= 0:
        raise ValueError("NS and Tmin must be positive per Section 6.3")
    return math.log10(1.0 + nd / (ns * t_min))


def compute_crs_initial(ef: float, pi: float) -> float:
    """Initial CRS as in Section 6.4(A)."""

    return (ef * pi) / KAPPA


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def update_crs(crs_old: float, ef: float, pi: float) -> float:
    """Dynamic CRS mixing per Section 6.4(B)."""

    if ef <= 0:
        raise ValueError("EF must be positive to update CRS")
    logits = math.log(ef) + 2.0 * (pi - 0.5)
    target = _sigmoid(logits)
    return (1.0 - GAMMA_CRS) * crs_old + GAMMA_CRS * target


def compute_alphaM(ef: float) -> float:
    """Sigmoid modulation αM from Section 6.5."""

    return 0.5 + 1.0 / (1.0 + math.exp(-SIGMOID_GAMMA * (ef - SIGMOID_MU)))


def get_I_base(revision_count: int) -> int:
    """Base interval lookup from Section 7.1."""

    if revision_count < 0:
        raise ValueError("revision_count must be non-negative")
    if revision_count < len(BASE_INTERVALS):
        return BASE_INTERVALS[revision_count]
    return BASE_INTERVALS[-1]


def compute_I_eff(i_base: float, crs: float, ef: float) -> float:
    """Effective interval computation per Section 7 step 1."""

    if i_base < 0:
        raise ValueError("I_base must be non-negative")
    alpha_m = compute_alphaM(ef)
    return i_base * crs * alpha_m


def compute_S_and_delta(i_eff: float) -> Tuple[float, float]:
    """Map I_eff to S and delta (Section 7)."""

    if i_eff <= 0:
        raise ValueError("I_eff must be positive")
    S = -i_eff / math.log(P_REF)
    delta = -S * math.log(P_NEXT)
    return S, delta


# ---------------------------------------------------------------------------
# Inline Worked Example assertions (≤ 1 % relative error per prompt requirement)
# ---------------------------------------------------------------------------


def _assert_relative_close(name: str, value: float, expected: float, tolerance: float = 0.01) -> None:
    if expected == 0.0:
        if not math.isclose(value, expected, abs_tol=tolerance):
            raise AssertionError(f"{name} expected {expected} got {value}")
        return
    rel_error = abs(value - expected) / abs(expected)
    if rel_error > tolerance:
        raise AssertionError(f"{name} expected {expected} got {value} (rel err {rel_error:.4f})")


_EX = WORKED_EXAMPLE

_example_clip = clip(_EX["CRS"], 0.05, 0.95)
_assert_relative_close("clip(example CRS)", _example_clip, clip(_EX["CRS"], 0.05, 0.95))

_example_ef_success = update_ef(_EX["EF"], True)
_expected_ef_success = max(EF_MIN, _EX["EF"] + 0.1)
_assert_relative_close("update_ef(success)", _example_ef_success, _expected_ef_success)

_example_pi = compute_pi(_EX["ND"], _EX["NS"], _EX["Tmin"])
_assert_relative_close("compute_pi", _example_pi, _EX["PI"])

_example_crs = compute_crs_initial(_EX["EF"], _EX["PI"])
_assert_relative_close("compute_crs_initial", _example_crs, _EX["CRS"])

_example_crs_updated = update_crs(_EX["CRS"], _EX["EF"], _EX["PI"])
_expected_crs_update = (1.0 - GAMMA_CRS) * _EX["CRS"] + GAMMA_CRS * _sigmoid(math.log(_EX["EF"]) + 2.0 * (_EX["PI"] - 0.5))
_assert_relative_close("update_crs", _example_crs_updated, _expected_crs_update)

_example_alpha = compute_alphaM(_EX["EF"])
_assert_relative_close("compute_alphaM", _example_alpha, _EX["alphaM"])

_example_i_base = _EX["I_eff"] / (_EX["CRS"] * _example_alpha)
_assert_relative_close("example I_base derived", _example_i_base, 5.0)

_example_i_eff = compute_I_eff(_example_i_base, _EX["CRS"], _EX["EF"])
_assert_relative_close("compute_I_eff", _example_i_eff, _EX["I_eff"])

_example_S, _example_delta = compute_S_and_delta(_EX["I_eff"])
_assert_relative_close("compute_S", _example_S, _EX["S"])
_assert_relative_close("compute_delta", _example_delta, _EX["delta"])

_example_revision_index = min(range(len(BASE_INTERVALS)), key=lambda idx: abs(BASE_INTERVALS[idx] - _example_i_base))
_assert_relative_close(
    "get_I_base(example index)",
    float(get_I_base(_example_revision_index)),
    float(BASE_INTERVALS[_example_revision_index]),
    0.0,
)
