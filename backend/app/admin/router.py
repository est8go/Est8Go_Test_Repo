from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.database.db import get_db
from app.users.models import User, PLATFORM_ROLES
from app.tenants.models import Tenant
from app.auth.deps import require_platform_user, require_superuser
from app.listings.models import Listing
from app.conversations.models import Conversation
from app.database.audit import log_action

router = APIRouter(prefix="/admin", tags=["Super Admin"])


# ================================================================
# SCHEMAS
# ================================================================

class TrustBadges(BaseModel):
    emerald: int = 0
    gold: int = 0
    silver: int = 0
    unverified: int = 0


class PulseResponse(BaseModel):
    total_tenants: int
    active_tenants: int
    total_listings: int
    verified_listings: int
    pending_queue: int
    avg_trust_score: float
    daily_conversations: int
    daily_inspections: int
    ai_calls_today: int
    active_realtors: int
    ignored_leads: int
    human_takeovers: int
    risk_count: int
    badges: TrustBadges
    risk_alerts: list


class CreateTenantRequest(BaseModel):
    name: str
    tenant_type: str = "agency"
    plan: str = "pilot"
    whatsapp_phone_number_id: Optional[str] = None
    admin_email: str
    admin_password: str


class TenantListItem(BaseModel):
    id: int
    name: str
    tenant_type: str
    plan: str
    is_active: bool
    listings_count: int = 0
    users_count: int = 0
    health_score: int = 75

    class Config:
        from_attributes = True


class SuspendTenantRequest(BaseModel):
    reason: str


class DeleteTenantRequest(BaseModel):
    reason: str
    confirm: str  # must equal "DELETE"


class ChangeStaffRoleRequest(BaseModel):
    role: str


# ================================================================
# PULSE — platform health snapshot
# ================================================================

@router.get("/pulse", response_model=PulseResponse)
def get_pulse(
    current_user: User = Depends(require_platform_user),
    db: Session = Depends(get_db),
):
    """Platform health snapshot for the command center header."""

    total_tenants  = db.query(Tenant).count()
    active_tenants = db.query(Tenant).filter(Tenant.is_active == True).count()
    total_listings = db.query(Listing).count()

    # Trust grade distribution
    emerald = db.query(Listing).filter(Listing.trust_grade == "Emerald").count()
    gold    = db.query(Listing).filter(Listing.trust_grade == "Gold").count()
    silver  = db.query(Listing).filter(Listing.trust_grade == "Silver").count()

    verified_listings = emerald + gold + silver
    pending_queue     = db.query(Listing).filter(
        Listing.trust_grade.is_(None)
    ).count()
    unverified        = total_listings - verified_listings

    # Average trust score
    avg_score_row = db.query(func.avg(Listing.trust_score)).scalar()
    avg_trust_score = round(float(avg_score_row or 0), 1)

    # Risk count = listings flagged or with very low trust score
    risk_count = db.query(Listing).filter(Listing.trust_score < 30).count()

    return {
        "total_tenants":       total_tenants,
        "active_tenants":      active_tenants,
        "total_listings":      total_listings,
        "verified_listings":   verified_listings,
        "pending_queue":       pending_queue,
        "avg_trust_score":     avg_trust_score,
        "daily_conversations": 0,   # wire to Message model when ready
        "daily_inspections":   0,   # wire to Inspection model when ready
        "ai_calls_today":      0,   # wire to AI usage tracker when ready
        "active_realtors":     0,   # wire to session/activity tracker
        "ignored_leads":       0,
        "human_takeovers":     0,
        "risk_count":          risk_count,
        "badges": {
            "emerald":    emerald,
            "gold":       gold,
            "silver":     silver,
            "unverified": unverified,
        },
        "risk_alerts": [],  # wire to risk detection engine when ready
    }


# ================================================================
# TENANTS — list all
# ================================================================

