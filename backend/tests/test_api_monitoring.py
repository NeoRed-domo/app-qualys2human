"""Tests for the monitoring API endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio(loop_scope="session")
async def test_monitoring_returns_all_sections(client: AsyncClient, admin_token: str):
    resp = await client.get(
        "/api/monitoring",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    # Top-level fields
    assert "uptime_seconds" in data
    assert isinstance(data["uptime_seconds"], int)
    assert "platform" in data
    assert "python_version" in data

    # Services
    assert "services" in data
    assert len(data["services"]) >= 2
    service_names = [s["name"] for s in data["services"]]
    assert "PostgreSQL" in service_names
    assert "API FastAPI" in service_names
    for svc in data["services"]:
        assert svc["status"] in ("ok", "warning", "error")

    # System metrics
    sys = data["system"]
    assert 0 <= sys["cpu_percent"] <= 100
    assert sys["memory_total_mb"] > 0
    assert sys["disk_total_gb"] > 0

    # DB pool
    assert data["db_pool"] is not None
    assert data["db_pool"]["pool_size"] > 0

    # Activity
    act = data["activity"]
    assert act["total_users"] >= 1  # at least admin

    # Alerts is a list (may be empty)
    assert isinstance(data["alerts"], list)


@pytest.mark.asyncio(loop_scope="session")
async def test_monitoring_requires_auth(client: AsyncClient):
    resp = await client.get("/api/monitoring")
    assert resp.status_code in (401, 403)
