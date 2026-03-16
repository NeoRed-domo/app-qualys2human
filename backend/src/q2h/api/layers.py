import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func, update, delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from q2h.auth.dependencies import get_current_user, require_admin, require_data_access
from q2h.api._filters import escape_like
from q2h.db import engine as db_engine
from q2h.db.engine import get_db
from q2h.db.models import VulnLayer, VulnLayerRule, Vulnerability, LatestVuln

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/layers", tags=["layers"])


# --- Reclassify job state (in-memory singleton) ---

class _ReclassifyState:
    running: bool = False
    progress: int = 0          # 0-100
    total_rules: int = 0
    rules_applied: int = 0
    classified: int = 0
    error: str | None = None
    dirty: bool | None = None   # None = unknown (server just started), True = rules changed, False = up-to-date

_reclassify = _ReclassifyState()


# --- Schemas ---

class LayerResponse(BaseModel):
    id: int
    name: str
    color: str
    position: int


class LayerCreate(BaseModel):
    name: str
    color: str = "#1677ff"
    position: int = 0


class LayerUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    position: Optional[int] = None


class RuleResponse(BaseModel):
    id: int
    layer_id: int
    match_field: str
    pattern: str
    priority: int
    created_at: str | None = None
    layer_name: str | None = None


class RuleCreate(BaseModel):
    match_field: str  # "title" | "category"
    pattern: str
    priority: int = 0


class RuleUpdate(BaseModel):
    match_field: Optional[str] = None
    pattern: Optional[str] = None
    priority: Optional[int] = None
    layer_id: Optional[int] = None


class MatchCountResponse(BaseModel):
    count: int


class AssignLayerRequest(BaseModel):
    qid: int
    layer_id: int


class AssignLayerResponse(BaseModel):
    updated: int


class ReclassifyStartResponse(BaseModel):
    started: bool
    message: str


class ReclassifyStatusResponse(BaseModel):
    running: bool
    progress: int
    total_rules: int
    rules_applied: int
    classified: int
    error: str | None = None
    dirty: bool | None = None


# --- Match count ---

