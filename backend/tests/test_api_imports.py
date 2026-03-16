"""Tests for the imports API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio(loop_scope="session")
async def test_list_imports(client: AsyncClient, admin_token: str):
    resp = await client.get(
        "/api/imports",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio(loop_scope="session")
async def test_list_imports_requires_auth(client: AsyncClient):
    resp = await client.get("/api/imports")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio(loop_scope="session")
async def test_get_import_not_found(client: AsyncClient, admin_token: str):
    resp = await client.get(
        "/api/imports/99999",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_upload_rejects_non_csv(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/imports/upload",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": ("notes.txt", b"hello world", "text/plain")},
    )
    assert resp.status_code == 400
    assert "csv" in resp.json()["detail"].lower()


@pytest.mark.asyncio(loop_scope="session")
async def test_upload_rejects_empty_csv(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/imports/upload",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": ("empty.csv", b"", "text/csv")},
    )
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()
