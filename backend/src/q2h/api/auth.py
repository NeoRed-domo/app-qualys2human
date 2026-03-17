from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from q2h.auth.service import AuthService
from q2h.auth.ldap_service import LdapService
from q2h.auth.dependencies import get_current_user
from q2h.db.engine import get_db
from q2h.db.models import User, Profile, AuditLog

router = APIRouter(prefix="/api/auth", tags=["auth"])
auth_service = AuthService()

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
# Grace period (seconds) during which the previous refresh token JTI is still valid
REFRESH_GRACE_SECONDS = 60


def _utcnow() -> datetime:
    """Naive UTC datetime — required by asyncpg for TIMESTAMP WITHOUT TIME ZONE columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class LoginRequest(BaseModel):
    username: str
    password: str
    domain: str = "local"


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    profile: str
    must_change_password: bool


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    if req.domain == "local":
        result = await db.execute(
            select(User).join(Profile).where(
                User.username == req.username,
                User.auth_type == "local",
                User.is_active == True,  # noqa: E712
            )
        )
        user = result.scalar_one_or_none()

        # Check lockout before password verification
        if user and user.locked_until and user.locked_until > _utcnow():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="ACCOUNT_LOCKED",
            )

        if not user or not auth_service.verify_password(req.password, user.password_hash):
            # Increment failed attempts if user exists
            if user:
                user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
                if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
                    user.locked_until = _utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
                await db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="INVALID_CREDENTIALS"
            )
    else:
        # ── AD / LDAP authentication ─────────────────────────────
        from q2h.api.ldap import _load_ldap_config, _load_group_mappings

        enabled, ldap_config = await _load_ldap_config(db)
        if not enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="LDAP_NOT_ENABLED",
            )

        # Check lockout if AD user already exists
        existing_result = await db.execute(
            select(User).where(
                User.username == req.username,
                User.auth_type == "ad",
            )
        )
        existing_user = existing_result.scalar_one_or_none()

        if existing_user and existing_user.locked_until and existing_user.locked_until > _utcnow():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="ACCOUNT_LOCKED",
            )

        # Direct bind with user credentials
        ldap_result = LdapService.authenticate(ldap_config, req.username, req.password)
        if not ldap_result.success:
            # Increment lockout if user exists in DB
            if existing_user:
                existing_user.failed_login_attempts = (existing_user.failed_login_attempts or 0) + 1
                if existing_user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
                    existing_user.locked_until = _utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
                await db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ldap_result.error or "INVALID_CREDENTIALS",
            )

        # Resolve profile from AD groups
        group_mappings = await _load_group_mappings(db)
        profile_name = LdapService.resolve_profile(ldap_result.groups, group_mappings)
        if not profile_name:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="NO_MATCHING_AD_GROUP",
            )

        profile_result = await db.execute(
            select(Profile).where(Profile.name == profile_name)
        )
        profile = profile_result.scalar_one_or_none()
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="PROFILE_NOT_FOUND",
            )

        # Check for local account name conflict
        local_conflict = await db.execute(
            select(User).where(
                User.username == req.username,
                User.auth_type == "local",
            )
        )
        if local_conflict.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="LOCAL_ACCOUNT_CONFLICT",
            )

        # Auto-provision or update AD user
        if existing_user:
            user = existing_user
            user.profile_id = profile.id
            user.ad_domain = req.domain
            user.is_active = True
            # Update names from AD if available
            user.first_name = ldap_result.first_name or user.first_name
            user.last_name = ldap_result.last_name or user.last_name
        else:
            user = User(
                username=req.username,
                first_name=ldap_result.first_name or None,
                last_name=ldap_result.last_name or None,
                password_hash=None,
                auth_type="ad",
                profile_id=profile.id,
                ad_domain=req.domain,
                is_active=True,
                must_change_password=False,
            )
            db.add(user)
            await db.flush()  # get user.id

    profile_result = await db.execute(select(Profile).where(Profile.id == user.profile_id))
    profile = profile_result.scalar_one()

    # Success — reset lockout + store JTI
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = _utcnow()
    refresh_token, jti = auth_service.create_refresh_token(user.id)
    user.refresh_token_jti = jti
    user.prev_refresh_token_jti = None
    user.prev_refresh_token_at = None

    db.add(AuditLog(user_id=user.id, action="login", detail=f"domain={req.domain}"))
    await db.commit()

    return TokenResponse(
        access_token=auth_service.create_access_token(user.id, user.username, profile.name),
        refresh_token=refresh_token,
        profile=profile.name,
        must_change_password=user.must_change_password,
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Exchange a valid refresh token for new access + refresh tokens (rotation)."""
    try:
        payload = auth_service.decode_token(req.refresh_token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = int(payload["sub"])
    jti = payload.get("jti")

    result = await db.execute(
        select(User).join(Profile).where(User.id == user_id, User.is_active == True)  # noqa: E712
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    # Validate JTI — current token or previous within grace period
    jti_valid = False
    if jti and jti == user.refresh_token_jti:
        jti_valid = True
    elif (
        jti
        and jti == user.prev_refresh_token_jti
        and user.prev_refresh_token_at
        and (_utcnow() - user.prev_refresh_token_at).total_seconds() < REFRESH_GRACE_SECONDS
    ):
        jti_valid = True
    elif not jti:
        # Legacy tokens without JTI — allow once then rotate
        jti_valid = True

    if not jti_valid:
        # Token reuse detected — invalidate all refresh tokens for safety
        user.refresh_token_jti = None
        user.prev_refresh_token_jti = None
        user.prev_refresh_token_at = None
        await db.commit()
        raise HTTPException(status_code=401, detail="Token reuse detected")

    # Issue new tokens (rotation)
    profile_result = await db.execute(select(Profile).where(Profile.id == user.profile_id))
    profile = profile_result.scalar_one()

    new_refresh, new_jti = auth_service.create_refresh_token(user.id)
    user.prev_refresh_token_jti = user.refresh_token_jti
    user.prev_refresh_token_at = _utcnow()
    user.refresh_token_jti = new_jti
    await db.commit()

    return RefreshResponse(
        access_token=auth_service.create_access_token(user.id, user.username, profile.name),
        refresh_token=new_refresh,
    )


class MeResponse(BaseModel):
    username: str
    profile: str
    must_change_password: bool
    first_name: str | None = None
    last_name: str | None = None


@router.get("/me", response_model=MeResponse)
async def me(
    token_payload: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return current user identity, validated against DB.

    This is the ONLY source of truth for the frontend — localStorage
    must never be trusted for user identity.
    """
    user_id = int(token_payload["sub"])
    result = await db.execute(
        select(User).join(Profile).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    if user.locked_until and user.locked_until > _utcnow():
        raise HTTPException(status_code=403, detail="Account locked")

    profile_result = await db.execute(select(Profile).where(Profile.id == user.profile_id))
    profile = profile_result.scalar_one()
    return MeResponse(
        username=user.username,
        profile=profile.name,
        must_change_password=user.must_change_password,
        first_name=user.first_name,
        last_name=user.last_name,
    )
