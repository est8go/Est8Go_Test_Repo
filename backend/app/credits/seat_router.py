"""
Seat Management API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.auth.deps import get_current_user, require_superuser, require_tenant_admin
from app.users.models import User
from app.credits.seat_service import (
    get_seat_status,
    purchase_extra_seat,
    run_monthly_seat_renewal,
    EXTRA_SEAT_COST,
)
from app.credits.models import SeatEntitlement

router = APIRouter(prefix="/seats", tags=["Seat Entitlements"])


# ── GET SEAT STATUS (tenant admin or superuser) ───────────────────
@router.get("/status")
def seat_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns seat usage and limits for the current tenant."""
    if not current_user.tenant_id:
        raise HTTPException(400, "No tenant associated.")
    return get_seat_status(current_user.tenant_id, db)


# ── GET SEAT STATUS FOR ANY TENANT (superuser only) ───────────────
@router.get("/status/{tenant_id}")
def seat_status_for_tenant(
    tenant_id: int,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    return get_seat_status(tenant_id, db)


# ── LIST EXTRA SEATS (tenant admin) ──────────────────────────────
@router.get("/list")
def list_extra_seats(
    current_user: User = Depends(require_tenant_admin),
    db: Session = Depends(get_db),
):
    """List all extra seat entitlements for this tenant."""
    seats = (
        db.query(SeatEntitlement)
        .filter(SeatEntitlement.tenant_id == current_user.tenant_id)
        .all()
    )
    result = []
    for s in seats:
        user = db.query(User).filter(User.id == s.user_id).first()
        result.append({
            "id":                s.id,
            "user_id":           s.user_id,
            "user_email":        user.email if user else "—",
            "user_name":         user.first_name if user else "—",
            "status":            s.status,
            "credits_per_month": s.credits_per_month,
            "grace_until":       s.grace_until.isoformat() if s.grace_until else None,
            "last_renewed_at":   s.last_renewed_at.isoformat() if s.last_renewed_at else None,
            "last_month_year":   s.last_month_year,
        })
    return result


# ── TRIGGER MONTHLY RENEWAL (superuser only — for testing + cron) ─
@router.post("/renew-monthly")
async def trigger_monthly_renewal(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    """
    Manually triggers the monthly seat renewal job.
    Normally called by a cron job on the 1st of each month.
    Superuser only.
    """
    background_tasks.add_task(run_monthly_seat_renewal, db)
    return {"success": True, "message": "Monthly seat renewal started in background."}


# ── REACTIVATE SEAT MANUALLY (superuser override) ─────────────────
@router.patch("/{seat_id}/reactivate")
def reactivate_seat(
    seat_id: int,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    """Super Admin manually reactivates a suspended seat. No credits deducted."""
    seat = db.query(SeatEntitlement).filter(SeatEntitlement.id == seat_id).first()
    if not seat:
        raise HTTPException(404, "Seat entitlement not found.")

    user = db.query(User).filter(User.id == seat.user_id).first()
    if user:
        user.is_active = True

    seat.status      = "active"
    seat.grace_until = None
    db.commit()

    return {
        "success": True,
        "message": f"Seat for user {user.email if user else seat.user_id} reactivated.",
    }


# ── SUSPEND SEAT MANUALLY (superuser override) ────────────────────
@router.patch("/{seat_id}/suspend")
def suspend_seat(
    seat_id: int,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    seat = db.query(SeatEntitlement).filter(SeatEntitlement.id == seat_id).first()
    if not seat:
        raise HTTPException(404, "Seat entitlement not found.")

    user = db.query(User).filter(User.id == seat.user_id).first()
    if user:
        user.is_active = False

    seat.status = "suspended"
    db.commit()

    return {"success": True, "message": "Seat suspended."}
