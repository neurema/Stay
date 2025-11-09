import anyio
import httpx
from app.main import app

async def main():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        # health
        r = await client.get("/health")
        print('health', r.status_code, r.json())
        # create topic
        payload = {
            "subject_tag": "Smoke Topic",
            "difficulty": 0.6,
            "add_day": 1,
            "rt_ratio": 1.0,
            "accuracy": 0.85,
            "nd": 180,
            "ns": 50,
            "tmin_label": "Major",
        }
        r = await client.post("/topics/", json=payload)
        print('create', r.status_code)
        body = r.json()
        print('keys', sorted(body.keys()))
        topic_id = body["id"]
        # execute revision
        r = await client.post("/revision/", json={"topic_id": topic_id, "day": 1, "success": True})
        print('rev', r.status_code)
        rev_body = r.json()
        print('next-day', rev_body["history"][-1][-1])
        # schedule/day
        r = await client.get("/revision/schedule/day/1")
        print('sched', r.status_code, list(r.json().keys()))

anyio.run(main)
