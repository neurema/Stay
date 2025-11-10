"""Integration tests for FastAPI endpoints using httpx ASGI transport.

Avoids Starlette TestClient to sidestep environment-specific lifespan issues.
"""
from __future__ import annotations

import json
import unittest
from typing import Any, Dict

from app.main import app
from app import services
from app.bubble_templates import resolve_templates
from app.constants import MAX_BUBBLE_DAY, MAX_REVISIONS_DAY
import anyio
import httpx


class EndpointTest(unittest.TestCase):
    """Test endpoints with deterministic payloads, printing request/response bodies."""

    def setUp(self) -> None:
        self.app = app
        self.topic_id: str | None = None
        services.configure_bubble_templates(resolve_templates())

    def _print_request_response(self, method: str, url: str, request_body: Dict[str, Any], response: Any) -> None:
        """Helper to print request and response bodies for visibility."""
        print(f"\n--- {method.upper()} {url} ---")
        print("Request Body:")
        print(json.dumps(request_body, indent=2))
        print("Response Body:")
        print(json.dumps(response, indent=2))
        # response here is already JSON or a simple dict
        print("--- End ---\n")

    def test_health(self) -> None:
        """Test health endpoint."""
        async def run() -> None:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://testserver") as client:
                resp = await client.get("/health")
                self.assertEqual(resp.status_code, 200)
                self._print_request_response("GET", "/health", {}, resp.json())
        anyio.run(run)

    def test_create_topic(self) -> None:
        """Test topic creation with worked example inputs."""
        payload = {
            "subject_tag": "Test Topic",
            "difficulty": 0.5,
            "add_day": 1,
            "rt_ratio": 1.0,
            "accuracy": 0.8,
            "nd": 180,
            "ns": 50,
            "tmin_label": "Major",
        }
        async def run() -> None:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://testserver") as client:
                resp = await client.post("/topics/", json=payload)
                self.assertEqual(resp.status_code, 200)
                body = resp.json()
                self.assertIn("id", body)
                self.topic_id = body["id"]
                self._print_request_response("POST", "/topics/", payload, body)
        anyio.run(run)

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

        async def run() -> None:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://testserver") as client:
                resp = await client.post("/topics/bulk", json=payload)
                self.assertEqual(resp.status_code, 200)
                body = resp.json()
                self.assertIn("topics", body)
                topics = body["topics"]
                self.assertEqual(len(topics), 2)
                for item in topics:
                    self.assertIn("id", item)
                    self.assertTrue(item["schedule"], "schedule should not be empty")
                self._print_request_response("POST", "/topics/bulk", payload, body)

        anyio.run(run)

    def test_create_topic_with_bubble_template(self) -> None:
        """Ensure explicit bubble templates are honoured when provided."""

        services.register_bubble_template("bubble-test", [30, 45])

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
        async def run() -> None:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://testserver") as client:
                resp = await client.post("/topics/", json=payload)
                self.assertEqual(resp.status_code, 200)
                body = resp.json()
                self.assertIn(30, body["schedule"])
                self.assertIn(45, body["schedule"])
                self._print_request_response("POST", "/topics/", payload, body)
        anyio.run(run)

    def test_get_topic(self) -> None:
        """Test topic retrieval."""
        if not self.topic_id:
            self.test_create_topic()
        async def run() -> None:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://testserver") as client:
                resp = await client.get(f"/topics/{self.topic_id}")
                self.assertEqual(resp.status_code, 200)
                self._print_request_response("GET", f"/topics/{self.topic_id}", {}, resp.json())
        anyio.run(run)

    def test_execute_revision(self) -> None:
        """Test revision execution."""
        if not self.topic_id:
            self.test_create_topic()
        payload = {
            "topic_id": self.topic_id,
            "day": 1,
            "success": True,
        }
        async def run() -> None:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://testserver") as client:
                resp = await client.post("/revision/", json=payload)
                self.assertEqual(resp.status_code, 200)
                self._print_request_response("POST", "/revision/", payload, resp.json())
        anyio.run(run)

    def test_get_schedule(self) -> None:
        """Test schedule retrieval for a day."""
        async def run() -> None:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://testserver") as client:
                resp = await client.get("/revision/schedule/day/1")
                self.assertEqual(resp.status_code, 200)
                body = resp.json()
                self.assertIn("topics", body)
                self.assertIn("total_count", body)
                self.assertIn("capped_count", body)
                self.assertLessEqual(body["capped_count"], MAX_REVISIONS_DAY)
                self.assertLessEqual(body["bubble_capped_count"], MAX_BUBBLE_DAY)
                self._print_request_response("GET", "/revision/schedule/day/1", {}, body)
        anyio.run(run)


if __name__ == "__main__":
    unittest.main(verbosity=2)
