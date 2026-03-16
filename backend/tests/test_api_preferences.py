"""Tests for the user preferences API."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio(loop_scope="session")
async def test_get_default_preferences(client: AsyncClient, admin_token: str):
    resp = await client.get(
        "/api/user/preferences",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "layout" in data
    assert "settings" in data


@pytest.mark.asyncio(loop_scope="session")
async def test_save_and_get_layout(client: AsyncClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}

    layout = [
        {"i": "kpi", "x": 0, "y": 0, "w": 12, "h": 2},
        {"i": "severity", "x": 0, "y": 2, "w": 6, "h": 4},
    ]

    # Save layout
    resp = await client.put(
        "/api/user/preferences",
        headers=headers,
        json={"layout": layout},
    )
    assert resp.status_code == 200
    assert resp.json()["layout"] == layout

    # Get and verify persisted
    resp = await client.get("/api/user/preferences", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["layout"] == layout


@pytest.mark.asyncio(loop_scope="session")
async def test_reset_layout(client: AsyncClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Reset
    resp = await client.delete("/api/user/preferences/layout", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["layout"] is None

    # Verify
    resp = await client.get("/api/user/preferences", headers=headers)
    assert resp.json()["layout"] is None


@pytest.mark.asyncio(loop_scope="session")
async def test_save_settings(client: AsyncClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}

    resp = await client.put(
        "/api/user/preferences",
        headers=headers,
        json={"settings": {"theme": "dark", "language": "fr"}},
    )
    assert resp.status_code == 200
    assert resp.json()["settings"]["theme"] == "dark"


@pytest.mark.asyncio(loop_scope="session")
async def test_preferences_requires_auth(client: AsyncClient):
    resp = await client.get("/api/user/preferences")
    assert resp.status_code in (401, 403)
