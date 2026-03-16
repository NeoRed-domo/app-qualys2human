import pytest
from httpx import AsyncClient


@pytest.mark.asyncio(loop_scope="session")
async def test_host_detail(client: AsyncClient, admin_token: str):
    """Test GET /api/hosts/{ip} returns host info with vuln summary."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Host 10.0.0.1 was seeded — has 3 vulns (QID 1001, 1002, 1004)
    resp = await client.get("/api/hosts/10.0.0.1", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ip"] == "10.0.0.1"
    assert data["dns"] == "server1.test.local"
    assert data["os"] == "Windows Server 2019"
    assert data["vuln_count"] == 3

    # Non-existent host
    resp = await client.get("/api/hosts/192.168.99.99", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_host_vulnerabilities(client: AsyncClient, admin_token: str):
    """Test GET /api/hosts/{ip}/vulnerabilities returns paginated vuln list."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    resp = await client.get("/api/hosts/10.0.0.1/vulnerabilities", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] == 3
    assert len(data["items"]) == 3
    # Each item has vuln info
    assert "qid" in data["items"][0]
    assert "title" in data["items"][0]
    assert "severity" in data["items"][0]

    # Test pagination
    resp = await client.get(
        "/api/hosts/10.0.0.1/vulnerabilities?page=1&page_size=2", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["total"] == 3

    # Requires auth
    resp = await client.get("/api/hosts/10.0.0.1/vulnerabilities")
    assert resp.status_code == 403
