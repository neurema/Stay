"""API-driven cohort schedule test for a 900-topic, nine-month plan.

Creates topics via FastAPI endpoints, registers 100 bubble-enhanced topics, and
plots the resulting revision load per day over the full planning horizon.
"""
from __future__ import annotations

import csv
import random
import unittest
from pathlib import Path
from typing import List

import anyio
import httpx

from app.constants import MAX_BUBBLE_DAY, MAX_REVISIONS_DAY, TOTAL_DAYS
from app.main import app
from app import services
from app.bubble_templates import resolve_templates
from app.scheduler import DeterministicScheduler


class CohortRevisionLoadAPITest(unittest.TestCase):
    """Validate API topic creation and aggregate revision load graph."""

    TOPIC_COUNT = 900
    BUBBLE_COUNT = 100
    ADD_WINDOW = 220
    GRAPH_DIR = Path(__file__).parent / "artifacts"
    GRAPH_NAME = "api_revision_vs_day.png"
    SEED = int(__import__("time").time())
    BUBBLE_ID = "api-cohort-bubble"
    BUBBLE_DAYS = (240, 255)

    def setUp(self) -> None:
        self._reset_services()

    def _reset_services(self) -> None:
        services._topics.clear()  # type: ignore[attr-defined]
        services._scheduler = DeterministicScheduler()  # type: ignore[attr-defined]
        services.configure_bubble_templates(resolve_templates())
        services.register_bubble_template(self.BUBBLE_ID, self.BUBBLE_DAYS)

    def test_api_cohort_revision_graph(self) -> None:
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:  # pragma: no cover - optional dependency
            self.skipTest("matplotlib is required to generate the graph")

        rng = random.Random(self.SEED)
        self.GRAPH_DIR.mkdir(parents=True, exist_ok=True)

        bubble_indices = set(rng.sample(range(self.TOPIC_COUNT), self.BUBBLE_COUNT))
        bubble_topic_ids = set()
        created_topic_ids: List[str] = []
        add_days: List[int] = []

        async def create_all() -> None:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
                for topic_idx in range(self.TOPIC_COUNT):
                    add_day = rng.randint(0, self.ADD_WINDOW)
                    payload = {
                        "subject_tag": f"Topic {topic_idx:03d}",
                        "difficulty": round(rng.betavariate(2.0, 3.0), 3),
                        "add_day": add_day,
                        "rt_ratio": round(rng.uniform(0.8, 1.2), 2),
                        "accuracy": round(rng.uniform(0.7, 0.95), 2),
                        "nd": 270,
                        "ns": 90,
                        "tmin_label": "Major",
                    }
                    if topic_idx in bubble_indices:
                        payload["bubble_id"] = self.BUBBLE_ID

                    response = await client.post("/topics/", json=payload)
                    self.assertEqual(response.status_code, 200)
                    body = response.json()
                    created_topic_ids.append(body["id"])
                    add_days.append(body["add_day"])

                    if topic_idx in bubble_indices:
                        bubble_topic_ids.add(body["id"])
                        self.assertTrue(
                            all(day in body["schedule"] for day in self.BUBBLE_DAYS),
                            "Bubble topics should include registered bubble days",
                        )
        anyio.run(create_all)

        self.assertEqual(len(created_topic_ids), self.TOPIC_COUNT)
        self.assertEqual(len(bubble_topic_ids), self.BUBBLE_COUNT)
        self.assertLessEqual(max(add_days), self.ADD_WINDOW)

        days = list(range(TOTAL_DAYS + 1))
        total_counts: List[int] = []
        bubble_counts: List[int] = []
        single_counts: List[int] = []

        async def fetch_days() -> None:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
                for day in days:
                    response = await client.get(f"/revision/schedule/day/{day}")
                    self.assertEqual(response.status_code, 200)
                    summary = response.json()
                    topics_for_day = summary["topics"]
                    total_counts.append(summary["capped_count"])
                    bubble_counts.append(summary["bubble_capped_count"])
                    self.assertEqual(len(topics_for_day), summary["capped_count"])
                    single_capped = summary["capped_count"] - summary["bubble_capped_count"]
                    self.assertGreaterEqual(single_capped, 0)
                    single_counts.append(single_capped)
                    self.assertLessEqual(summary["capped_count"], MAX_REVISIONS_DAY)
                    self.assertLessEqual(summary["bubble_capped_count"], MAX_BUBBLE_DAY)
                    self.assertGreaterEqual(summary["total_count"], summary["capped_count"])
                    self.assertGreaterEqual(summary["bubble_total_count"], summary["bubble_capped_count"])
        anyio.run(fetch_days)

        self.assertGreater(sum(total_counts), 0)
        self.assertTrue(any(value > 0 for value in single_counts))

        fig, ax = plt.subplots(figsize=(11, 4))
        ax.plot(days, total_counts, label="Total revisions", color="#3b6fb6", linewidth=1.5)
        ax.plot(days, bubble_counts, label="Bubble topics", color="#e07a5f", linewidth=1.2)
        ax.set_title("API Cohort: Daily Revision Load")
        ax.set_xlabel("Day")
        ax.set_ylabel("Revisions")
        ax.set_xlim(0, TOTAL_DAYS)
        ax.legend(loc="upper right")
        ax.grid(alpha=0.25)
        fig.tight_layout()

        graph_path = self.GRAPH_DIR / self.GRAPH_NAME
        fig.savefig(graph_path, dpi=150)
        plt.close(fig)

        self.assertTrue(graph_path.exists())
        self.assertGreater(graph_path.stat().st_size, 0)

        csv_path = self.GRAPH_DIR / "api_revision_vs_day.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["day", "total_revisions", "bubble_revisions", "single_revisions"])
            for day_value, total, bubble, single in zip(days, total_counts, bubble_counts, single_counts):
                writer.writerow([day_value, total, bubble, single])

        self.assertTrue(csv_path.exists())
        self.assertGreater(csv_path.stat().st_size, 0)

        schedule_csv_path = self.GRAPH_DIR / "api_topic_schedule.csv"
        services.export_topic_schedule_csv(schedule_csv_path)
        self.assertTrue(schedule_csv_path.exists())
        self.assertGreater(schedule_csv_path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
