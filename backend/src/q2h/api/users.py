"""User management API — CRUD for users and profiles (admin only)."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, update, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from q2h.auth.dependencies import require_admin, get_current_user
from q2h.api._filters import escape_like
from q2h.auth.service import AuthService
from q2h.db.engine import get_db
from q2h.db.models import User, Profile, AuditLog, UserPreset, TrendTemplate

router = APIRouter(prefix="/api/users", tags=["users"])
auth_service = AuthService()


def _user_is_locked(u: User) -> bool:
    return bool(
        u.locked_until
        and u.locked_until > datetime.now(timezone.utc).replace(tzinfo=None)
    )


# --- Schemas ---

class UserResponse(BaseModel):
    id: int
    username: str
    first_name: str | None = None
    last_name: str | None = None
    auth_type: str
    profile_name: str
    profile_id: int
    ad_domain: str | None
    is_active: bool
    must_change_password: bool
    last_login: str | None
    is_locked: bool = False
    failed_login_attempts: int = 0


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int


class UserCreate(BaseModel):
    username: str
    password: str = Field(..., min_length=8)
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    auth_type: str = "local"
    profile_id: int
    ad_domain: Optional[str] = None


class UserUpdate(BaseModel):
    password: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    profile_id: Optional[int] = None
    is_active: Optional[bool] = None
    must_change_password: Optional[bool] = None
    ad_domain: Optional[str] = None
    unlock: Optional[bool] = None


class ProfileResponse(BaseModel):
    id: int
    name: str
    type: str
    permissions: dict
    is_default: bool


# --- Profiles ---

@router.get("/profiles", response_model=list[ProfileResponse])
async def list_profiles(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List all available profiles."""
    result = await db.execute(select(Profile).order_by(Profile.name))
    profiles = result.scalars().all()
    return [
        ProfileResponse(
            id=p.id, name=p.name, type=p.type,
            permissions=p.permissions, is_default=p.is_default,
        )
        for p in profiles
    ]


# --- Users CRUD ---

@router.get("", response_model=UserListResponse)
async def list_users(
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """List all users with pagination."""
    offset = (page - 1) * page_size

    base = select(User, Profile.name.label("profile_name")).join(Profile)
    count_base = select(func.count()).select_from(User)

    if search:
        escaped = escape_like(search)
        base = base.where(User.username.ilike(f"%{escaped}%"))
        count_base = count_base.where(User.username.ilike(f"%{escaped}%"))

    total = (await db.execute(count_base)).scalar()

    q = base.order_by(User.username).offset(offset).limit(page_size)
    rows = (await db.execute(q)).all()

    items = []
    for u, profile_name in rows:
        items.append(UserResponse(
            id=u.id,
            username=u.username,
            first_name=u.first_name,
            last_name=u.last_name,
            auth_type=u.auth_type,
            profile_name=profile_name,
            profile_id=u.profile_id,
            ad_domain=u.ad_domain,
            is_active=u.is_active,
            must_change_password=u.must_change_password,
            last_login=str(u.last_login) if u.last_login else None,
            is_locked=_user_is_locked(u),
            failed_login_attempts=u.failed_login_attempts or 0,
        ))

    return UserListResponse(items=items, total=total)


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Create a new user."""
    # Check username uniqueness
    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already exists")

    # Validate profile
    profile_result = await db.execute(select(Profile).where(Profile.id == body.profile_id))
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid profile_id")

    new_user = User(
        username=body.username,
        first_name=body.first_name,
        last_name=body.last_name,
        password_hash=auth_service.hash_password(body.password),
        auth_type=body.auth_type,
        profile_id=body.profile_id,
        ad_domain=body.ad_domain,
        must_change_password=True,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return UserResponse(
        id=new_user.id,
        username=new_user.username,
        first_name=new_user.first_name,
        last_name=new_user.last_name,
        auth_type=new_user.auth_type,
        profile_name=profile.name,
        profile_id=new_user.profile_id,
        ad_domain=new_user.ad_domain,
        is_active=new_user.is_active,
        must_change_password=new_user.must_change_password,
        last_login=None,
        is_locked=False,
        failed_login_attempts=0,
    )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Update an existing user."""
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    if body.password is not None:
        target.password_hash = auth_service.hash_password(body.password)
    if body.first_name is not None:
        target.first_name = body.first_name
    if body.last_name is not None:
        target.last_name = body.last_name
    if body.profile_id is not None:
        # Validate profile
        profile_check = await db.execute(select(Profile).where(Profile.id == body.profile_id))
        if not profile_check.scalar_one_or_none():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid profile_id")
        target.profile_id = body.profile_id
    if body.is_active is not None:
        target.is_active = body.is_active
    if body.must_change_password is not None:
        target.must_change_password = body.must_change_password
    if body.ad_domain is not None:
        target.ad_domain = body.ad_domain
    if body.unlock is True:
        target.failed_login_attempts = 0
        target.locked_until = None

    await db.commit()
    await db.refresh(target)

    profile_result = await db.execute(select(Profile).where(Profile.id == target.profile_id))
    profile = profile_result.scalar_one()

    return UserResponse(
        id=target.id,
        username=target.username,
        first_name=target.first_name,
        last_name=target.last_name,
        auth_type=target.auth_type,
        profile_name=profile.name,
        profile_id=target.profile_id,
        ad_domain=target.ad_domain,
        is_active=target.is_active,
        must_change_password=target.must_change_password,
        last_login=str(target.last_login) if target.last_login else None,
        is_locked=_user_is_locked(target),
        failed_login_attempts=target.failed_login_attempts or 0,
    )


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Delete a user (cannot delete yourself)."""
    current_user_id = int(user["sub"])
    if user_id == current_user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot delete yourself")

    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    # Nullify FKs that reference this user (keep audit logs for traceability)
    # Nullify FKs that reference this user (keep audit logs for traceability)
    await db.execute(
        update(AuditLog).where(AuditLog.user_id == user_id).values(user_id=None)
    )
    await db.execute(
        update(TrendTemplate).where(TrendTemplate.created_by == user_id).values(created_by=None)
    )
    # Delete user presets (no need to keep those)
    await db.execute(
        sql_delete(UserPreset).where(UserPreset.user_id == user_id)
    )

    await db.delete(target)
    await db.commit()
