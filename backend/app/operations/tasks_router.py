"""
EST8GO FOLLOW-UP TASK API
==========================
Reads and actions the queue written by followup_service.py.

SECURITY
--------
Every endpoint resolves the tenant from `current_user.tenant_id` and never
from a client-supplied value, per the tenant-isolation rules. A task that
exists but belongs to another tenant returns 403, not 404 — 404 would leak
whether that task id exists at all.

Within a tenant, authority follows the role:
    admin / platform staff  — every task in the tenant
    everyone else           — tasks assigned to them, or unassigned

Unassigned tasks are deliberately actionable by anyone in the tenant. The
sweep leaves a task unassigned when it cannot identify an owner, and a
shared queue that anyone can pick up beats a task silently parked on the
wrong person.

WHY /opened EXISTS AND WHAT IT IS NOT
------------------------------------
The agent messages the buyer from their PERSONAL WhatsApp, so the reply
lands on their phone and Kora never sees it. The platform therefore cannot
know whether contact actually happened — only that a button was tapped.
/opened records exactly that and DOES NOT close the task. "Mark done" stays
a deliberate human act, and the UI says so.
"""

import logging
import urllib.parse
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.database.audit import AuditLog
from app.database.db import get_db
from app.listings.models import Listing, ListingImage
from app.users.models import User
from app.operations.models import (
    FollowUpTask,
    STATUS_OPEN,
    STATUS_DONE,
    STATUS_DISMISSED,
    CLOSED_STATUSES,
    DISMISS_REASONS,
    REASON_CONTACTED,
)
from app.operations.followup_service import close_sibling_tasks

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["Follow-up Tasks"])

_ADMIN_ROLES = ("superuser", "super_staff", "admin")


class DismissRequest(BaseModel):
    reason: str = Field(..., description="One of DISMISS_REASONS")
    note: Optional[str] = Field(None, max_length=1000)


class AssignTaskRequest(BaseModel):
    """The staff member an agency manager has chosen to own a task."""

    assignee_id: int = Field(..., ge=1)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _tenant_id(current_user: User) -> int:
    """The caller's tenant, or 403. Never read from a header."""
    tid = current_user.tenant_id
    if not tid:
        raise HTTPException(
            status_code=403,
            detail="No tenant associated with this account",
        )
    return tid


def _is_admin(current_user: User) -> bool:
    return current_user.effective_role in _ADMIN_ROLES


def _assignment_snapshot(user: User | None) -> dict | None:
    """Small, non-sensitive snapshot stored in the immutable audit event."""
    if user is None:
        return None
    return {
        "id": user.id,
        "name": user.first_name or (user.email or "").split("@")[0],
        "email": user.email,
    }


def _record_assignment_audit(
    db: Session,
    *,
    actor: User,
    task: FollowUpTask,
    action: str,
    previous_assignee: User | None,
    new_assignee: User,
) -> None:
    """Keep manager assignment and self-claim decisions auditable."""
    db.add(
        AuditLog(
            actor_id=actor.id,
            actor_email=actor.email,
            actor_role=actor.effective_role,
            action=action,
            target_table="followup_tasks",
            target_id=task.id,
            old_value={"assignee": _assignment_snapshot(previous_assignee)},
            new_value={"assignee": _assignment_snapshot(new_assignee)},
        )
    )


def _wa_url(phone, text) -> str:
    """A ready-to-tap wa.me link, or "" when the number is unusable.

    Digits only, no "+", leading 0 -> 234 — the same normalisation
    email_service.wa_link() applies, reused rather than reimplemented so
    the two cannot drift.
    """
    from app.services.email_service import wa_link

    base = wa_link(phone)
    if not base:
        return ""
    if not text:
        return base
    return f"{base}?text={urllib.parse.quote(text)}"


def _user_label(db: Session, user_id, cache: dict):
    if not user_id:
        return None
    if user_id in cache:
        return cache[user_id]
    u = db.get(User, user_id)
    # Staff-facing, so the email local-part IS an acceptable fallback here
    # — unlike the buyer-facing opener, where it produced "this is admin
    # from Bravehomes Ltd".
    label = None
    if u:
        label = {
            "id": u.id,
            "name": u.first_name or (u.email or "").split("@")[0] or f"User {u.id}",
        }
    cache[user_id] = label
    return label


