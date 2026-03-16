from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from q2h.auth.service import AuthService
from q2h.db.engine import get_db
from q2h.db.models import User, Profile

security = HTTPBearer()
auth_service = AuthService()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Decode and validate JWT. Returns the token payload (sub, username, profile)."""
    try:
        payload = auth_service.decode_token(credentials.credentials)
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )


async def get_verified_user(
    token_payload: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Validate the JWT user against the database.

    Checks that the user:
    - exists in DB
    - is active (is_active=True)
    - is not locked
    - returns the CURRENT profile from DB (not the one in the JWT)

    This prevents privilege escalation via stale tokens after profile changes.
    """
    from datetime import datetime, timezone

    user_id = int(token_payload["sub"])
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if user.locked_until and user.locked_until > now:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account locked",
        )

    profile_result = await db.execute(
        select(Profile).where(Profile.id == user.profile_id)
    )
    profile = profile_result.scalar_one()

    return {
        "sub": str(user.id),
        "username": user.username,
        "profile": profile.name,
    }


async def require_admin(user: dict = Depends(get_verified_user)) -> dict:
    """Require admin profile, validated against DB (not just JWT)."""
    if user.get("profile") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin required"
        )
    return user


async def require_data_access(user: dict = Depends(get_verified_user)) -> dict:
    """Block monitoring-only profiles from accessing vulnerability data.
    Profile is verified against DB, not just JWT."""
    if user.get("profile") == "monitoring":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Monitoring profile cannot access vulnerability data",
        )
    return user
