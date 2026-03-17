"""Tests for the users management API."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio(loop_scope="session")
async def test_list_profiles(client: AsyncClient, admin_token: str):
    resp = await client.get(
        "/api/users/profiles",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    profiles = resp.json()
    assert len(profiles) >= 3  # admin, user, monitoring
    names = [p["name"] for p in profiles]
    assert "admin" in names
    assert "user" in names


@pytest.mark.asyncio(loop_scope="session")
async def test_list_users(client: AsyncClient, admin_token: str):
    resp = await client.get(
        "/api/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] >= 1  # at least admin
    admin_user = next(u for u in data["items"] if u["username"] == "admin")
    assert admin_user["profile_name"] == "admin"


@pytest.mark.asyncio(loop_scope="session")
async def test_create_and_delete_user(client: AsyncClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Get user profile id
    profiles = (await client.get("/api/users/profiles", headers=headers)).json()
    user_profile = next(p for p in profiles if p["name"] == "user")

    # Create user
    resp = await client.post(
        "/api/users",
        headers=headers,
        json={
            "username": "testuser_crud",
            "password": "TestPass123!",
            "profile_id": user_profile["id"],
        },
    )
    assert resp.status_code == 201
    created = resp.json()
    assert created["username"] == "testuser_crud"
    assert created["profile_name"] == "user"
    assert created["is_active"] is True
    user_id = created["id"]

    # Update user — deactivate
    resp = await client.put(
        f"/api/users/{user_id}",
        headers=headers,
        json={"is_active": False},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    # Delete user
    resp = await client.delete(f"/api/users/{user_id}", headers=headers)
    assert resp.status_code == 204


@pytest.mark.asyncio(loop_scope="session")
async def test_create_duplicate_username(client: AsyncClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}
    profiles = (await client.get("/api/users/profiles", headers=headers)).json()
    user_profile = next(p for p in profiles if p["name"] == "user")

    resp = await client.post(
        "/api/users",
        headers=headers,
        json={
            "username": "admin",  # already exists
            "password": "whatever",
            "profile_id": user_profile["id"],
        },
    )
    assert resp.status_code == 409


@pytest.mark.asyncio(loop_scope="session")
async def test_cannot_delete_self(client: AsyncClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}
    # Get admin user id from list
    users = (await client.get("/api/users", headers=headers)).json()
    admin_user = next(u for u in users["items"] if u["username"] == "admin")

    resp = await client.delete(f"/api/users/{admin_user['id']}", headers=headers)
    assert resp.status_code == 400
    assert "yourself" in resp.json()["detail"].lower()


@pytest.mark.asyncio(loop_scope="session")
async def test_list_users_requires_admin(client: AsyncClient):
    resp = await client.get("/api/users")
    assert resp.status_code in (401, 403)
