import anyio, httpx, json
from app.main import app

def show(title, data):
    print(f"\n=== {title} ===")
    print(json.dumps(data, indent=2))

async def main():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        # Health
        r = await client.get('/health')
        show('GET /health', r.json())

        # Create topic
        payload = {
            "subject_tag": "Postman Demo",
            "difficulty": 0.4,
            "add_day": 2,
            "rt_ratio": 1.0,
            "accuracy": 0.9,
            "nd": 240,
            "ns": 80,
            "tmin_label": "Major"
        }
        r = await client.post('/topics/', json=payload)
        body = r.json()
        topic_id = body['id']
        trimmed = {
            k: body[k] for k in (
                'id','subject_tag','is_hard','base_ef','ef','pi','crs','revision_count'
            )
        }
        trimmed['schedule_head'] = body['schedule'][:10]
        trimmed['history_last'] = body['history'][-1] if body['history'] else None
        show('POST /topics/', trimmed)

        # Revision
        r = await client.post('/revision/', json={"topic_id": topic_id, "day": 2, "success": True})
        b2 = r.json()
        t2 = {
            'id': b2['id'],
            'ef': b2['ef'],
            'pi': b2['pi'],
            'crs': b2['crs'],
            'revision_count': b2['revision_count'],
            'history_last': b2['history'][-1]
        }
        show('POST /revision/', t2)

        # Schedule day 2
        r = await client.get('/revision/schedule/day/2')
        show('GET /revision/schedule/day/2', r.json())

anyio.run(main)
