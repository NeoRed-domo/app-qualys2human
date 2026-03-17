"""LDAP / Active Directory admin API."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from q2h.auth.dependencies import get_current_user, require_admin
from q2h.auth.ldap_service import LdapConfig, LdapService
from q2h.db.engine import get_db
from q2h.db.models import AppSettings, Profile

router = APIRouter(prefix="/api/ldap", tags=["ldap"])

# ── AppSettings keys for LDAP config ──────────────────────────────

_LDAP_KEYS = {
    "enabled": "ldap_enabled",
    "server_url": "ldap_server_url",
    "use_starttls": "ldap_use_starttls",
    "upn_template": "ldap_upn_template",
    "search_base": "ldap_search_base",
    "group_attribute": "ldap_group_attribute",
    "tls_verify": "ldap_tls_verify",
    "tls_ca_cert": "ldap_tls_ca_cert",
}

_LDAP_DEFAULTS = {
    "enabled": "false",
    "server_url": "",
    "use_starttls": "false",
    "upn_template": "{username}@domain.com",
    "search_base": "",
    "group_attribute": "memberOf",
    "tls_verify": "false",
    "tls_ca_cert": "",
}


# ── Helpers (exported for auth.py) ────────────────────────────────

async def _load_ldap_config(db: AsyncSession) -> tuple[bool, LdapConfig]:
    """Load LDAP config from AppSettings. Returns (enabled, config)."""
    vals: dict[str, str] = {}
    for field, key in _LDAP_KEYS.items():
        row = await db.execute(select(AppSettings.value).where(AppSettings.key == key))
        vals[field] = row.scalar() or _LDAP_DEFAULTS[field]
    enabled = vals["enabled"].lower() == "true"
    config = LdapConfig(
        server_url=vals["server_url"],
        use_starttls=vals["use_starttls"].lower() == "true",
        upn_template=vals["upn_template"],
        search_base=vals["search_base"],
        group_attribute=vals["group_attribute"],
        tls_verify=vals["tls_verify"].lower() == "true",
        tls_ca_cert=vals["tls_ca_cert"],
    )
    return enabled, config


async def _load_group_mappings(db: AsyncSession) -> dict[str, str]:
    """Load profile → ad_group_dn mappings. Returns {profile_name: ad_group_dn}."""
    result = await db.execute(
        select(Profile.name, Profile.ad_group_dn).where(
            Profile.ad_group_dn.isnot(None),
            Profile.ad_group_dn != "",
        )
    )
    return {name: dn for name, dn in result.all()}


# ── Pydantic models ──────────────────────────────────────────────

class GroupMapping(BaseModel):
    profile_name: str
    ad_group_dn: str


class LdapSettingsResponse(BaseModel):
    enabled: bool
    server_url: str
    use_starttls: bool
    upn_template: str
    search_base: str
    group_attribute: str
    tls_verify: bool
    tls_ca_cert: str
    default_auth_mode: str  # "local" or "ad"
    group_mappings: list[GroupMapping]


class LdapSettingsUpdate(BaseModel):
    enabled: bool = False
    server_url: str = ""
    use_starttls: bool = False
    upn_template: str = "{username}@domain.com"
    search_base: str = ""
    group_attribute: str = "memberOf"
    tls_verify: bool = False
    tls_ca_cert: str = ""
    default_auth_mode: str = "local"
    group_mappings: list[GroupMapping] = []


class LdapTestRequest(BaseModel):
    username: str
    password: str


class LdapTestResponse(BaseModel):
    success: bool
    message: str


class LdapEnabledResponse(BaseModel):
    enabled: bool
    default_mode: str  # "local" or "ad"


# ── Endpoints ────────────────────────────────────────────────────

@router.get("/settings", response_model=LdapSettingsResponse)
async def get_ldap_settings(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    enabled, config = await _load_ldap_config(db)
    mappings = await _load_group_mappings(db)
    row = await db.execute(
        select(AppSettings.value).where(AppSettings.key == "ldap_default_auth_mode")
    )
    default_auth_mode = row.scalar() or "local"
    return LdapSettingsResponse(
        enabled=enabled,
        server_url=config.server_url,
        use_starttls=config.use_starttls,
        upn_template=config.upn_template,
        search_base=config.search_base,
        group_attribute=config.group_attribute,
        tls_verify=config.tls_verify,
        tls_ca_cert=config.tls_ca_cert,
        default_auth_mode=default_auth_mode,
        group_mappings=[
            GroupMapping(profile_name=name, ad_group_dn=dn)
            for name, dn in mappings.items()
        ],
    )


@router.put("/settings", response_model=LdapSettingsResponse)
async def update_ldap_settings(
    body: LdapSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    # Save config to AppSettings
    updates = {
        "enabled": str(body.enabled).lower(),
        "server_url": body.server_url,
        "use_starttls": str(body.use_starttls).lower(),
        "upn_template": body.upn_template,
        "search_base": body.search_base,
        "group_attribute": body.group_attribute,
        "tls_verify": str(body.tls_verify).lower(),
        "tls_ca_cert": body.tls_ca_cert,
    }
    for field_name, value in updates.items():
        key = _LDAP_KEYS[field_name]
        existing = (
            await db.execute(select(AppSettings).where(AppSettings.key == key))
        ).scalar_one_or_none()
        if existing:
            existing.value = value
        else:
            db.add(AppSettings(key=key, value=value))

    # Save default_auth_mode
    dam_key = "ldap_default_auth_mode"
    dam_val = body.default_auth_mode if body.default_auth_mode in ("local", "ad") else "local"
    existing_dam = (
        await db.execute(select(AppSettings).where(AppSettings.key == dam_key))
    ).scalar_one_or_none()
    if existing_dam:
        existing_dam.value = dam_val
    else:
        db.add(AppSettings(key=dam_key, value=dam_val))

    # Save group mappings to Profile.ad_group_dn
    for mapping in body.group_mappings:
        profile = (
            await db.execute(
                select(Profile).where(Profile.name == mapping.profile_name)
            )
        ).scalar_one_or_none()
        if profile:
            profile.ad_group_dn = mapping.ad_group_dn

    await db.commit()

    # Return updated state
    return await get_ldap_settings(db=db, admin=admin)


@router.post("/test", response_model=LdapTestResponse)
async def test_ldap_connection(
    body: LdapTestRequest,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """Test LDAP connectivity with a direct bind using the provided credentials."""
    enabled, config = await _load_ldap_config(db)
    if not config.server_url:
        raise HTTPException(400, "LDAP_URL_NOT_CONFIGURED")
    result = LdapService.test_connection(config, body.username, body.password)
    return LdapTestResponse(**result)


@router.get("/enabled", response_model=LdapEnabledResponse)
async def ldap_enabled(db: AsyncSession = Depends(get_db)):
    """Public endpoint (no auth) — tells the login page whether AD is available."""
    row = await db.execute(
        select(AppSettings.value).where(AppSettings.key == "ldap_enabled")
    )
    val = row.scalar() or "false"
    row2 = await db.execute(
        select(AppSettings.value).where(AppSettings.key == "ldap_default_auth_mode")
    )
    default_mode = row2.scalar() or "local"
    return LdapEnabledResponse(enabled=val.lower() == "true", default_mode=default_mode)
