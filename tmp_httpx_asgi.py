import httpx
from app.main import app

transport = httpx.ASGITransport(app=app)
with httpx.Client(transport=transport, base_url="http://testserver") as client:
    r = client.get("/health")
    print(r.status_code)
    print(r.json())
