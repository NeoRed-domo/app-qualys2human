"""User preferences API — dashboard layout and personal settings."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from q2h.auth.dependencies import get_current_user
from q2h.db.engine import get_db
from q2h.db.models import User

router = APIRouter(prefix="/api/user/preferences", tags=["preferences"])


class PreferencesResponse(BaseModel):
    layout: list | None = None
    trends_layout: list | None = None
    settings: dict | None = None
    last_seen_version: str | None = None
    language: str | None = None


class PreferencesUpdate(BaseModel):
    layout: list | None = None
    trends_layout: list | None = None
    settings: dict | None = None
    last_seen_version: str | None = None
    language: str | None = None


@router.get("", response_model=PreferencesResponse)
async def get_preferences(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get current user's preferences."""
    user_id = int(user["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    u = result.scalar_one()
    prefs = u.preferences or {}
    return PreferencesResponse(
        layout=prefs.get("layout"),
        trends_layout=prefs.get("trends_layout"),
        settings=prefs.get("settings"),
        last_seen_version=prefs.get("last_seen_version"),
        language=prefs.get("language"),
    )


@router.put("", response_model=PreferencesResponse)
async def update_preferences(
    body: PreferencesUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Save user preferences (layout and/or settings)."""
    user_id = int(user["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    u = result.scalar_one()
    prefs = dict(u.preferences or {})

    if body.layout is not None:
        prefs["layout"] = body.layout
    if body.trends_layout is not None:
        prefs["trends_layout"] = body.trends_layout
    if body.settings is not None:
        prefs["settings"] = body.settings
    if body.last_seen_version is not None:
        prefs["last_seen_version"] = body.last_seen_version
    if body.language is not None:
        prefs["language"] = body.language

    u.preferences = prefs
    await db.commit()

    return PreferencesResponse(
        layout=prefs.get("layout"),
        trends_layout=prefs.get("trends_layout"),
        settings=prefs.get("settings"),
        last_seen_version=prefs.get("last_seen_version"),
        language=prefs.get("language"),
    )


@router.delete("/layout", response_model=PreferencesResponse)
async def reset_layout(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Reset dashboard layout to default."""
    user_id = int(user["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    u = result.scalar_one()
    prefs = dict(u.preferences or {})
    prefs.pop("layout", None)
    u.preferences = prefs
    await db.commit()

    return PreferencesResponse(
        layout=None,
        trends_layout=prefs.get("trends_layout"),
        settings=prefs.get("settings"),
        last_seen_version=prefs.get("last_seen_version"),
        language=prefs.get("language"),
    )


@router.delete("/trends-layout", response_model=PreferencesResponse)
async def reset_trends_layout(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Reset trends layout to default."""
    user_id = int(user["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    u = result.scalar_one()
    prefs = dict(u.preferences or {})
    prefs.pop("trends_layout", None)
    u.preferences = prefs
    await db.commit()

    return PreferencesResponse(
        layout=prefs.get("layout"),
        trends_layout=None,
        settings=prefs.get("settings"),
        last_seen_version=prefs.get("last_seen_version"),
        language=prefs.get("language"),
    )
