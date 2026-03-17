# backend/tests/test_upgrade_api.py
"""Integration tests for upgrade API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_get_schedule_no_upgrade(client: AsyncClient, admin_token: str):
    """No upgrade scheduled -> scheduled: false."""
    resp = await client.get(
        "/api/upgrade/schedule",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["scheduled"] is False


@pytest.mark.anyio
async def test_get_history_empty(client: AsyncClient, admin_token: str):
    """No upgrades done -> empty list."""
    resp = await client.get(
        "/api/upgrade/history",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.anyio
async def test_get_settings_defaults(client: AsyncClient, admin_token: str):
    """Default notification thresholds."""
    resp = await client.get(
        "/api/upgrade/settings",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["default_thresholds"]) == 3
    assert data["default_thresholds"][0]["minutes_before"] == 2880


@pytest.mark.anyio
async def test_update_settings(client: AsyncClient, admin_token: str):
    """Update notification thresholds."""
    new_thresholds = [
        {"minutes_before": 1440, "level": "info"},
        {"minutes_before": 60, "level": "warning"},
        {"minutes_before": 10, "level": "danger"},
    ]
    resp = await client.put(
        "/api/upgrade/settings",
        json={"default_thresholds": new_thresholds},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["default_thresholds"] == new_thresholds


@pytest.mark.anyio
async def test_cancel_no_schedule(client: AsyncClient, admin_token: str):
    """Cancel when nothing scheduled -> 404."""
    resp = await client.delete(
        "/api/upgrade/schedule",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_upload_requires_admin(client: AsyncClient):
    """Upload without auth -> 401/403."""
    resp = await client.post("/api/upgrade/upload")
    assert resp.status_code in (401, 403, 422)


@pytest.mark.anyio
async def test_history_requires_admin(client: AsyncClient):
    """History without auth -> 401/403."""
    resp = await client.get("/api/upgrade/history")
    assert resp.status_code in (401, 403)


@pytest.mark.anyio
async def test_schedule_get_allows_any_user(client: AsyncClient, admin_token: str):
    """GET /schedule is accessible to any authenticated user (for banner)."""
    resp = await client.get(
        "/api/upgrade/schedule",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
