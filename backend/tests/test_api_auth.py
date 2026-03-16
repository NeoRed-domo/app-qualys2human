import pytest
from httpx import AsyncClient


@pytest.mark.asyncio(loop_scope="session")
async def test_auth_endpoints(client: AsyncClient):
    """Test health, login with seeded admin, and wrong password in one session."""
    # Health endpoint
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    # Login with seeded admin credentials
    response = await client.post("/api/auth/login", json={
        "username": "admin",
        "password": "Qualys2Human!",
        "domain": "local",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["profile"] == "admin"
    assert data["must_change_password"] is True
    assert "access_token" in data
    assert "refresh_token" in data

    # Wrong password
    response = await client.post("/api/auth/login", json={
        "username": "admin",
        "password": "wrong",
        "domain": "local",
    })
    assert response.status_code == 401

    # Non-existent user
    response = await client.post("/api/auth/login", json={
        "username": "nobody",
        "password": "test",
        "domain": "local",
    })
    assert response.status_code == 401
