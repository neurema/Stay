import json
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
resp = client.get('/health')
print(resp.status_code)
print(json.dumps(resp.json(), indent=2))
