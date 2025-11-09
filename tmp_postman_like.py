import anyio
import httpx
import json
from app.main import app

async def show(client, method: str, url: str, json_body=None):
    print(f"\n--- {method} {url} ---")
    if json_body is not None:
        print("Request:")
        print(json.dumps(json_body, indent=2))
    resp = await client.request(method, url, json=json_body)
    print("Status:", resp.status_code)
    try:
        body = resp.json()
        print("Response:")
        print(json.dumps(body, indent=2))
    except Exception:
        print(resp.text)
    print("--- END ---\n")

async def main():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        # 1. Health
        await show(client, "GET", "/health")

        # 2. Create topic
        create_payload = {
            "subject_tag": "Smoke Topic",
            "difficulty": 0.6,
            "add_day": 1,
            "rt_ratio": 1.0,
            "accuracy": 0.85,
            "nd": 180,
            "ns": 50,
            "tmin_label": "Major"
        }
        resp = await client.post("/topics/", json=create_payload)
        topic = resp.json()
        print("\nCreated topic id:", topic["id"])  # quick peek
        # Re-print nicely using helper
        await show(client, "POST", "/topics/", json_body=create_payload)

        topic_id = topic["id"]

        # 3. Get topic
        await show(client, "GET", f"/topics/{topic_id}")

        # 4. Execute revision for day 1
        revision_payload = {"topic_id": topic_id, "day": 1, "success": True}
        await show(client, "POST", "/revision/", json_body=revision_payload)

        # 5. Fetch schedule for day 1
        await show(client, "GET", "/revision/schedule/day/1")

anyio.run(main)
