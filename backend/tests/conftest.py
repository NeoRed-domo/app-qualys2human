import pytest
from httpx import AsyncClient, ASGITransport
from q2h.main import app


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
async def client():
    """Session-scoped ASGI client — single lifespan for all API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture(scope="session")
async def admin_token(client: AsyncClient) -> str:
    """Login as admin once and return the access token for the session."""
    resp = await client.post("/api/auth/login", json={
        "username": "admin",
        "password": "Qualys2Human!",
        "domain": "local",
    })
    assert resp.status_code == 200
    return resp.json()["access_token"]