def _listing_brief(db: Session, listing_id, cache: dict):
    if not listing_id:
        return None
    if listing_id in cache:
        return cache[listing_id]
    lst = db.get(Listing, listing_id)
    brief = None
    if lst:
        img = (
            db.query(ListingImage)
            .filter(ListingImage.listing_id == lst.id)
            .order_by(ListingImage.is_main.desc(), ListingImage.id.asc())
            .first()
        )
        brief = {
            "id": lst.id,
            "title": lst.title,
            "location": (lst.location or "").title(),
            "price": lst.price,
            "price_display": f"₦{int(lst.price):,}" if lst.price else "",
            "trust_score": lst.trust_score or 0,
            "trust_grade": lst.trust_grade or "ungraded",
            "image_url": img.url if img else None,
        }
    cache[listing_id] = brief
    return brief


def _fmt(db: Session, t: FollowUpTask, ucache: dict, lcache: dict) -> dict:
    _n = _now()
    _quiet_h = None
    if t.quiet_since:
        _quiet_h = (_n - t.quiet_since).total_seconds() / 3600.0

    return {
        "id": t.id,
        "tier": t.tier,
        "kind": t.kind,
        "status": t.status,
        "outcome_reason": t.outcome_reason,
        "outcome_note": t.outcome_note,

        "buyer_name": t.buyer_name,
        "buyer_phone": t.buyer_phone,
        "funnel_stage": t.funnel_stage,
        "lead_score": t.lead_score or 0,
        "priority_value": int(t.priority_value or 0),
        "priority_value_display": (
            f"₦{int(t.priority_value):,}" if t.priority_value else ""
        ),

        "quiet_since": str(t.quiet_since) if t.quiet_since else None,
        "hours_quiet": round(_quiet_h, 1) if _quiet_h is not None else None,
        "days_quiet": int(_quiet_h // 24) if _quiet_h is not None else None,

        "due_at": str(t.due_at) if t.due_at else None,
        "is_overdue": bool(
            t.status == STATUS_OPEN and t.due_at and t.due_at < _n
        ),
        "hours_overdue": (
            round((_n - t.due_at).total_seconds() / 3600.0, 1)
            if (t.status == STATUS_OPEN and t.due_at and t.due_at < _n)
            else 0
        ),

        "suggested_message": t.suggested_message,
        # Built server-side so the dashboard never reimplements the
        # 0 -> 234 normalisation.
        "wa_url": _wa_url(t.buyer_phone, t.suggested_message),

        "listing": _listing_brief(db, t.listing_id, lcache),
        "assigned_to": _user_label(db, t.assigned_user_id, ucache),
        "escalated_from": _user_label(db, t.escalated_from_id, ucache),
        "parent_task_id": t.parent_task_id,

        "conversation_id": t.conversation_id,
        "created_at": str(t.created_at) if t.created_at else None,
        "opened_at": str(t.opened_at) if t.opened_at else None,
        "closed_at": str(t.closed_at) if t.closed_at else None,
    }


def _load_task(db: Session, task_id: int, current_user: User) -> FollowUpTask:
    """Fetch a task the caller is allowed to ACT on, or raise.

    404 only when the task genuinely does not exist. A task belonging to
    another tenant raises 403 — returning 404 there would confirm or deny
    the id's existence across the tenant boundary.
    """
    tid = _tenant_id(current_user)
    task = db.get(FollowUpTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.tenant_id != tid:
        raise HTTPException(status_code=403, detail="Not your tenant's task")
    if not _is_admin(current_user):
        if task.assigned_user_id not in (None, current_user.id):
            raise HTTPException(
                status_code=403,
                detail="This follow-up is assigned to someone else",
            )
    return task


# ================================================================
# READS
# ================================================================


@router.get("")
@router.get("/")
async def list_tasks(
    scope: str = Query("mine", pattern="^(mine|team|escalated|exceptions|unassigned)$"),
    status: str = Query("open"),
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    scope:
      mine       — assigned to me (the realtor's default view)
      unassigned — nobody owns it yet; anyone in the tenant may claim it
      team       — everything in the tenant (admin only)
      escalated  — tier 2 escalations assigned to me (supervisor view)
      exceptions — tier 3, the owner's view (admin only)
    """
    tid = _tenant_id(current_user)
    q = db.query(FollowUpTask).filter(FollowUpTask.tenant_id == tid)

    if status != "all":
        if status == "closed":
            q = q.filter(FollowUpTask.status.in_(CLOSED_STATUSES))
        else:
            q = q.filter(FollowUpTask.status == status)

    if scope == "mine":
        q = q.filter(FollowUpTask.assigned_user_id == current_user.id)
    elif scope == "unassigned":
        q = q.filter(FollowUpTask.assigned_user_id.is_(None))
    elif scope == "escalated":
        q = q.filter(
            FollowUpTask.tier == 2,
            FollowUpTask.assigned_user_id == current_user.id,
        )
    elif scope in ("team", "exceptions"):
        # Whole-tenant views are for admins. A realtor asking for "team"
        # gets their own tasks rather than a 403: the dashboard shows the
        # segment to everyone, and silently narrowing is friendlier than
        # an error for a view they simply cannot populate.
        if not _is_admin(current_user):
            q = q.filter(FollowUpTask.assigned_user_id == current_user.id)
        if scope == "exceptions":
            q = q.filter(FollowUpTask.tier == 3)

    # Ordered by LEAD VALUE, not age. An agent who reads only the first
    # row should be acting on the most valuable lead, not the oldest.
    # Overdue first, then value, then age.
    tasks = (
        q.order_by(
            FollowUpTask.due_at.asc(),
            FollowUpTask.priority_value.desc(),
            FollowUpTask.lead_score.desc(),
        )
        .limit(limit)
        .all()
    )

    _uc: dict = {}
    _lc: dict = {}
    return {
        "count": len(tasks),
        "scope": scope,
        "status": status,
        "tasks": [_fmt(db, t, _uc, _lc) for t in tasks],
    }


@router.get("/summary")
async def task_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Badge counts for the Operations tab."""
    tid = _tenant_id(current_user)
    _n = _now()
    base = db.query(FollowUpTask).filter(
        FollowUpTask.tenant_id == tid,
        FollowUpTask.status == STATUS_OPEN,
    )
    mine = base.filter(FollowUpTask.assigned_user_id == current_user.id)

    return {
        "mine": mine.count(),
        "mine_overdue": mine.filter(FollowUpTask.due_at < _n).count(),
        "unassigned": base.filter(
            FollowUpTask.assigned_user_id.is_(None)
        ).count(),
        "escalated_to_me": base.filter(
            FollowUpTask.tier == 2,
            FollowUpTask.assigned_user_id == current_user.id,
        ).count(),
        "team_open": base.count() if _is_admin(current_user) else None,
        "exceptions": (
            base.filter(FollowUpTask.tier == 3).count()
            if _is_admin(current_user) else None
        ),
        "is_admin": _is_admin(current_user),
    }


@router.get("/insights")
async def task_insights(
    days: int = Query(90, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Why leads die — the owner's number, which no Nigerian agency
    currently has. Admin only: it aggregates the whole tenant."""
    tid = _tenant_id(current_user)
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required.")

    from datetime import timedelta
    since = _now() - timedelta(days=days)

    rows = (
        db.query(
            FollowUpTask.outcome_reason,
            func.count(FollowUpTask.id),
            func.coalesce(func.sum(FollowUpTask.priority_value), 0),
        )
        .filter(
            FollowUpTask.tenant_id == tid,
            FollowUpTask.status.in_(CLOSED_STATUSES),
            FollowUpTask.closed_at >= since,
            FollowUpTask.outcome_reason.isnot(None),
        )
        .group_by(FollowUpTask.outcome_reason)
        .all()
    )
    total = sum(r[1] for r in rows) or 0

    return {
        "days": days,
        "total_closed": total,
        "breakdown": [
            {
                "reason": r[0],
                "count": r[1],
                "pct": round(r[1] * 100.0 / total, 1) if total else 0,
                "value": int(r[2] or 0),
                "value_display": f"₦{int(r[2] or 0):,}",
            }
            for r in sorted(rows, key=lambda x: -x[1])
        ],
    }


# ================================================================
# ACTIONS
# ================================================================


@router.get("/{task_id}/assignment-history")
async def assignment_history(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the immutable record of who assigned this task and when."""
    task = _load_task(db, task_id, current_user)
    history = (
        db.query(AuditLog)
        .filter(
            AuditLog.target_table == "followup_tasks",
            AuditLog.target_id == task.id,
            AuditLog.action.in_(("task_assigned", "task_reassigned", "task_claimed")),
        )
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .all()
    )
    return {
        "task_id": task.id,
        "history": [
            {
                "action": event.action,
                "actor": {
                    "id": event.actor_id,
                    "name": event.actor_email or "Unknown user",
                    "role": event.actor_role,
                },
                "from": event.old_value or {},
                "to": event.new_value or {},
                "at": str(event.created_at) if event.created_at else None,
            }
            for event in history
        ],
    }


@router.post("/{task_id}/assign")
async def assign_task(
    task_id: int,
    payload: AssignTaskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Let an agency manager assign or reassign an open task deliberately."""
    tenant_id = _tenant_id(current_user)
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required.")

    task = _load_task(db, task_id, current_user)
    if task.status != STATUS_OPEN:
        raise HTTPException(status_code=409, detail=f"Task is {task.status}")

    assignee = (
        db.query(User)
        .filter(
            User.id == payload.assignee_id,
            User.tenant_id == tenant_id,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
        .first()
    )
    if assignee is None:
        raise HTTPException(
            status_code=400,
            detail="Choose an active staff member from your agency.",
        )

    previous_id = task.assigned_user_id
    previous_assignee = db.get(User, previous_id) if previous_id else None
    if previous_id == assignee.id:
        return {
            "status": "ok",
            "task_id": task.id,
            "already_assigned": True,
            "assigned_to": _assignment_snapshot(assignee),
        }

    # Compare the assignment we read with the row at write time. This prevents
    # a manager from overwriting a staff member who claimed the task a moment ago.
    assignment_query = db.query(FollowUpTask).filter(
        FollowUpTask.id == task.id,
        FollowUpTask.tenant_id == tenant_id,
        FollowUpTask.status == STATUS_OPEN,
    )
    if previous_id is None:
        assignment_query = assignment_query.filter(FollowUpTask.assigned_user_id.is_(None))
    else:
        assignment_query = assignment_query.filter(FollowUpTask.assigned_user_id == previous_id)

    changed = assignment_query.update(
        {
            FollowUpTask.assigned_user_id: assignee.id,
            FollowUpTask.updated_at: _now(),
        },
        synchronize_session=False,
    )
    if changed != 1:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This task changed before it could be assigned. Refresh and try again.",
        )

    _record_assignment_audit(
        db,
        actor=current_user,
        task=task,
        action="task_assigned" if previous_id is None else "task_reassigned",
        previous_assignee=previous_assignee,
        new_assignee=assignee,
    )
    db.commit()

    logger.info(
        "TASK ASSIGNED: task=%s tenant=%s from_user=%s to_user=%s by_user=%s",
        task.id,
        tenant_id,
        previous_id,
        assignee.id,
        current_user.id,
    )
    return {
        "status": "ok",
        "task_id": task.id,
        "already_assigned": False,
        "assigned_to": _assignment_snapshot(assignee),
    }


@router.post("/{task_id}/opened")
async def mark_opened(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record that the agent tapped through to WhatsApp.

    This is a BEACON, not a completion. It deliberately does not change
    `status`, stop the SLA clock, or trigger escalation logic — the agent's
    conversation happens on their personal phone where Kora cannot see it,
    so tapping a button is the only thing the platform actually observed.
    """
    task = _load_task(db, task_id, current_user)
    if task.opened_at is None:
        task.opened_at = _now()
        db.commit()
    return {
        "status": "ok",
        "opened_at": str(task.opened_at),
        "task_status": task.status,
        "note": "Opened in WhatsApp. The follow-up stays open until you mark it done.",
    }


@router.post("/{task_id}/done")
async def mark_done(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The agent actually followed up."""
    task = _load_task(db, task_id, current_user)
    if task.status in CLOSED_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Task already {task.status}",
        )

    _n = _now()
    task.status = STATUS_DONE
    task.outcome_reason = REASON_CONTACTED
    task.closed_at = _n
    task.closed_by_id = current_user.id

    # Answering the tier-1 task answers the escalation sitting in the
    # admin's queue too — otherwise the supervisor chases something
    # already handled.
    _siblings = close_sibling_tasks(
        db, task, STATUS_DONE, REASON_CONTACTED, closed_by_id=current_user.id
    )
    db.commit()

    logger.info(
        f"✅ FOLLOWUP DONE: task={task.id} tenant={task.tenant_id} "
        f"by_user={current_user.id} siblings_closed={_siblings}"
    )
    return {
        "status": "ok",
        "task_id": task.id,
        "siblings_closed": _siblings,
    }


@router.post("/{task_id}/dismiss")
async def dismiss_task(
    task_id: int,
    payload: DismissRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Close a follow-up WITH A REASON.

    The reason is mandatory and constrained to a short list. Two seconds
    for the agent; for the owner it is the only dataset that answers "why
    do our leads actually die" — which is why free text is an optional
    note beside the reason rather than a replacement for it.
    """
    if payload.reason not in DISMISS_REASONS:
        raise HTTPException(
            status_code=400,
            detail=f"reason must be one of: {', '.join(DISMISS_REASONS)}",
        )

    task = _load_task(db, task_id, current_user)
    if task.status in CLOSED_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Task already {task.status}",
        )

    _n = _now()
    task.status = STATUS_DISMISSED
    task.outcome_reason = payload.reason
    task.outcome_note = (payload.note or "").strip() or None
    task.closed_at = _n
    task.closed_by_id = current_user.id

    _siblings = close_sibling_tasks(
        db, task, STATUS_DISMISSED, payload.reason, closed_by_id=current_user.id
    )
    db.commit()

    logger.info(
        f"🚫 FOLLOWUP DISMISSED: task={task.id} tenant={task.tenant_id} "
        f"reason={payload.reason} by_user={current_user.id} "
        f"siblings_closed={_siblings}"
    )
    return {
        "status": "ok",
        "task_id": task.id,
        "reason": payload.reason,
        "siblings_closed": _siblings,
    }


@router.post("/{task_id}/claim")
async def claim_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Take ownership of an unassigned task.

    Without this, a task the sweep could not attribute sits in the shared
    pool with nobody accountable — which is the exact failure this whole
    feature exists to remove.
    """
    task = _load_task(db, task_id, current_user)
    if task.status != STATUS_OPEN:
        raise HTTPException(status_code=409, detail=f"Task is {task.status}")
    # One conditional UPDATE is the ownership decision. A read-then-write
    # sequence lets two staff members both believe they claimed the same task.
    claimed = (
        db.query(FollowUpTask)
        .filter(
            FollowUpTask.id == task.id,
            FollowUpTask.tenant_id == task.tenant_id,
            FollowUpTask.status == STATUS_OPEN,
            FollowUpTask.assigned_user_id.is_(None),
        )
        .update(
            {
                FollowUpTask.assigned_user_id: current_user.id,
                FollowUpTask.updated_at: _now(),
            },
            synchronize_session=False,
        )
    )
    if claimed != 1:
        db.rollback()
        db.expire_all()
        current_task = db.get(FollowUpTask, task.id)
        if current_task and current_task.assigned_user_id == current_user.id:
            return {"status": "ok", "task_id": task.id, "already_yours": True}
        if current_task and current_task.status != STATUS_OPEN:
            raise HTTPException(status_code=409, detail=f"Task is {current_task.status}")
        raise HTTPException(status_code=409, detail="Already claimed by someone else")

    _record_assignment_audit(
        db,
        actor=current_user,
        task=task,
        action="task_claimed",
        previous_assignee=None,
        new_assignee=current_user,
    )
    db.commit()
    logger.info(
        f"🙋 FOLLOWUP CLAIMED: task={task.id} by_user={current_user.id}"
    )
    return {"status": "ok", "task_id": task.id, "already_yours": False}
