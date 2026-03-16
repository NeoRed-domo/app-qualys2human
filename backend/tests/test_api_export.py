import pytest
from httpx import AsyncClient


@pytest.mark.asyncio(loop_scope="session")
async def test_csv_export_overview(client: AsyncClient, admin_token: str):
    """Test CSV export for overview — returns all vulns as CSV."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    resp = await client.get("/api/export/csv?view=overview", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "content-disposition" in resp.headers

    lines = resp.text.strip().split("\n")
    # Header line + data rows
    assert len(lines) >= 1  # at least header
    assert "QID" in lines[0]
    assert "IP" in lines[0]
    assert "Severity" in lines[0]


@pytest.mark.asyncio(loop_scope="session")
async def test_csv_export_with_filter(client: AsyncClient, admin_token: str):
    """Test CSV export with severity filter."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    resp = await client.get("/api/export/csv?view=overview&severities=5", headers=headers)
    assert resp.status_code == 200
    lines = resp.text.strip().split("\n")
    # Should have fewer rows than unfiltered
    assert len(lines) >= 1


@pytest.mark.asyncio(loop_scope="session")
async def test_csv_export_host(client: AsyncClient, admin_token: str):
    """Test CSV export for a specific host's vulns."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    resp = await client.get("/api/export/csv?view=host&ip=10.0.0.1", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")


@pytest.mark.asyncio(loop_scope="session")
async def test_pdf_export_overview(client: AsyncClient, admin_token: str):
    """Test PDF export returns a valid PDF."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    resp = await client.get("/api/export/pdf?view=overview", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"


@pytest.mark.asyncio(loop_scope="session")
async def test_export_requires_auth(client: AsyncClient):
    """Export endpoints require authentication."""
    resp = await client.get("/api/export/csv?view=overview")
    assert resp.status_code == 403
    resp = await client.get("/api/export/pdf?view=overview")
    assert resp.status_code == 403
