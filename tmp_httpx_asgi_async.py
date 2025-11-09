import anyio
import httpx
from app.main import app

async def main():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        r = await client.get("/health")
        print(r.status_code)
        print(r.json())

anyio.run(main)
