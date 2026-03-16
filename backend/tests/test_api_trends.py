import pytest
from httpx import AsyncClient


@pytest.mark.asyncio(loop_scope="session")
async def test_trend_config(client: AsyncClient, admin_token: str):
    """Test trend config GET and PUT."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    # GET config — should return defaults
    resp = await client.get("/api/trends/config", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "max_window_days" in data
    assert "query_timeout_seconds" in data

    # PUT config (admin only)
    resp = await client.put("/api/trends/config", headers=headers, json={
        "max_window_days": 180,
        "query_timeout_seconds": 15,
    })
    assert resp.status_code == 200
    assert resp.json()["max_window_days"] == 180

    # Verify update persisted
    resp = await client.get("/api/trends/config", headers=headers)
    assert resp.json()["max_window_days"] == 180


@pytest.mark.asyncio(loop_scope="session")
async def test_trend_templates(client: AsyncClient, admin_token: str):
    """Test trend templates CRUD."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    # GET templates — initially empty
    resp = await client.get("/api/trends/templates", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

    # POST a new template
    resp = await client.post("/api/trends/templates", headers=headers, json={
        "name": "Critical vulns over time",
        "metric": "critical_count",
        "group_by": "severity",
        "filters": {"severities": [4, 5]},
    })
    assert resp.status_code == 201
    tmpl = resp.json()
    assert tmpl["name"] == "Critical vulns over time"
    assert tmpl["metric"] == "critical_count"
    tmpl_id = tmpl["id"]

    # GET templates — should have 1
    resp = await client.get("/api/trends/templates", headers=headers)
    assert len(resp.json()) >= 1

    # DELETE template
    resp = await client.delete(f"/api/trends/templates/{tmpl_id}", headers=headers)
    assert resp.status_code == 204


@pytest.mark.asyncio(loop_scope="session")
async def test_trend_query(client: AsyncClient, admin_token: str):
    """Test POST /api/trends/query executes a trend query."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    resp = await client.post("/api/trends/query", headers=headers, json={
        "metric": "total_vulns",
        "group_by": None,
        "date_from": "2025-01-01",
        "date_to": "2026-12-31",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "series" in data
    assert isinstance(data["series"], list)

    # Requires auth
    resp = await client.post("/api/trends/query", json={
        "metric": "total_vulns",
    })
    assert resp.status_code == 403
