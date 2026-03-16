import pytest
from datetime import datetime
from httpx import AsyncClient


async def seed_test_data():
    """Seed scan report, hosts, and vulnerabilities via direct DB access."""
    from sqlalchemy import delete
    from q2h.db.engine import SessionLocal
    from q2h.db.models import ScanReport, Host, Vulnerability

    async with SessionLocal() as session:
        # Clean up any leftover test data
        await session.execute(delete(Vulnerability))
        await session.execute(delete(Host))
        await session.execute(delete(ScanReport))
        await session.commit()

    async with SessionLocal() as session:
        report = ScanReport(
            filename="test_report.csv",
            report_date=datetime(2026, 1, 15),
            asset_group="TestGroup",
            total_vulns_declared=5,
            source="manual",
        )
        session.add(report)
        await session.flush()

        host1 = Host(ip="10.0.0.1", dns="server1.test.local", os="Windows Server 2019")
        host2 = Host(ip="10.0.0.2", dns="server2.test.local", os="Linux Ubuntu 22.04")
        session.add_all([host1, host2])
        await session.flush()

        vulns = [
            Vulnerability(
                scan_report_id=report.id, host_id=host1.id, qid=1001,
                title="Critical RCE Vuln", severity=5, type="Vulnerability",
                category="Windows", tracking_method="IP",
            ),
            Vulnerability(
                scan_report_id=report.id, host_id=host1.id, qid=1002,
                title="Medium Info Disclosure", severity=3, type="Vulnerability",
                category="Web Application", tracking_method="IP",
            ),
            Vulnerability(
                scan_report_id=report.id, host_id=host2.id, qid=1001,
                title="Critical RCE Vuln", severity=5, type="Vulnerability",
                category="Windows", tracking_method="IP",
            ),
            Vulnerability(
                scan_report_id=report.id, host_id=host2.id, qid=1003,
                title="Low Risk Finding", severity=1, type="Practice",
                category="General", tracking_method="IP",
            ),
            Vulnerability(
                scan_report_id=report.id, host_id=host1.id, qid=1004,
                title="High Privilege Escalation", severity=4, type="Vulnerability",
                category="Windows", tracking_method="IP",
            ),
        ]
        session.add_all(vulns)
        await session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_dashboard_overview(client: AsyncClient, admin_token: str):
    """Test the dashboard overview endpoint returns KPIs and top 10s."""
    await seed_test_data()
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Call overview with no filters
    resp = await client.get("/api/dashboard/overview", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    # KPI assertions
    assert data["total_vulns"] == 5
    assert data["host_count"] == 2
    assert data["critical_count"] == 3  # severity 4 + 5
    assert isinstance(data["severity_distribution"], list)

    # Severity distribution check
    sev_map = {s["severity"]: s["count"] for s in data["severity_distribution"]}
    assert sev_map[5] == 2  # two severity-5 vulns
    assert sev_map[4] == 1
    assert sev_map[3] == 1
    assert sev_map[1] == 1

    # Top vulns (by frequency)
    assert len(data["top_vulns"]) <= 10
    assert data["top_vulns"][0]["qid"] == 1001  # appears twice
    assert data["top_vulns"][0]["count"] == 2

    # Top hosts (by vuln count)
    assert len(data["top_hosts"]) <= 10
    assert data["top_hosts"][0]["host_count"] == 3  # host1 has 3 vulns

    # Coherence checks
    assert isinstance(data["coherence_checks"], list)

    # Test with severity filter
    resp = await client.get(
        "/api/dashboard/overview?severities=5", headers=headers
    )
    assert resp.status_code == 200
    filtered = resp.json()
    assert filtered["total_vulns"] == 2  # only severity 5

    # Test with report_id filter
    resp = await client.get(
        "/api/dashboard/overview?report_id=1", headers=headers
    )
    assert resp.status_code == 200

    # Requires auth
    resp = await client.get("/api/dashboard/overview")
    assert resp.status_code == 403  # no token
