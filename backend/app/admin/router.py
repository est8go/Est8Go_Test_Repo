import re
import calendar
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone, timedelta

from app.database.db import get_db
from app.users.models import User, PLATFORM_ROLES
from app.tenants.models import Tenant
from app.auth.deps import require_platform_user, require_superuser
from app.listings.models import Listing
from app.conversations.models import Conversation
from app.database.audit import log_action
from app.credits.models import MmefTracking, CreditTransaction, CreditWallet

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
    business_name: Optional[str] = None
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

    # ── STEP 1: Required fields not empty ────────────────────────
    required = {
        "name":          payload.name,
        "business_name": payload.business_name or payload.name,
        "plan":          payload.plan,
    }
    for field, value in required.items():
        if not value or not str(value).strip():
            raise HTTPException(status_code=400, detail=f"{field} is required and cannot be empty.")

    # ── STEP 2: Admin email format + uniqueness ───────────────────
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if payload.admin_email:
        if not re.match(email_pattern, payload.admin_email):
            raise HTTPException(status_code=400, detail="Invalid email address format.")
        existing_user = db.query(User).filter(
            User.email == payload.admin_email.lower().strip()
        ).first()
        if existing_user:
            raise HTTPException(status_code=400, detail=f"Email {payload.admin_email} is already registered.")

    # ── STEP 3: WhatsApp number uniqueness ───────────────────────
    if payload.whatsapp_phone_number_id:
        wa = str(payload.whatsapp_phone_number_id).strip()
        existing_wa = db.query(Tenant).filter(
            Tenant.whatsapp_phone_number_id == wa,
            Tenant.is_active == True,
        ).first()
        if existing_wa:
            raise HTTPException(
                status_code=400,
                detail=f"WhatsApp number {wa} is already registered to {existing_wa.business_name}.",
            )
        payload.whatsapp_phone_number_id = wa
    else:
        payload.whatsapp_phone_number_id = None

    # ── STEP 4: Phone number format (if field present) ───────────
    if hasattr(payload, "phone") and payload.phone:
        phone_clean = re.sub(r"[\s\-\(\)]", "", str(payload.phone).strip())
        phone_valid = (
            re.match(r"^0[789][01]\d{8}$", phone_clean) or
            re.match(r"^\+?234[789][01]\d{8}$", phone_clean)
        )
        if not phone_valid:
            raise HTTPException(
                status_code=400,
                detail="Invalid Nigerian phone number format. Use 08012345678 or +2348012345678.",
            )

    # ── STEP 5: Plan is one of allowed values ─────────────────────
    allowed_plans = ["pilot", "starter", "growth", "enterprise"]
    if payload.plan and payload.plan.lower() not in allowed_plans:
        raise HTTPException(
            status_code=400,
            detail=f"Plan must be one of: {', '.join(allowed_plans)}",
        )

    # ── STEP 6: Business name uniqueness ─────────────────────────
    biz_name = (payload.business_name or payload.name).strip()
    existing_biz = db.query(Tenant).filter(
        Tenant.business_name == biz_name,
        Tenant.is_active == True,
    ).first()
    if existing_biz:
        raise HTTPException(
            status_code=400,
            detail=f"A tenant named '{biz_name}' already exists.",
        )

    # ── STEP 7: Safe defaults ─────────────────────────────────────
    business_name = biz_name
    tenant_name   = (payload.name or business_name).strip()
    admin_email   = payload.admin_email.lower().strip() if payload.admin_email else ""

    # ── STEP 8: Validate tenant type ─────────────────────────────
    valid_types = ("agency", "freelance", "developer", "investor")
    if payload.tenant_type not in valid_types:
        raise HTTPException(status_code=400, detail="Invalid tenant type.")

    # ── CREATE TENANT + USER (wrapped in single IntegrityError catch) ──
    try:
        tenant = Tenant(
            name=tenant_name,
            business_name=business_name,
            tenant_type=payload.tenant_type,
            plan=payload.plan.lower(),
            whatsapp_phone_number_id=payload.whatsapp_phone_number_id,
            is_active=True,
        )
        db.add(tenant)
        db.flush()  # get tenant.id before creating user

        admin = User(
            tenant_id=tenant.id,
            email=admin_email,
            hashed_password=hash_password(payload.admin_password),
            role="admin",
            is_active=True,
            is_platform_user=False,
            is_admin=True,  # legacy flag
        )
        db.add(admin)
        db.commit()

    except IntegrityError as e:
        db.rollback()
        err = str(e.orig).lower()
        if "whatsapp_phone_number_id" in err:
            raise HTTPException(status_code=400, detail="WhatsApp number already registered to another tenant.")
        if "email" in err:
            raise HTTPException(status_code=400, detail="Email address already registered.")
        if "business_name" in err:
            raise HTTPException(status_code=400, detail="Business name already exists.")
        raise HTTPException(status_code=400, detail="Creation failed: duplicate data detected.")

    # Log the action
    log_action(db, actor=current_user, action="tenant_created",
               target_table="tenants", target_id=tenant.id,
               new_value={"name": tenant.name, "type": tenant.tenant_type})

    return {
        "success": True,
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
    tenant.suspended_at = datetime.utcnow()

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
    tenant.suspended_at = None   # clear suspension timestamp on reactivation
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


# ================================================================
# VERIFY QUEUE — pending listings with images + GPS + docs
# ================================================================

@router.get("/verify-queue")
def get_verify_queue(
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    """Return listings that are not yet verified. Superuser only."""
    from app.listings.models import ListingImage

    listings = (
        db.query(Listing)
        .filter(Listing.status.notin_(["verified", "rejected", "flagged"]))
        .order_by(desc(Listing.created_at))
        .limit(50)
        .all()
    )

    result = []
    for l in listings:
        images = db.query(ListingImage).filter(ListingImage.listing_id == l.id).all()
        tenant = db.query(Tenant).filter(Tenant.id == l.tenant_id).first()
        result.append({
            "id":             l.id,
            "title":          l.title,
            "location":       l.location,
            "price":          l.price,
            "property_type":  l.property_type,
            "trust_score":    l.trust_score,
            "trust_grade":    l.trust_grade,
            "status":         l.status,
            "latitude":       l.latitude,
            "longitude":      l.longitude,
            "cof_uploaded":   l.cof_uploaded,
            "survey_uploaded": l.survey_uploaded,
            "deed_uploaded":  l.deed_uploaded,
            "gps_verified_at": l.gps_verified_at.isoformat() if l.gps_verified_at else None,
            "created_at":     l.created_at.isoformat() if l.created_at else None,
            "tenant_name":    tenant.business_name if tenant else "—",
            "images":         [{"url": img.url} for img in images],
        })
    return result


# ================================================================
# LISTINGS — verify / flag / reject (superuser only)
# ================================================================

@router.patch("/listings/{listing_id}/verify")
def verify_listing(
    listing_id: int,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")
    listing.status = "verified"
    db.commit()
    log_action(db, actor=current_user, action="listing_verified",
               target_table="listings", target_id=listing.id,
               new_value={"status": "verified"})
    return {"success": True}


@router.patch("/listings/{listing_id}/flag")
def flag_listing(
    listing_id: int,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")
    listing.status     = "flagged"
    listing.trust_grade = "flagged"
    db.commit()
    log_action(db, actor=current_user, action="listing_flagged",
               target_table="listings", target_id=listing.id,
               new_value={"status": "flagged"})
    return {"success": True}


@router.patch("/listings/{listing_id}/reject")
def reject_listing(
    listing_id: int,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")
    listing.status = "rejected"
    db.commit()
    log_action(db, actor=current_user, action="listing_rejected",
               target_table="listings", target_id=listing.id,
               new_value={"status": "rejected"})
    return {"success": True}


# ================================================================
# MMEF COMPLIANCE — monitor Core & Growth tenants
# ================================================================

_MMEF_THRESHOLDS = {"core": 2500, "growth": 6000}


@router.get("/mmef/compliance")
def get_mmef_compliance(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superuser),
):
    """Returns MMEF compliance status for all Core and Growth tenants."""
    current_month = datetime.utcnow().strftime("%Y-%m")
    now = datetime.utcnow()
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    days_left = days_in_month - now.day

    tenants = db.query(Tenant).filter(
        Tenant.plan.in_(["core", "growth"]),
        Tenant.is_active == True,
    ).all()

    results = []
    for tenant in tenants:
        threshold = _MMEF_THRESHOLDS.get(tenant.plan, 0)

        purchased = db.query(
            func.sum(CreditTransaction.amount_ngn)
        ).filter(
            CreditTransaction.tenant_id == tenant.id,
            CreditTransaction.status == "completed",
            CreditTransaction.month_year == current_month,
        ).scalar() or 0

        mmef = db.query(MmefTracking).filter(
            MmefTracking.tenant_id == tenant.id,
            MmefTracking.month_year == current_month,
        ).first()

        pct = round((purchased / threshold) * 100) if threshold > 0 else 100

        if purchased >= threshold:
            status = "compliant"
        elif mmef and mmef.grace_until and mmef.grace_until > now:
            status = "grace_period"
        elif pct >= 70:
            status = "at_risk"
        else:
            status = "non_compliant"

        wallet = db.query(CreditWallet).filter(
            CreditWallet.tenant_id == tenant.id
        ).first()

        results.append({
            "tenant_id":      tenant.id,
            "tenant_name":    tenant.business_name or "—",
            "plan":           tenant.plan,
            "threshold_ngn":  threshold,
            "purchased_ngn":  purchased,
            "percentage":     min(pct, 100),
            "status":         status,
            "days_left":      days_left,
            "grace_until":    mmef.grace_until.isoformat() if mmef and mmef.grace_until else None,
            "credit_balance": (wallet.purchased_balance + wallet.bonus_balance) if wallet else 0,
            "month_year":     current_month,
        })

    order = {"non_compliant": 0, "at_risk": 1, "grace_period": 2, "compliant": 3}
    results.sort(key=lambda x: order.get(x["status"], 4))

    return {
        "month_year":    current_month,
        "total":         len(results),
        "compliant":     sum(1 for r in results if r["status"] == "compliant"),
        "at_risk":       sum(1 for r in results if r["status"] == "at_risk"),
        "grace":         sum(1 for r in results if r["status"] == "grace_period"),
        "non_compliant": sum(1 for r in results if r["status"] == "non_compliant"),
        "tenants":       results,
    }


@router.post("/mmef/{tenant_id}/override")
def mmef_override(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superuser),
):
    """Super Admin manually marks a tenant as MMEF compliant for current month."""
    current_month = datetime.utcnow().strftime("%Y-%m")

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    threshold = _MMEF_THRESHOLDS.get(tenant.plan, 0)

    mmef = db.query(MmefTracking).filter(
        MmefTracking.tenant_id == tenant_id,
        MmefTracking.month_year == current_month,
    ).first()

    if mmef:
        mmef.met = True
        mmef.purchased_ngn = threshold
    else:
        mmef = MmefTracking(
            tenant_id=tenant_id,
            month_year=current_month,
            tier=tenant.plan,
            required_ngn=threshold,
            purchased_ngn=threshold,
            met=True,
        )
        db.add(mmef)

    db.commit()
    log_action(
        db, actor=current_user, action="mmef_override",
        target_table="mmef_tracking", target_id=tenant_id,
        new_value={"month_year": current_month, "met": True},
    )
    return {"success": True, "message": f"MMEF override applied for {tenant.business_name}"}


@router.post("/mmef/{tenant_id}/extend-grace")
def mmef_extend_grace(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superuser),
):
    """Extend grace period by 7 days for a tenant."""
    current_month = datetime.utcnow().strftime("%Y-%m")

    mmef = db.query(MmefTracking).filter(
        MmefTracking.tenant_id == tenant_id,
        MmefTracking.month_year == current_month,
    ).first()

    if mmef:
        new_grace = (mmef.grace_until or datetime.utcnow()) + timedelta(days=7)
        mmef.grace_until = new_grace
    else:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        mmef = MmefTracking(
            tenant_id=tenant_id,
            month_year=current_month,
            tier=tenant.plan if tenant else "core",
            required_ngn=_MMEF_THRESHOLDS.get(tenant.plan if tenant else "core", 2500),
            grace_until=datetime.utcnow() + timedelta(days=7),
        )
        db.add(mmef)

    db.commit()
    log_action(
        db, actor=current_user, action="mmef_grace_extended",
        target_table="mmef_tracking", target_id=tenant_id,
        new_value={"month_year": current_month, "grace_days": 7},
    )
    return {"success": True, "message": "Grace period extended by 7 days"}