@router.get("/tenants")
def list_tenants(
    current_user: User = Depends(require_platform_user),
    db: Session = Depends(get_db),
):
    """List all tenants with enriched stats."""
    tenants = db.query(Tenant).order_by(desc(Tenant.created_at)).all()

    result = []
    for t in tenants:
        listings_count = db.query(Listing).filter(Listing.tenant_id == t.id).count()
        users_count    = db.query(User).filter(User.tenant_id == t.id).count()

        result.append({
            "id":            t.id,
            "name":          t.name,
            "business_name": t.business_name,
            "tenant_type":   t.tenant_type,
            "plan":          t.plan,
            "is_active":     t.is_active,
            "listings_count": listings_count,
            "users_count":   users_count,
            "health_score":  75,   # wire to health scoring engine when ready
            "created_at":    str(t.created_at) if t.created_at else None,
        })
    return result


# ================================================================
# TENANTS — create with admin user (superuser only)
# ================================================================

@router.post("/tenants")
def create_tenant(
    payload: CreateTenantRequest,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    """
    Onboard a new tenant and create their first admin user in one shot.
    Superuser only.
    """
    from app.core.security import hash_password

    # Validate tenant type
    valid_types = ("agency", "freelance", "developer", "investor")
    if payload.tenant_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid tenant type.")

    # Create tenant
    tenant = Tenant(
        name=payload.name,
        tenant_type=payload.tenant_type,
        plan=payload.plan,
        whatsapp_phone_number_id=payload.whatsapp_phone_number_id or None,
        is_active=True,
    )
    db.add(tenant)
    db.flush()  # get tenant.id before creating user

    # Create admin user for this tenant
    admin = User(
        tenant_id=tenant.id,
        email=payload.admin_email,
        hashed_password=hash_password(payload.admin_password),
        role="admin",
        is_active=True,
        is_platform_user=False,
        is_admin=True,  # legacy flag
    )
    db.add(admin)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=409, detail="Tenant or email already exists.")

    # Log the action
    log_action(db, actor=current_user, action="tenant_created",
               target_table="tenants", target_id=tenant.id,
               new_value={"name": tenant.name, "type": tenant.tenant_type})

    return {
        "message": f"Tenant '{tenant.name}' created successfully.",
        "tenant_id": tenant.id,
        "admin_email": admin.email,
    }


# ================================================================
# TENANTS — deactivate (superuser only)
# ================================================================

