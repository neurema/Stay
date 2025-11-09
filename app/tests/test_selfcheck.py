"""Self-checks for the decay-based scheduling formulas."""
from __future__ import annotations

import unittest

from app.constants import WORKED_EXAMPLE
from app import formulas


class WorkedExampleTest(unittest.TestCase):
    """Ensure the decay model aligns with the abstract's worked values."""

    tolerance = 0.01

    def assertRelativeAlmostEqual(self, actual: float, expected: float, msg: str) -> None:
        if expected == 0.0:
            self.assertAlmostEqual(actual, expected, places=6, msg=msg)
            return
        rel_error = abs(actual - expected) / abs(expected)
        self.assertLessEqual(rel_error, self.tolerance, msg=f"{msg} rel_error={rel_error:.4f}")

    def test_recall_probability(self) -> None:
        ex = WORKED_EXAMPLE
        prob = formulas.recall_probability(ex["elapsed"], ex["forgetting_rate"])
        self.assertRelativeAlmostEqual(prob, ex["recall_probability"], "Recall probability matches worked example")

    def test_interval_for_threshold(self) -> None:
        ex = WORKED_EXAMPLE
        interval = formulas.interval_for_threshold(ex["forgetting_rate"], threshold=ex["threshold"])
        self.assertRelativeAlmostEqual(interval, ex["raw_interval"], "Base interval matches worked example")

    def test_short_horizon_scaling(self) -> None:
        ex = WORKED_EXAMPLE
        compressed = formulas.apply_short_horizon(ex["raw_interval"], ex["remaining_days"])
        self.assertRelativeAlmostEqual(
            compressed,
            ex["compressed_interval"],
            "Short-horizon compression matches worked example",
        )

    def test_difficulty_adjustment(self) -> None:
        ex = WORKED_EXAMPLE
        adjusted = formulas.apply_difficulty_focus(ex["compressed_interval"], ex["difficulty"], True)
        self.assertRelativeAlmostEqual(
            adjusted,
            ex["difficulty_interval"],
            "Difficulty multiplier matches worked example",
        )

    def test_full_interval(self) -> None:
        ex = WORKED_EXAMPLE
        full_interval = formulas.compute_interval(
            ex["forgetting_rate"],
            remaining_days=ex["remaining_days"],
            difficulty=ex["difficulty"],
            is_hard=True,
            threshold=ex["threshold"],
        )
        self.assertRelativeAlmostEqual(full_interval, ex["difficulty_interval"], "Full interval matches cascade")


if __name__ == "__main__":
    unittest.main()
