from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.database.db import get_db
from app.auth.deps import require_superuser, require_platform_user
from app.users.models import User
from app.services.health_service import PlatformIssue

router = APIRouter(prefix="/admin/issues", tags=["Issues Tracker"])

_VALID_SEVERITIES = ("critical", "high", "medium", "low")
_VALID_STATUSES = ("open", "in_progress", "resolved")


class CreateIssueRequest(BaseModel):
    title: str
    description: Optional[str] = None
    severity: str = "high"
    affected_area: Optional[str] = None
    tenant_id: Optional[int] = None
    assigned_to: Optional[str] = None


class UpdateIssueRequest(BaseModel):
    status: Optional[str] = None
    severity: Optional[str] = None
    diagnosis: Optional[str] = None
    fix_applied: Optional[str] = None
    assigned_to: Optional[str] = None


def _fmt(i: PlatformIssue) -> dict:
    return {
        "id": i.id,
        "title": i.title,
        "description": i.description,
        "severity": i.severity,
        "status": i.status,
        "affected_area": i.affected_area,
        "tenant_id": i.tenant_id,
        "assigned_to": i.assigned_to,
        "diagnosis": i.diagnosis,
        "fix_applied": i.fix_applied,
        "resolved_at": str(i.resolved_at) if i.resolved_at else None,
        "created_at": str(i.created_at),
        "updated_at": str(i.updated_at),
    }


@router.get("/")
async def list_issues(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_platform_user),
):
    """List platform issues. Platform staff only."""
    query = db.query(PlatformIssue).order_by(desc(PlatformIssue.created_at))
    if status:
        query = query.filter(PlatformIssue.status == status)
    if severity:
        query = query.filter(PlatformIssue.severity == severity)
    return [_fmt(i) for i in query.limit(limit).all()]


@router.post("/")
async def create_issue(
    payload: CreateIssueRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superuser),
):
    """Create a new platform issue manually. Superuser only."""
    if payload.severity not in _VALID_SEVERITIES:
        raise HTTPException(400, f"severity must be one of: {', '.join(_VALID_SEVERITIES)}")
    issue = PlatformIssue(
        title=payload.title,
        description=payload.description,
        severity=payload.severity,
        affected_area=payload.affected_area,
        tenant_id=payload.tenant_id,
        assigned_to=payload.assigned_to,
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)
    return _fmt(issue)


@router.patch("/{issue_id}")
async def update_issue(
    issue_id: int,
    payload: UpdateIssueRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_platform_user),
):
    """Update issue status, diagnosis, or notes. Platform staff only."""
    issue = db.query(PlatformIssue).filter(PlatformIssue.id == issue_id).first()
    if not issue:
        raise HTTPException(404, "Issue not found")
    if payload.status is not None:
        if payload.status not in _VALID_STATUSES:
            raise HTTPException(400, f"status must be one of: {', '.join(_VALID_STATUSES)}")
        issue.status = payload.status
    if payload.severity is not None:
        if payload.severity not in _VALID_SEVERITIES:
            raise HTTPException(400, f"severity must be one of: {', '.join(_VALID_SEVERITIES)}")
        issue.severity = payload.severity
    if payload.diagnosis is not None:
        issue.diagnosis = payload.diagnosis
    if payload.fix_applied is not None:
        issue.fix_applied = payload.fix_applied
    if payload.assigned_to is not None:
        issue.assigned_to = payload.assigned_to
    db.commit()
    db.refresh(issue)
    return _fmt(issue)


@router.post("/{issue_id}/resolve")
async def resolve_issue(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superuser),
):
    """Mark an issue resolved. Superuser only."""
    issue = db.query(PlatformIssue).filter(PlatformIssue.id == issue_id).first()
    if not issue:
        raise HTTPException(404, "Issue not found")
    issue.status = "resolved"
    issue.resolved_at = datetime.utcnow()
    db.commit()
    return {"success": True, "message": f"Issue #{issue_id} marked resolved."}
