import pytest
from httpx import AsyncClient


@pytest.mark.asyncio(loop_scope="session")
async def test_enterprise_presets(client: AsyncClient, admin_token: str):
    """Test enterprise preset endpoints (admin only)."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    # GET enterprise rules — should return defaults
    resp = await client.get("/api/presets/enterprise", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "severities" in data
    assert "types" in data

    # PUT enterprise rules — admin updates
    resp = await client.put("/api/presets/enterprise", headers=headers, json={
        "severities": [3, 4, 5],
        "types": ["Vulnerability"],
        "name": "High severity only",
    })
    assert resp.status_code == 200

    # Verify the update persisted
    resp = await client.get("/api/presets/enterprise", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["severities"] == [3, 4, 5]
    assert data["types"] == ["Vulnerability"]


@pytest.mark.asyncio(loop_scope="session")
async def test_user_presets(client: AsyncClient, admin_token: str):
    """Test user preset CRUD."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Initially no user presets
    resp = await client.get("/api/presets/user", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

    # Create a user preset
    resp = await client.post("/api/presets/user", headers=headers, json={
        "name": "My Custom Filter",
        "severities": [4, 5],
        "types": ["Vulnerability", "Practice"],
    })
    assert resp.status_code == 201
    created = resp.json()
    assert created["name"] == "My Custom Filter"
    preset_id = created["id"]

    # List user presets — should have 1
    resp = await client.get("/api/presets/user", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

    # Delete the preset
    resp = await client.delete(f"/api/presets/user/{preset_id}", headers=headers)
    assert resp.status_code == 204

    # Verify deleted
    resp = await client.get("/api/presets/user", headers=headers)
    presets = resp.json()
    assert all(p["id"] != preset_id for p in presets)

    # Requires auth
    resp = await client.get("/api/presets/user")
    assert resp.status_code == 403
