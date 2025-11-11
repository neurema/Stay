"""Integration tests for Stay Effective v5 FastAPI endpoints.

Uses FastAPI TestClient to test endpoints deterministically, outputting request/response bodies.
References: Section 8 Revision Execution, Section 11 Worked Example from Stay_Effective_v5_Complete.md.
"""
from __future__ import annotations

import json
import unittest
from typing import Any, Dict

from fastapi.testclient import TestClient

from app.main import app
from app import services
from app.bubble_templates import resolve_templates
from app.constants import MAX_BUBBLE_DAY, MAX_REVISIONS_DAY, WORKED_EXAMPLE


class EndpointTest(unittest.TestCase):
    """Test endpoints with deterministic payloads, printing request/response bodies."""

    def setUp(self) -> None:
        self.client = TestClient(app)
        self.topic_id: str | None = None
        services.configure_bubble_templates(resolve_templates())

    def _print_request_response(self, method: str, url: str, request_body: Dict[str, Any], response: Any) -> None:
        """Helper to print request and response bodies for visibility."""
        print(f"\n--- {method.upper()} {url} ---")
        print("Request Body:")
        print(json.dumps(request_body, indent=2))
        print("Response Body:")
        print(json.dumps(response.json(), indent=2))
        print("Status Code:", response.status_code)
        print("--- End ---\n")

    def test_health(self) -> None:
        """Test health endpoint."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self._print_request_response("GET", "/health", {}, response)

    def test_create_topic(self) -> None:
        """Test topic creation with worked example inputs."""
        ex = WORKED_EXAMPLE
        payload = {
            "subject_tag": "Test Topic",
            "difficulty": 0.5,  # arbitrary, not directly from example
            "add_day": 1,
            "rt_ratio": 1.0,  # RT=1.1 from example, but ratio approx
            "accuracy": 0.8,  # AS=1.1, accuracy approx
            "nd": int(ex["ND"]),
            "ns": int(ex["NS"]),
            "tmin_label": "Major",  # Tmin=0.10
        }
        response = self.client.post("/topics/", json=payload)
        self.assertEqual(response.status_code, 200)  # FastAPI default for POST
        self.assertIn("id", response.json())
        self.topic_id = response.json()["id"]  # store for later tests
        self._print_request_response("POST", "/topics/", payload, response)

    def test_bulk_create_topics(self) -> None:
        """Ensure bulk topic creation returns ordered schedules."""

        payload = {
            "topics": [
                {
                    "subject_tag": "Bulk Topic A",
                    "difficulty": 0.55,
                    "add_day": 0,
                    "rt_ratio": 1.0,
                    "accuracy": 0.9,
                    "nd": 180,
                    "ns": 96,
                    "tmin_label": "Major",
                },
                {
                    "subject_tag": "Bulk Topic B",
                    "difficulty": 0.75,
                    "add_day": 0,
                    "rt_ratio": 1.2,
                    "accuracy": 0.8,
                    "nd": 200,
                    "ns": 120,
                    "tmin_label": "Major",
                },
            ]
        }

        response = self.client.post("/topics/bulk", json=payload)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("topics", body)
        topics = body["topics"]
        self.assertEqual(len(topics), 2)
        for item in topics:
            self.assertIn("id", item)
            self.assertTrue(item["schedule"], "schedule should not be empty")

        self._print_request_response("POST", "/topics/bulk", payload, response)

    def test_create_topic_with_bubble_template(self) -> None:
        """Ensure explicit bubble templates are honoured when provided."""

        services.register_bubble_template("bubble-test", [250, 265])

        payload = {
            "subject_tag": "Bubble Topic",
            "difficulty": 0.4,
            "add_day": 10,
            "rt_ratio": 1.0,
            "accuracy": 0.85,
            "nd": 200,
            "ns": 60,
            "tmin_label": "Major",
            "bubble_id": "bubble-test",
        }
        response = self.client.post("/topics/", json=payload)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn(250, body["schedule"])
        self.assertIn(265, body["schedule"])
        self._print_request_response("POST", "/topics/", payload, response)

    def test_schedule_respects_exam_day(self) -> None:
        """Ensure schedules do not extend beyond the declared exam day."""

        payload = {
            "subject_tag": "Exam Bound Topic",
            "difficulty": 0.5,
            "add_day": 0,
            "rt_ratio": 1.0,
            "accuracy": 0.85,
            "nd": 30,
            "ns": 40,
            "tmin_label": "Major",
        }
        response = self.client.post("/topics/", json=payload)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        exam_day = payload["add_day"] + payload["nd"]
        self.assertTrue(body["schedule"], "schedule should include at least one planned day")
        self.assertTrue(all(day < exam_day for day in body["schedule"]))

        topic_id = body["id"]
        revision_day = next((day for day in body["schedule"] if day > payload["add_day"]), body["schedule"][-1])
        revision_payload = {
            "topic_id": topic_id,
            "day": revision_day,
            "success": True,
            "nd": 5,
        }
        revision_response = self.client.post("/revision/", json=revision_payload)
        self.assertEqual(revision_response.status_code, 200)
        updated = revision_response.json()
        new_exam_day = revision_day + revision_payload["nd"]
        if updated["schedule"]:
            self.assertTrue(all(day < new_exam_day for day in updated["schedule"]))
            self.assertTrue(all(day > revision_day for day in updated["schedule"]))

    def test_get_topic(self) -> None:
        """Test topic retrieval."""
        if not self.topic_id:
            self.test_create_topic()  # ensure topic exists
        response = self.client.get(f"/topics/{self.topic_id}")
        self.assertEqual(response.status_code, 200)
        self._print_request_response("GET", f"/topics/{self.topic_id}", {}, response)

    def test_execute_revision(self) -> None:
        """Test revision execution."""
        if not self.topic_id:
            self.test_create_topic()  # ensure topic exists
        payload = {
            "topic_id": self.topic_id,
            "day": 1,
            "success": True,
        }
        response = self.client.post("/revision/", json=payload)
        self.assertEqual(response.status_code, 200)
        self._print_request_response("POST", "/revision/", payload, response)

    def test_get_schedule(self) -> None:
        """Test schedule retrieval for a day."""
        response = self.client.get("/revision/schedule/day/1")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("topics", body)
        self.assertIn("total_count", body)
        self.assertIn("capped_count", body)
        self.assertLessEqual(body["capped_count"], MAX_REVISIONS_DAY)
        self.assertLessEqual(body["bubble_capped_count"], MAX_BUBBLE_DAY)
        self._print_request_response("GET", "/revision/schedule/day/1", {}, response)


if __name__ == "__main__":
    unittest.main(verbosity=2)