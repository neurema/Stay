"""Self-checks reproducing the Stay Effective v5 worked example.

References: Section 6 Canonical Formulas, Section 7 Interval Mapping, Section 11
Worked Example in Stay_Effective_v5_Complete.md.
"""
from __future__ import annotations

import math
import unittest

from app.constants import WORKED_EXAMPLE
from app import formulas


class WorkedExampleTest(unittest.TestCase):
    """Ensure the deterministic formulas match Section 11 within 1%."""

    tolerance = 0.01

    def assertRelativeAlmostEqual(self, actual: float, expected: float, msg: str) -> None:
        if expected == 0.0:
            self.assertAlmostEqual(actual, expected, places=6, msg=msg)
            return
        rel_error = abs(actual - expected) / abs(expected)
        self.assertLessEqual(rel_error, self.tolerance, msg=f"{msg} rel_error={rel_error:.4f}")

    def test_pi(self) -> None:
        ex = WORKED_EXAMPLE
        pi = formulas.compute_pi(ex["ND"], ex["NS"], ex["Tmin"])
        self.assertRelativeAlmostEqual(pi, ex["PI"], "PI matches worked example")

    def test_crs(self) -> None:
        ex = WORKED_EXAMPLE
        crs = formulas.compute_crs_initial(ex["EF"], ex["PI"])
        self.assertRelativeAlmostEqual(crs, ex["CRS"], "CRS matches worked example")

    def test_alphaM(self) -> None:
        ex = WORKED_EXAMPLE
        alpha = formulas.compute_alphaM(ex["EF"])
        self.assertRelativeAlmostEqual(alpha, ex["alphaM"], "alphaM matches worked example")

    def test_i_eff(self) -> None:
        ex = WORKED_EXAMPLE
        i_base = ex["I_eff"] / (ex["CRS"] * ex["alphaM"])
        i_eff = formulas.compute_I_eff(i_base, ex["CRS"], ex["EF"])
        self.assertRelativeAlmostEqual(i_eff, ex["I_eff"], "I_eff matches worked example")

    def test_S_and_delta(self) -> None:
        ex = WORKED_EXAMPLE
        S, delta = formulas.compute_S_and_delta(ex["I_eff"])
        self.assertRelativeAlmostEqual(S, ex["S"], "S matches worked example")
        self.assertRelativeAlmostEqual(delta, ex["delta"], "delta matches worked example")
        self.assertGreater(S, 0.0)
        self.assertGreater(delta, 0.0)


if __name__ == "__main__":
    unittest.main()
