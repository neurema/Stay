import threading
import faulthandler
from fastapi.testclient import TestClient
from app.main import app

def dump():
    print('--- stack dump ---', flush=True)
    faulthandler.dump_traceback()

t = threading.Timer(5.0, dump)
t.daemon = True
t.start()
client = TestClient(app)
response = client.get('/health')
print(response.status_code)
