from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as client:
    response = client.get('/health')
    print(response.status_code)
