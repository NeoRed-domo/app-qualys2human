"""Shared filter helpers used across dashboard, vulnerabilities, trends, search, etc."""

from sqlalchemy import select, func, or_, text
from sqlalchemy.ext.asyncio import AsyncSession

from q2h.db.models import AppSettings


# ── Freshness thresholds ────────────────────────────────────────────

async def get_freshness_thresholds(db: AsyncSession) -> dict:
    """Fetch admin-configurable freshness thresholds from app_settings."""
    stale = (await db.execute(
        select(AppSettings.value).where(AppSettings.key == "freshness_stale_days")
    )).scalar() or "7"
    hide = (await db.execute(
        select(AppSettings.value).where(AppSettings.key == "freshness_hide_days")
    )).scalar() or "30"
    return {"stale_days": int(stale), "hide_days": int(hide)}


def _make_interval_days(days: int):
    """Build a safe SQL interval literal. int() cast prevents injection."""
    return text(f"interval '{int(days)} days'")


def apply_freshness(stmt, column, freshness_val: str, thresholds: dict):
    """Apply freshness filter to a query using the given date column.

    Works with both LatestVuln.last_detected and Vulnerability.last_detected.
    NULL last_detected is treated as active (not filtered out).
    """
    if freshness_val == "all":
        return stmt
    stale_interval = _make_interval_days(thresholds["stale_days"])
    hide_interval = _make_interval_days(thresholds["hide_days"])
    if freshness_val == "stale":
        return stmt.where(
            column.is_not(None),
            column < func.now() - stale_interval,
            column >= func.now() - hide_interval,
        )
    # Default: active only — include NULLs (unknown date = assume active)
    return stmt.where(
        or_(
            column >= func.now() - stale_interval,
            column.is_(None),
        )
    )


# ── ILIKE escaping ──────────────────────────────────────────────────

def escape_like(s: str) -> str:
    """Escape special LIKE/ILIKE characters (%, _) for safe pattern matching."""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ── OS classification ───────────────────────────────────────────────

NIX_PATTERNS = [
    "%linux%", "%unix%", "%ubuntu%", "%debian%", "%centos%",
    "%red hat%", "%rhel%", "%suse%", "%fedora%",
    "%aix%", "%solaris%", "%freebsd%",
]


def nix_ilike_conditions(os_column):
    """Return a list of ILIKE conditions matching NIX-family operating systems."""
    return [os_column.ilike(p) for p in NIX_PATTERNS]


def os_class_case(os_column):
    """Build a CASE expression classifying OS into Windows / NIX / Autre."""
    from sqlalchemy import case
    return case(
        (os_column.ilike("%windows%"), "Windows"),
        (or_(*nix_ilike_conditions(os_column)), "NIX"),
        else_="Autre",
    )


def os_type_case(os_column):
    """Build a CASE expression extracting OS type (e.g. Windows Server, Ubuntu, RHEL)."""
    from sqlalchemy import case
    return case(
        (os_column.ilike("%windows server%"), "Windows Server"),
        (os_column.ilike("%windows%"), "Windows Desktop"),
        (os_column.ilike("%ubuntu%"), "Ubuntu"),
        (os_column.ilike("%red hat%"), "RHEL"),
        (os_column.ilike("%rhel%"), "RHEL"),
        (os_column.ilike("%centos%"), "CentOS"),
        (os_column.ilike("%debian%"), "Debian"),
        (os_column.ilike("%suse%"), "SUSE"),
        (os_column.ilike("%sles%"), "SUSE"),
        (os_column.ilike("%fedora%"), "Fedora"),
        (os_column.ilike("%aix%"), "AIX"),
        (os_column.ilike("%solaris%"), "Solaris"),
        (os_column.ilike("%freebsd%"), "FreeBSD"),
        (os_column.ilike("%linux%"), "Linux"),
        (os_column.ilike("%unix%"), "Unix"),
        else_="Other",
    )


def os_class_filter_conditions(os_column, cls_list: list[str]):
    """Return OR conditions for filtering by OS class list."""
    conditions = []
    if "windows" in cls_list:
        conditions.append(os_column.ilike("%windows%"))
    if "nix" in cls_list:
        conditions.append(or_(*nix_ilike_conditions(os_column)))
    return conditions
