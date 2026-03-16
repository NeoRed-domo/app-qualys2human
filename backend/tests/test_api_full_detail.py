import pytest
from httpx import AsyncClient


@pytest.mark.asyncio(loop_scope="session")
async def test_full_detail(client: AsyncClient, admin_token: str):
    """Test GET /api/hosts/{ip}/vulnerabilities/{qid} returns all fields."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Host 10.0.0.1 + QID 1001 exists from seeded data
    resp = await client.get(
        "/api/hosts/10.0.0.1/vulnerabilities/1001", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ip"] == "10.0.0.1"
    assert data["qid"] == 1001
    assert data["title"] == "Critical RCE Vuln"
    assert data["severity"] == 5
    assert data["type"] == "Vulnerability"
    assert data["category"] == "Windows"
    # All raw fields should be present (even if null)
    for field in [
        "vuln_status", "port", "protocol", "fqdn", "ssl",
        "first_detected", "last_detected", "times_detected",
        "cve_ids", "vendor_reference", "bugtraq_id",
        "cvss_base", "cvss_temporal", "cvss3_base", "cvss3_temporal",
        "threat", "impact", "solution", "results",
        "pci_vuln", "ticket_state", "tracking_method",
        "dns", "os",
    ]:
        assert field in data, f"Missing field: {field}"

    # Non-existent combo
    resp = await client.get(
        "/api/hosts/10.0.0.1/vulnerabilities/99999", headers=headers
    )
    assert resp.status_code == 404

    resp = await client.get(
        "/api/hosts/192.168.99.99/vulnerabilities/1001", headers=headers
    )
    assert resp.status_code == 404

    # Requires auth
    resp = await client.get("/api/hosts/10.0.0.1/vulnerabilities/1001")
    assert resp.status_code == 403
