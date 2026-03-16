"""Tests for the branding API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio(loop_scope="session")
async def test_get_default_logo(client: AsyncClient, admin_token: str):
    resp = await client.get(
        "/api/branding/logo",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert "svg" in resp.headers.get("content-type", "")


@pytest.mark.asyncio(loop_scope="session")
async def test_get_template(client: AsyncClient, admin_token: str):
    resp = await client.get(
        "/api/branding/template",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert "svg" in resp.headers.get("content-type", "")
    assert b"Votre Logo Ici" in resp.content


@pytest.mark.asyncio(loop_scope="session")
async def test_upload_and_delete_logo(client: AsyncClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Upload a small PNG-like file
    fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    resp = await client.post(
        "/api/branding/logo",
        headers=headers,
        files={"file": ("test-logo.png", fake_png, "image/png")},
    )
    assert resp.status_code == 200
    assert "uploaded" in resp.json()["message"].lower()

    # Get should now return custom logo
    resp = await client.get("/api/branding/logo", headers=headers)
    assert resp.status_code == 200
    assert "png" in resp.headers.get("content-type", "")

    # Delete custom logo
    resp = await client.delete("/api/branding/logo", headers=headers)
    assert resp.status_code == 200

    # Should be back to default SVG
    resp = await client.get("/api/branding/logo", headers=headers)
    assert resp.status_code == 200
    assert "svg" in resp.headers.get("content-type", "")


@pytest.mark.asyncio(loop_scope="session")
async def test_upload_rejects_bad_extension(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/branding/logo",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": ("logo.exe", b"bad content", "application/octet-stream")},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_no_custom_logo(client: AsyncClient, admin_token: str):
    resp = await client.delete(
        "/api/branding/logo",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404