@router.get("/match-count", response_model=MatchCountResponse)
async def match_count(
    pattern: str,
    match_field: str = "title",
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Count distinct QIDs matching a pattern (ILIKE) on title or category."""
    if match_field not in ("title", "category"):
        raise HTTPException(status_code=400, detail="match_field must be 'title' or 'category'")
    col = LatestVuln.title if match_field == "title" else LatestVuln.category
    result = await db.execute(
        select(func.count(func.distinct(LatestVuln.qid)))
        .where(col.ilike(f"%{escape_like(pattern)}%"))
    )
    return MatchCountResponse(count=result.scalar_one())


# --- Layer CRUD ---

@router.get("", response_model=list[LayerResponse])
async def list_layers(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(VulnLayer).order_by(VulnLayer.position, VulnLayer.id)
    )
    layers = result.scalars().all()
    return [
        LayerResponse(id=l.id, name=l.name, color=l.color, position=l.position)
        for l in layers
    ]


@router.post("", response_model=LayerResponse, status_code=201)
async def create_layer(
    body: LayerCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    layer = VulnLayer(name=body.name, color=body.color, position=body.position)
    db.add(layer)
    await db.commit()
    await db.refresh(layer)
    _reclassify.dirty = True
    return LayerResponse(id=layer.id, name=layer.name, color=layer.color, position=layer.position)


@router.put("/assign", response_model=AssignLayerResponse)
async def assign_layer(
    body: AssignLayerRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Manually assign a layer to all occurrences of a QID."""
    # Verify layer exists
    layer = (await db.execute(select(VulnLayer).where(VulnLayer.id == body.layer_id))).scalar_one_or_none()
    if not layer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Layer not found")

    result = await db.execute(
        update(Vulnerability)
        .where(Vulnerability.qid == body.qid)
        .values(layer_id=body.layer_id)
    )
    await db.commit()

    await db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY latest_vulns"))
    await db.commit()

    from q2h.services.trend_snapshots import recompute_all_snapshots
    await recompute_all_snapshots(db)

    return AssignLayerResponse(updated=result.rowcount)


@router.put("/{layer_id}", response_model=LayerResponse)
async def update_layer(
    layer_id: int,
    body: LayerUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    result = await db.execute(select(VulnLayer).where(VulnLayer.id == layer_id))
    layer = result.scalar_one_or_none()
    if not layer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Layer not found")
    if body.name is not None:
        layer.name = body.name
    if body.color is not None:
        layer.color = body.color
    if body.position is not None:
        layer.position = body.position
    await db.commit()
    _reclassify.dirty = True
    return LayerResponse(id=layer.id, name=layer.name, color=layer.color, position=layer.position)


@router.delete("/{layer_id}", status_code=204)
async def delete_layer(
    layer_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    result = await db.execute(select(VulnLayer).where(VulnLayer.id == layer_id))
    layer = result.scalar_one_or_none()
    if not layer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Layer not found")
    # Nullify layer_id on vulnerabilities referencing this layer
    await db.execute(
        update(Vulnerability).where(Vulnerability.layer_id == layer_id).values(layer_id=None)
    )
    # Delete rules for this layer
    await db.execute(
        delete(VulnLayerRule).where(VulnLayerRule.layer_id == layer_id)
    )
    await db.delete(layer)
    await db.commit()
    # Refresh materialized view so dashboard reflects nullified layer_ids
    await db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY latest_vulns"))
    await db.commit()
    from q2h.services.trend_snapshots import recompute_all_snapshots
    await recompute_all_snapshots(db)
    _reclassify.dirty = True


# --- Rule CRUD ---

@router.get("/{layer_id}/rules", response_model=list[RuleResponse])
async def list_rules(
    layer_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    result = await db.execute(
        select(VulnLayerRule)
        .where(VulnLayerRule.layer_id == layer_id)
        .order_by(VulnLayerRule.created_at.desc())
    )
    rules = result.scalars().all()
    return [
        RuleResponse(id=r.id, layer_id=r.layer_id, match_field=r.match_field,
                     pattern=r.pattern, priority=r.priority,
                     created_at=r.created_at.isoformat() if r.created_at else None)
        for r in rules
    ]


@router.post("/{layer_id}/rules", response_model=RuleResponse, status_code=201)
async def create_rule(
    layer_id: int,
    body: RuleCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    # Verify layer exists
    result = await db.execute(select(VulnLayer).where(VulnLayer.id == layer_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Layer not found")
    rule = VulnLayerRule(
        layer_id=layer_id, match_field=body.match_field,
        pattern=body.pattern, priority=body.priority,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    _reclassify.dirty = True
    return RuleResponse(id=rule.id, layer_id=rule.layer_id, match_field=rule.match_field,
                        pattern=rule.pattern, priority=rule.priority,
                        created_at=rule.created_at.isoformat() if rule.created_at else None)


@router.put("/rules/{rule_id}", response_model=RuleResponse)
async def update_rule(
    rule_id: int,
    body: RuleUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    result = await db.execute(select(VulnLayerRule).where(VulnLayerRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    if body.layer_id is not None:
        # Verify target layer exists
        layer_check = await db.execute(select(VulnLayer).where(VulnLayer.id == body.layer_id))
        if not layer_check.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Layer not found")
        rule.layer_id = body.layer_id
    if body.match_field is not None:
        rule.match_field = body.match_field
    if body.pattern is not None:
        rule.pattern = body.pattern
    if body.priority is not None:
        rule.priority = body.priority
    await db.commit()
    _reclassify.dirty = True
    return RuleResponse(id=rule.id, layer_id=rule.layer_id, match_field=rule.match_field,
                        pattern=rule.pattern, priority=rule.priority,
                        created_at=rule.created_at.isoformat() if rule.created_at else None)


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    result = await db.execute(select(VulnLayerRule).where(VulnLayerRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    await db.delete(rule)
    await db.commit()
    _reclassify.dirty = True


# --- Reclassify (async with progress) ---

_BATCH_SIZE = 2000


async def _run_reclassify():
    """Background task that reclassifies all vulnerabilities.

    Optimised path: classify per unique QID in Python (title/category are
    QID-level properties), then batch-update all rows in a single pass.
    """
    state = _reclassify
    try:
        async with db_engine.SessionLocal() as db:
            # 1. Load rules ordered by created_at (newest first = first match wins)
            rules_result = await db.execute(
                select(VulnLayerRule).order_by(VulnLayerRule.created_at.desc())
            )
            rules = [
                (r.match_field, r.pattern.lower(), r.layer_id)
                for r in rules_result.scalars().all()
            ]
            state.total_rules = len(rules)

            if state.total_rules == 0:
                state.progress = 100
                state.running = False
                return

            state.progress = 5

            # 2. Fetch distinct QIDs with their title/category
            distinct_result = await db.execute(
                select(
                    Vulnerability.qid,
                    Vulnerability.title,
                    Vulnerability.category,
                ).distinct(Vulnerability.qid)
            )
            qid_rows = distinct_result.all()
            state.progress = 15

            # 3. Match rules in Python — first match wins per QID
            qid_to_layer: dict[int, int] = {}
            for qid, title_raw, category_raw in qid_rows:
                title_low = (title_raw or "").lower()
                cat_low = (category_raw or "").lower()
                for match_field, pattern_low, layer_id in rules:
                    value = title_low if match_field == "title" else cat_low
                    if pattern_low in value:
                        qid_to_layer[qid] = layer_id
                        break

            state.rules_applied = state.total_rules
            state.classified = len(qid_to_layer)
            state.progress = 25

            # 4. Reset all layer_ids
            await db.execute(update(Vulnerability).values(layer_id=None))
            state.progress = 35

            # 5. Batch UPDATE using VALUES join
            classified_items = list(qid_to_layer.items())
            total_batches = max(1, (len(classified_items) + _BATCH_SIZE - 1) // _BATCH_SIZE)

            for batch_idx in range(total_batches):
                start = batch_idx * _BATCH_SIZE
                batch = classified_items[start : start + _BATCH_SIZE]
                if not batch:
                    break
                # Build VALUES clause: (qid, layer_id), ...
                values_clause = ", ".join(
                    f"({qid}, {lid})" for qid, lid in batch
                )
                stmt = text(
                    f"UPDATE vulnerabilities v SET layer_id = m.lid "
                    f"FROM (VALUES {values_clause}) AS m(qid, lid) "
                    f"WHERE v.qid = m.qid"
                )
                await db.execute(stmt)
                state.progress = 35 + int(55 * (batch_idx + 1) / total_batches)

            await db.commit()
            state.progress = 92

            # 6. Refresh materialized view so dashboard reflects new layer_ids
            await db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY latest_vulns"))
            await db.commit()

            # 7. Recompute trend snapshots (layer dimension changed)
            from q2h.services.trend_snapshots import recompute_all_snapshots
            await recompute_all_snapshots(db)

            state.progress = 100
            state.dirty = False
    except Exception as e:
        logger.exception("Reclassify failed")
        state.error = str(e)
    finally:
        state.running = False


@router.post("/reclassify", response_model=ReclassifyStartResponse)
async def reclassify(
    user: dict = Depends(require_admin),
):
    if _reclassify.running:
        return ReclassifyStartResponse(started=False, message="RECLASSIFY_IN_PROGRESS")

    # Reset state
    _reclassify.running = True
    _reclassify.progress = 0
    _reclassify.total_rules = 0
    _reclassify.rules_applied = 0
    _reclassify.classified = 0
    _reclassify.error = None

    asyncio.create_task(_run_reclassify())
    return ReclassifyStartResponse(started=True, message="RECLASSIFY_STARTED")


@router.get("/reclassify/status", response_model=ReclassifyStatusResponse)
async def reclassify_status(
    user: dict = Depends(get_current_user),
):
    return ReclassifyStatusResponse(
        running=_reclassify.running,
        progress=_reclassify.progress,
        total_rules=_reclassify.total_rules,
        rules_applied=_reclassify.rules_applied,
        classified=_reclassify.classified,
        error=_reclassify.error,
        dirty=_reclassify.dirty,
    )


# --- Orphan (uncategorized) QIDs ---

class OrphanQid(BaseModel):
    qid: int
    title: str | None = None
    category: str | None = None
    type: str | None = None
    severity: int
    occurrences: int


@router.get("/orphans", response_model=list[OrphanQid])
async def list_orphans(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_data_access),
):
    """List distinct QIDs with no layer assigned."""
    result = await db.execute(
        select(
            LatestVuln.qid,
            LatestVuln.title,
            LatestVuln.category,
            LatestVuln.type,
            LatestVuln.severity,
            func.count().label("occurrences"),
        )
        .where(LatestVuln.layer_id.is_(None))
        .group_by(LatestVuln.qid, LatestVuln.title, LatestVuln.category, LatestVuln.type, LatestVuln.severity)
        .order_by(LatestVuln.severity.desc())
    )
    return [
        OrphanQid(qid=r.qid, title=r.title, category=r.category, type=r.type,
                  severity=r.severity, occurrences=r.occurrences)
        for r in result.all()
    ]
