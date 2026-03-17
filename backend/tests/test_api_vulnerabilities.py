import pytest
from httpx import AsyncClient


@pytest.mark.asyncio(loop_scope="session")
async def test_vulnerability_detail(client: AsyncClient, admin_token: str):
    """Test GET /api/vulnerabilities/{qid} returns vuln detail with affected hosts."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    # QID 1001 was seeded in test_api_dashboard — appears on 2 hosts
    resp = await client.get("/api/vulnerabilities/1001", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["qid"] == 1001
    assert data["title"] == "Critical RCE Vuln"
    assert data["severity"] == 5
    assert data["affected_host_count"] == 2
    assert data["total_occurrences"] == 2

    # Non-existent QID
    resp = await client.get("/api/vulnerabilities/99999", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_vulnerability_hosts(client: AsyncClient, admin_token: str):
    """Test GET /api/vulnerabilities/{qid}/hosts returns paginated host list."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    resp = await client.get("/api/vulnerabilities/1001/hosts", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] == 2
    assert len(data["items"]) == 2
    # Each item has host info
    assert "ip" in data["items"][0]

    # Test pagination
    resp = await client.get(
        "/api/vulnerabilities/1001/hosts?page=1&page_size=1", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["total"] == 2

    # Requires auth
    resp = await client.get("/api/vulnerabilities/1001/hosts")
    assert resp.status_code == 403