@router.patch("/tenants/{tenant_id}/deactivate")
def deactivate_tenant(
    tenant_id: int,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found.")

    tenant.is_active = False
    db.commit()

    log_action(db, actor=current_user, action="tenant_deactivated",
               target_table="tenants", target_id=tenant.id,
               old_value={"is_active": True}, new_value={"is_active": False})

    return {"message": f"Tenant '{tenant.name}' has been deactivated."}


# ================================================================
# AUDIT LOGS — read (platform staff can view, not modify)
# ================================================================

@router.get("/audit-logs")
def get_audit_logs(
    limit: int = Query(default=50, le=200),
    action: Optional[str] = None,
    current_user: User = Depends(require_platform_user),
    db: Session = Depends(get_db),
):
    """Retrieve audit logs. Filterable by action type."""
    from app.database.audit import AuditLog

    query = db.query(AuditLog).order_by(desc(AuditLog.created_at))

    if action:
        query = query.filter(AuditLog.action == action)

    logs = query.limit(limit).all()

    return [
        {
            "id":           l.id,
            "actor_email":  l.actor_email,
            "actor_role":   l.actor_role,
            "action":       l.action,
            "target_table": l.target_table,
            "target_id":    l.target_id,
            "old_value":    l.old_value,
            "new_value":    l.new_value,
            "created_at":   str(l.created_at) if l.created_at else None,
        }
        for l in logs
    ]


# ================================================================
# TENANTS — suspend (superuser only)
# ================================================================

@router.patch("/tenants/{tenant_id}/suspend")
def suspend_tenant(
    tenant_id: int,
    payload: SuspendTenantRequest,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    """Suspend a tenant and silence their bot. Superuser only."""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    if not tenant.is_active:
        raise HTTPException(status_code=400, detail="Tenant is already suspended.")

    tenant.is_active = False

    # Silence all conversations for this tenant
    db.query(Conversation).filter(Conversation.tenant_id == tenant_id).update(
        {"is_bot_active": False}, synchronize_session=False
    )

    db.commit()

    log_action(
        db, actor=current_user, action="tenant_suspended",
        target_table="tenants", target_id=tenant.id,
        old_value={"is_active": True},
        new_value={"is_active": False, "reason": payload.reason},
    )

    return {"success": True, "message": f"Tenant '{tenant.name}' suspended."}


# ================================================================
# TENANTS — reactivate (superuser only)
# ================================================================

@router.patch("/tenants/{tenant_id}/reactivate")
def reactivate_tenant(
    tenant_id: int,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    """Reactivate a suspended tenant. Superuser only."""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    if tenant.is_active:
        raise HTTPException(status_code=400, detail="Tenant is already active.")

    tenant.is_active = True
    db.commit()

    log_action(
        db, actor=current_user, action="tenant_reactivated",
        target_table="tenants", target_id=tenant.id,
        old_value={"is_active": False}, new_value={"is_active": True},
    )

    return {"success": True, "message": f"Tenant '{tenant.name}' reactivated."}


# ================================================================
# TENANTS — soft delete (superuser only)
# ================================================================

@router.delete("/tenants/{tenant_id}")
def delete_tenant(
    tenant_id: int,
    payload: DeleteTenantRequest,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    """
    Soft-delete a tenant. Data is preserved for audit.
    Requires confirm='DELETE' in the request body.
    Superuser only.
    """
    if payload.confirm != "DELETE":
        raise HTTPException(
            status_code=400,
            detail="Confirmation value must be exactly 'DELETE'.",
        )

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found.")

    # Soft delete: deactivate and mark name with deletion timestamp
    deleted_at_str = datetime.utcnow().strftime("%Y-%m-%d")
    tenant.is_active = False

    # Silence all conversations
    db.query(Conversation).filter(Conversation.tenant_id == tenant_id).update(
        {"is_bot_active": False}, synchronize_session=False
    )

    db.commit()

    log_action(
        db, actor=current_user, action="tenant_deleted",
        target_table="tenants", target_id=tenant.id,
        old_value={"is_active": True, "name": tenant.name},
        new_value={
            "is_active": False,
            "reason": payload.reason,
            "deleted_at": deleted_at_str,
        },
    )

    return {"success": True, "message": f"Tenant '{tenant.name}' has been soft-deleted."}


# ================================================================
# STAFF — change role (superuser only)
# ================================================================

@router.patch("/staff/{user_id}/role")
def change_staff_role(
    user_id: int,
    payload: ChangeStaffRoleRequest,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    """
    Change a platform staff member's role.
    Cannot demote the last superuser.
    Superuser only.
    """
    if payload.role not in PLATFORM_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Role must be one of: {', '.join(PLATFORM_ROLES)}.",
        )

    user = db.query(User).filter(
        User.id == user_id, User.is_platform_user == True
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="Platform staff member not found.")

    # Prevent demoting the last superuser
    if user.role == "superuser" and payload.role != "superuser":
        superuser_count = db.query(User).filter(
            User.is_platform_user == True,
            User.role == "superuser",
            User.is_active == True,
        ).count()
        if superuser_count <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot demote the last active superuser.",
            )

    old_role = user.role
    user.role = payload.role
    db.commit()

    log_action(
        db, actor=current_user, action="role_changed",
        target_table="users", target_id=user.id,
        old_value={"role": old_role},
        new_value={"role": payload.role},
    )

    return {
        "success": True,
        "message": f"{user.email} role changed from {old_role} to {payload.role}.",
    }
