"""Rule proposals — user-submitted categorization rules for admin review."""

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from q2h.auth.dependencies import require_admin, require_data_access
from q2h.db.engine import get_db
from q2h.db.models import (
    AuditLog,
    RuleProposal,
    VulnLayer,
    VulnLayerRule,
)

router = APIRouter(prefix="/api/rules/proposals", tags=["proposals"])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ProposalCreate(BaseModel):
    pattern: str
    match_field: str
    layer_id: int

    @field_validator("pattern")
    @classmethod
    def pattern_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Pattern must not be empty")
        if len(v) > 500:
            raise ValueError("Pattern too long (max 500)")
        return v

    @field_validator("match_field")
    @classmethod
    def match_field_valid(cls, v: str) -> str:
        if v not in ("title", "category"):
            raise ValueError("match_field must be 'title' or 'category'")
        return v


class ProposalResponse(BaseModel):
    id: int
    pattern: str
    match_field: str
    layer_id: int
    layer_name: str | None = None
    status: str
    admin_comment: str | None = None
    created_at: datetime
    reviewed_at: datetime | None = None

    class Config:
        from_attributes = True


class ProposalAdminResponse(ProposalResponse):
    user_id: int | None = None
    user_username: str | None = None
    user_first_name: str | None = None
    user_last_name: str | None = None
    reviewed_by: int | None = None


class ApproveBody(BaseModel):
    pattern: str | None = None
    match_field: str | None = None
    layer_id: int | None = None
    comment: str | None = None

    @field_validator("pattern")
    @classmethod
    def pattern_not_empty(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Pattern must not be empty")
        return v

    @field_validator("match_field")
    @classmethod
    def match_field_valid(cls, v: str | None) -> str | None:
        if v is not None and v not in ("title", "category"):
            raise ValueError("match_field must be 'title' or 'category'")
        return v


class RejectBody(BaseModel):
    comment: str | None = None


class PendingCountResponse(BaseModel):
    count: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_response(p: RuleProposal) -> ProposalResponse:
    return ProposalResponse(
        id=p.id,
        pattern=p.pattern,
        match_field=p.match_field,
        layer_id=p.layer_id,
        layer_name=p.layer.name if p.layer else None,
        status=p.status,
        admin_comment=p.admin_comment,
        created_at=p.created_at,
        reviewed_at=p.reviewed_at,
    )


def _to_admin_response(p: RuleProposal) -> ProposalAdminResponse:
    return ProposalAdminResponse(
        id=p.id,
        pattern=p.pattern,
        match_field=p.match_field,
        layer_id=p.layer_id,
        layer_name=p.layer.name if p.layer else None,
        status=p.status,
        admin_comment=p.admin_comment,
        created_at=p.created_at,
        reviewed_at=p.reviewed_at,
        user_id=p.user_id,
        user_username=p.user.username if p.user else None,
        user_first_name=p.user.first_name if p.user else None,
        user_last_name=p.user.last_name if p.user else None,
        reviewed_by=p.reviewed_by,
    )


# ---------------------------------------------------------------------------
# User endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=ProposalResponse, status_code=201)
async def create_proposal(
    body: ProposalCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_data_access),
):
    # Verify layer exists
    layer = (
        await db.execute(select(VulnLayer).where(VulnLayer.id == body.layer_id))
    ).scalar_one_or_none()
    if not layer:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "LAYER_NOT_FOUND")

    # Duplicate check
    dup = (
        await db.execute(
            select(RuleProposal.id).where(
                RuleProposal.pattern == body.pattern,
                RuleProposal.match_field == body.match_field,
                RuleProposal.layer_id == body.layer_id,
                RuleProposal.status == "pending",
            )
        )
    ).scalar()
    if dup:
        raise HTTPException(status.HTTP_409_CONFLICT, "DUPLICATE_PROPOSAL")

    uid = int(user["sub"])
    proposal = RuleProposal(
        user_id=uid,
        layer_id=body.layer_id,
        pattern=body.pattern,
        match_field=body.match_field,
        created_at=_now(),
    )
    db.add(proposal)

    db.add(
        AuditLog(
            user_id=uid,
            action="proposal_create",
            detail=f"pattern={body.pattern}, match_field={body.match_field}, layer_id={body.layer_id}",
        )
    )
    await db.commit()
    await db.refresh(proposal, ["layer"])
    return _to_response(proposal)


@router.get("/mine", response_model=list[ProposalResponse])
async def my_proposals(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_data_access),
):
    rows = (
        await db.execute(
            select(RuleProposal)
            .options(joinedload(RuleProposal.layer))
            .where(RuleProposal.user_id == int(user["sub"]))
            .order_by(RuleProposal.created_at.desc())
        )
    ).scalars().unique().all()
    return [_to_response(p) for p in rows]


