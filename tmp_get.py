from fastapi.testclient import TestClient
from app.main import app
print('about to build client')
client = TestClient(app)
print('client ready, issuing request')
response = client.get('/health')
print('response received', response.status_code)
