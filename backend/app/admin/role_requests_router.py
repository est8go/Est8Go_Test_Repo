import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database.db import get_db
from app.auth.models import RoleChangeRequest
from app.users.models import User
from app.auth.deps import get_current_user, require_superuser
from app.core.security import verify_password
from app.services.email_service import (
    send_role_change_request,
    send_role_change_approved,
    send_role_change_rejected,
)

router = APIRouter(prefix="/admin/role-requests", tags=["Role Requests"])
BASE_URL = os.getenv("BASE_URL", "https://est8go-api.onrender.com")


class RoleRequestBody(BaseModel):
    requested_role: str
    reason: str
    expiry_hours: int = 24


class ApproveBody(BaseModel):
    password: str


@router.post("")
def create_role_request(
    body: RoleRequestBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    allowed = ["superuser", "super_staff"]
    if body.requested_role not in allowed:
        raise HTTPException(400, "Invalid role")
    if body.requested_role == current_user.role:
        raise HTTPException(400, "You already have this role")
    if body.expiry_hours > 168:
        raise HTTPException(400, "Maximum elevation is 7 days (168 hours)")

    existing = db.query(RoleChangeRequest).filter(
        RoleChangeRequest.requester_id == current_user.id,
        RoleChangeRequest.status       == "pending",
    ).first()
    if existing:
        raise HTTPException(400, "You already have a pending request")

    req = RoleChangeRequest(
        requester_id   = current_user.id,
        current_role   = current_user.role,
        requested_role = body.requested_role,
        reason         = body.reason,
        expiry_hours   = body.expiry_hours,
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    superusers = db.query(User).filter(
        User.role            == "superuser",
        User.is_active       == True,
        User.is_platform_user == True,
    ).all()

    approve_url = f"{BASE_URL}/public/super-admin-portal"
    for su in superusers:
        send_role_change_request(
            admin_email     = su.email,
            requester_name  = current_user.email.split("@")[0].title(),
            requester_email = current_user.email,
            requested_role  = body.requested_role,
            approve_url     = approve_url,
            reject_url      = approve_url,
        )

    return {"success": True, "message": "Request submitted. Awaiting approval."}


@router.get("")
def list_role_requests(
    db: Session = Depends(get_db),
    _: User = Depends(require_superuser),
):
    requests = db.query(RoleChangeRequest).filter(
        RoleChangeRequest.status == "pending"
    ).order_by(RoleChangeRequest.created_at.desc()).all()

    result = []
    for r in requests:
        requester = db.query(User).filter(User.id == r.requester_id).first()
        result.append({
            "id":              r.id,
            "requester_email": requester.email if requester else "—",
            "requester_name":  requester.email.split("@")[0].title() if requester else "—",
            "current_role":    r.current_role,
            "requested_role":  r.requested_role,
            "reason":          r.reason,
            "expiry_hours":    r.expiry_hours,
            "created_at":      r.created_at.isoformat() if r.created_at else None,
        })
    return result


@router.post("/{request_id}/approve")
def approve_role_request(
    request_id: int,
    body: ApproveBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superuser),
):
    if not verify_password(body.password, current_user.hashed_password):
        raise HTTPException(403, "Incorrect password. Approval denied.")

    req = db.query(RoleChangeRequest).filter(
        RoleChangeRequest.id     == request_id,
        RoleChangeRequest.status == "pending",
    ).first()
    if not req:
        raise HTTPException(404, "Request not found or already actioned")

    requester = db.query(User).filter(User.id == req.requester_id).first()
    if not requester:
        raise HTTPException(404, "Requester not found")

    now        = datetime.utcnow()
    expires_at = now + timedelta(hours=req.expiry_hours)

    req.status       = "approved"
    req.approved_by  = current_user.id
    req.activated_at = now
    req.expires_at   = expires_at
    req.actioned_at  = now

    requester.role            = req.requested_role
    requester.role_expires_at = expires_at
    requester.previous_role   = req.current_role

    db.commit()

    name = requester.email.split("@")[0].title()
    send_role_change_approved(requester.email, name, req.requested_role, req.expiry_hours)

    return {"success": True, "message": f"Role elevated to {req.requested_role}"}


@router.post("/{request_id}/reject")
def reject_role_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superuser),
):
    req = db.query(RoleChangeRequest).filter(
        RoleChangeRequest.id     == request_id,
        RoleChangeRequest.status == "pending",
    ).first()
    if not req:
        raise HTTPException(404, "Request not found")

    requester       = db.query(User).filter(User.id == req.requester_id).first()
    req.status      = "rejected"
    req.actioned_at = datetime.utcnow()
    db.commit()

    if requester:
        name = requester.email.split("@")[0].title()
        send_role_change_rejected(requester.email, name, req.requested_role)

    return {"success": True, "message": "Request rejected"}