@router.delete("/{proposal_id}", status_code=204)
async def cancel_proposal(
    proposal_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_data_access),
):
    proposal = (
        await db.execute(
            select(RuleProposal).where(RuleProposal.id == proposal_id)
        )
    ).scalar_one_or_none()
    if not proposal:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "PROPOSAL_NOT_FOUND")
    uid = int(user["sub"])
    if proposal.user_id != uid:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "NOT_OWNER")
    if proposal.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "PROPOSAL_NOT_PENDING")

    db.add(
        AuditLog(
            user_id=uid,
            action="proposal_cancel",
            detail=f"proposal_id={proposal_id}",
        )
    )
    await db.delete(proposal)
    await db.commit()


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[ProposalAdminResponse])
async def list_proposals(
    status_filter: Literal["pending", "approved", "rejected"] | None = None,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    q = select(RuleProposal).options(
        joinedload(RuleProposal.layer), joinedload(RuleProposal.user)
    )
    if status_filter:
        q = q.where(RuleProposal.status == status_filter)
    q = q.order_by(RuleProposal.created_at.desc())
    rows = (await db.execute(q)).scalars().unique().all()
    return [_to_admin_response(p) for p in rows]


@router.get("/pending/count", response_model=PendingCountResponse)
async def pending_count(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    count = (
        await db.execute(
            select(func.count())
            .select_from(RuleProposal)
            .where(RuleProposal.status == "pending")
        )
    ).scalar() or 0
    return PendingCountResponse(count=count)


@router.put("/{proposal_id}/approve", response_model=ProposalAdminResponse)
async def approve_proposal(
    proposal_id: int,
    body: ApproveBody,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    # SELECT FOR UPDATE — use selectinload (separate queries) to avoid
    # "FOR UPDATE cannot be applied to the nullable side of an outer join"
    proposal = (
        await db.execute(
            select(RuleProposal)
            .options(selectinload(RuleProposal.layer), selectinload(RuleProposal.user))
            .where(RuleProposal.id == proposal_id)
            .with_for_update()
        )
    ).scalars().unique().one_or_none()
    if not proposal:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "PROPOSAL_NOT_FOUND")
    if proposal.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "PROPOSAL_ALREADY_REVIEWED")

    # Use modified values or originals
    final_pattern = body.pattern if body.pattern is not None else proposal.pattern
    final_match_field = (
        body.match_field if body.match_field is not None else proposal.match_field
    )
    final_layer_id = body.layer_id if body.layer_id is not None else proposal.layer_id

    # Verify final layer exists (if changed)
    if body.layer_id is not None:
        layer = (
            await db.execute(select(VulnLayer).where(VulnLayer.id == final_layer_id))
        ).scalar_one_or_none()
        if not layer:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "LAYER_NOT_FOUND")

    # Create rule
    rule = VulnLayerRule(
        layer_id=final_layer_id,
        match_field=final_match_field,
        pattern=final_pattern,
        priority=0,  # deprecated, keep default
        created_at=_now(),
    )
    db.add(rule)
    await db.flush()  # get rule.id

    # Update proposal
    admin_id = int(admin["sub"])
    proposal.status = "approved"
    proposal.admin_comment = body.comment
    proposal.reviewed_at = _now()
    proposal.reviewed_by = admin_id
    proposal.applied_rule_id = rule.id

    db.add(
        AuditLog(
            user_id=admin_id,
            action="proposal_approve",
            detail=f"proposal_id={proposal_id}, rule_id={rule.id}, pattern={final_pattern}",
        )
    )
    await db.commit()

    # Mark reclassification as needed (admin triggers it manually when done reviewing)
    try:
        from q2h.api.layers import _reclassify
        _reclassify.dirty = True
    except ImportError:
        pass

    await db.refresh(proposal, ["layer", "user"])
    return _to_admin_response(proposal)


@router.put("/{proposal_id}/reject", response_model=ProposalAdminResponse)
async def reject_proposal(
    proposal_id: int,
    body: RejectBody,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    proposal = (
        await db.execute(
            select(RuleProposal)
            .options(selectinload(RuleProposal.layer), selectinload(RuleProposal.user))
            .where(RuleProposal.id == proposal_id)
            .with_for_update()
        )
    ).scalars().unique().one_or_none()
    if not proposal:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "PROPOSAL_NOT_FOUND")
    if proposal.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "PROPOSAL_ALREADY_REVIEWED")

    admin_id = int(admin["sub"])
    proposal.status = "rejected"
    proposal.admin_comment = body.comment
    proposal.reviewed_at = _now()
    proposal.reviewed_by = admin_id

    db.add(
        AuditLog(
            user_id=admin_id,
            action="proposal_reject",
            detail=f"proposal_id={proposal_id}",
        )
    )
    await db.commit()
    await db.refresh(proposal, ["layer", "user"])
    return _to_admin_response(proposal)
