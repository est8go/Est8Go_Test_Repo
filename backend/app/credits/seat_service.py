"""
Est8Go Seat Entitlement Service
================================
Manages staff seat limits per plan, extra seat billing,
grace periods, and automatic suspension/reactivation.

World-class standard:
- Base seats are free and never suspended automatically
- Extra seats cost 800 credits/month each
- 1-day grace period on credit failure, then suspend
- Reactivation is automatic when credits are topped up
- freelance tenants always have exactly 1 seat (no extras)
"""

import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.credits.models import (
    CreditWallet, CreditLedger, LedgerEvent, SeatEntitlement,
)
from app.users.models import User
from app.tenants.models import Tenant

logger = logging.getLogger(__name__)

# ── PLAN SEAT LIMITS ─────────────────────────────────────────────
PLAN_BASE_SEATS = {
    "pilot":      1,
    "access":     1,
    "growth":     2,
    "business":   5,
    "enterprise": None,   # None = unlimited
}

EXTRA_SEAT_COST = 800  # credits per seat per month


def get_base_seat_limit(plan: str):
    """Returns the base seat limit for a plan. None = unlimited."""
    return PLAN_BASE_SEATS.get((plan or "").lower(), 1)


def get_active_staff_count(tenant_id: int, db: Session) -> int:
    """Count of active, non-platform tenant users."""
    return (
        db.query(func.count(User.id))
        .filter(
            User.tenant_id == tenant_id,
            User.is_active == True,
            User.is_platform_user == False,
            User.deleted_at == None,
        )
        .scalar() or 0
    )


def get_seat_status(tenant_id: int, db: Session) -> dict:
    """
    Returns full seat status for a tenant.
    Used by dashboard and enforcement checks.
    """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        return {"error": "Tenant not found"}

    base_limit = get_base_seat_limit(tenant.plan)
    current_count = get_active_staff_count(tenant_id, db)
    extra_seats = db.query(SeatEntitlement).filter(
        SeatEntitlement.tenant_id == tenant_id,
        SeatEntitlement.status.in_(["active", "grace"]),
    ).count()

    # freelance tenants are always solo — 1 seat max
    if tenant.tenant_type == "freelance":
        return {
            "plan":          tenant.plan,
            "base_limit":    1,
            "extra_seats":   0,
            "total_allowed": 1,
            "current_count": current_count,
            "can_add_staff": False,
            "is_freelance":  True,
        }

    total_allowed = (
        None if base_limit is None
        else base_limit + extra_seats
    )

    can_add = (
        total_allowed is None or current_count < total_allowed
    )

    return {
        "plan":            tenant.plan,
        "base_limit":      base_limit,
        "extra_seats":     extra_seats,
        "total_allowed":   total_allowed,
        "current_count":   current_count,
        "can_add_staff":   can_add,
        "is_freelance":    False,
        "slots_remaining": (
            None if total_allowed is None
            else max(0, total_allowed - current_count)
        ),
    }


def check_can_add_staff(tenant_id: int, db: Session):
    """
    Returns (allowed: bool, reason: str).
    Call this before creating any tenant user.
    """
    status = get_seat_status(tenant_id, db)

    if status.get("is_freelance"):
        return False, (
            "Independent realtors operate as solo accounts. "
            "Staff seats are not available on this account type."
        )

    if status.get("can_add_staff"):
        return True, "ok"

    plan = (status.get("plan") or "").title()
    limit = status.get("total_allowed", 0)
    return False, (
        f"Your {plan} plan allows {limit} staff account(s). "
        f"Purchase extra seats with Est8Go credits to add more staff, "
        f"or upgrade your plan."
    )


def purchase_extra_seat(
    tenant_id: int,
    user_id: int,
    db: Session,
    purchased_by: int = None,
) -> dict:
    """
    Register an extra seat for a user and deduct first month's credits.
    Call this when a tenant admin adds a user that exceeds base seats.
    """
    from app.credits.service import get_or_create_wallet, log_ledger

    # Check wallet has enough credits
    wallet = get_or_create_wallet(tenant_id, db)
    available = wallet.purchased_balance + wallet.bonus_balance - wallet.reserved
    if available < EXTRA_SEAT_COST:
        raise ValueError(
            f"Not enough credits to activate extra seat. "
            f"This seat costs {EXTRA_SEAT_COST} credits/month. "
            f"You have {available} credits available."
        )

    # Deduct first month — bonus first, then purchased
    if wallet.bonus_balance >= EXTRA_SEAT_COST:
        wallet.bonus_balance -= EXTRA_SEAT_COST
        credit_type = "bonus"
    elif wallet.bonus_balance > 0:
        remainder = EXTRA_SEAT_COST - wallet.bonus_balance
        wallet.bonus_balance = 0
        wallet.purchased_balance -= remainder
        credit_type = "mixed"
    else:
        wallet.purchased_balance -= EXTRA_SEAT_COST
        credit_type = "purchased"

    wallet.total_spent += EXTRA_SEAT_COST
    wallet.last_activity_at = datetime.utcnow()
    balance_after = wallet.purchased_balance + wallet.bonus_balance

    current_month = datetime.utcnow().strftime("%Y-%m")

    log_ledger(
        tenant_id     = tenant_id,
        event_type    = LedgerEvent.SEAT_RENEWAL,
        debited       = EXTRA_SEAT_COST,
        credited      = 0,
        balance_after = balance_after,
        credit_type   = credit_type,
        reference     = f"extra_seat_user_{user_id}_{current_month}",
        action_type   = "EXTRA_SEAT",
        metadata      = {"user_id": user_id, "month_year": current_month},
        created_by    = purchased_by,
        db            = db,
    )

    entitlement = SeatEntitlement(
        tenant_id         = tenant_id,
        user_id           = user_id,
        status            = "active",
        credits_per_month = EXTRA_SEAT_COST,
        last_renewed_at   = datetime.utcnow(),
        last_month_year   = current_month,
    )
    db.add(entitlement)
    db.commit()

    return {
        "success":       True,
        "credits_spent": EXTRA_SEAT_COST,
        "balance_after": balance_after,
        "month_year":    current_month,
    }


async def run_monthly_seat_renewal(db: Session):
    """
    Run on the 1st of each month.
    Renews all extra seats by deducting credits.
    Starts grace period for tenants that can't afford renewal.
    Suspends seats where grace has expired.
    """
    from app.credits.service import get_or_create_wallet, log_ledger

    current_month = datetime.utcnow().strftime("%Y-%m")
    now = datetime.utcnow()

    logger.info(f"▶ Starting monthly seat renewal for {current_month}")

    # ── STEP 1: Suspend seats where grace period has expired ──────
    expired_grace = db.query(SeatEntitlement).filter(
        SeatEntitlement.status == "grace",
        SeatEntitlement.grace_until <= now,
    ).all()

    for seat in expired_grace:
        user = db.query(User).filter(User.id == seat.user_id).first()
        if user:
            user.is_active = False
            logger.info(
                f"🔒 Suspended user {user.email} (tenant {seat.tenant_id}) "
                f"— grace period expired"
            )
        seat.status = "suspended"
        db.commit()

    # ── STEP 2: Renew active extra seats ─────────────────────────
    active_seats = db.query(SeatEntitlement).filter(
        SeatEntitlement.status == "active",
        SeatEntitlement.last_month_year != current_month,
    ).all()

    for seat in active_seats:
        wallet = get_or_create_wallet(seat.tenant_id, db)
        available = (
            wallet.purchased_balance + wallet.bonus_balance - wallet.reserved
        )

        if available >= seat.credits_per_month:
            cost = seat.credits_per_month
            if wallet.bonus_balance >= cost:
                wallet.bonus_balance -= cost
                credit_type = "bonus"
            elif wallet.bonus_balance > 0:
                remainder = cost - wallet.bonus_balance
                wallet.bonus_balance = 0
                wallet.purchased_balance -= remainder
                credit_type = "mixed"
            else:
                wallet.purchased_balance -= cost
                credit_type = "purchased"

            wallet.total_spent += cost
            wallet.last_activity_at = now
            balance_after = wallet.purchased_balance + wallet.bonus_balance

            log_ledger(
                tenant_id     = seat.tenant_id,
                event_type    = LedgerEvent.SEAT_RENEWAL,
                debited       = cost,
                credited      = 0,
                balance_after = balance_after,
                credit_type   = credit_type,
                reference     = f"seat_renewal_{seat.user_id}_{current_month}",
                action_type   = "SEAT_RENEWAL",
                metadata      = {
                    "user_id":    seat.user_id,
                    "month_year": current_month,
                },
                db = db,
            )

            seat.last_renewed_at = now
            seat.last_month_year = current_month
            seat.grace_until     = None
            db.commit()

        else:
            # Not enough credits — start grace period
            seat.status      = "grace"
            seat.grace_until = now + timedelta(hours=24)
            db.commit()

            tenant = db.query(Tenant).filter(
                Tenant.id == seat.tenant_id
            ).first()
            admin = db.query(User).filter(
                User.tenant_id == seat.tenant_id,
                User.role == "admin",
                User.is_active == True,
                User.phone_number != None,
            ).first()

            if admin and admin.phone_number:
                extra_user = db.query(User).filter(
                    User.id == seat.user_id
                ).first()
                seat_user_name = (
                    (extra_user.first_name or extra_user.email)
                    if extra_user else "a staff member"
                )
                business = (
                    (tenant.business_name or tenant.name)
                    if tenant else "your account"
                )
                alert_text = (
                    f"⚠️ *Est8Go Seat Alert — {business}*\n\n"
                    f"Your extra seat for *{seat_user_name}* could not be "
                    f"renewed — insufficient credits.\n\n"
                    f"💳 Cost: {seat.credits_per_month} credits/month\n"
                    f"⏰ *Grace period: 24 hours*\n\n"
                    f"Top up your credits now to keep this seat active. "
                    f"After 24 hours, the account will be suspended "
                    f"until credits are restored.\n\n"
                    f"📲 Top up at: https://est8go.com/public/realtor-portal"
                )
                try:
                    from app.services.notification_service import (
                        send_meta_text_message,
                    )
                    await send_meta_text_message(admin.phone_number, alert_text)
                    logger.info(
                        f"📱 Grace alert sent to {admin.phone_number} "
                        f"for tenant {seat.tenant_id}"
                    )
                except Exception as e:
                    logger.error(f"Failed to send grace alert: {e}")

    # ── STEP 3: Auto-reactivate suspended seats if credits restored ─
    suspended_seats = db.query(SeatEntitlement).filter(
        SeatEntitlement.status == "suspended",
    ).all()

    for seat in suspended_seats:
        wallet = get_or_create_wallet(seat.tenant_id, db)
        available = wallet.purchased_balance + wallet.bonus_balance - wallet.reserved

        if available >= seat.credits_per_month:
            cost = seat.credits_per_month
            if wallet.bonus_balance >= cost:
                wallet.bonus_balance -= cost
                credit_type = "bonus"
            else:
                wallet.purchased_balance -= cost
                credit_type = "purchased"

            wallet.total_spent += cost
            wallet.last_activity_at = now
            balance_after = wallet.purchased_balance + wallet.bonus_balance

            log_ledger(
                tenant_id     = seat.tenant_id,
                event_type    = LedgerEvent.SEAT_RENEWAL,
                debited       = cost,
                credited      = 0,
                balance_after = balance_after,
                credit_type   = credit_type,
                reference     = f"seat_reactivation_{seat.user_id}_{current_month}",
                action_type   = "SEAT_REACTIVATION",
                metadata      = {"user_id": seat.user_id},
                db            = db,
            )

            user = db.query(User).filter(User.id == seat.user_id).first()
            if user:
                user.is_active = True

            seat.status          = "active"
            seat.last_renewed_at = now
            seat.last_month_year = current_month
            seat.grace_until     = None
            db.commit()

            logger.info(
                f"✅ Seat reactivated for user {seat.user_id} "
                f"tenant {seat.tenant_id}"
            )

    logger.info(f"✅ Monthly seat renewal complete for {current_month}")


def flag_tenant_for_review(tenant_id: int, db: Session):
    """
    Creates a platform issue after 7 days of suspended seats.
    Super Admin sees it in the Issues tab.
    """
    from app.services.health_service import PlatformIssue

    existing = db.query(PlatformIssue).filter(
        PlatformIssue.tenant_id == tenant_id,
        PlatformIssue.status == "open",
        PlatformIssue.affected_area == "seats",
    ).first()

    if existing:
        return  # already flagged

    issue = PlatformIssue(
        title         = "Suspended extra seats — tenant review needed",
        description   = (
            f"Tenant ID {tenant_id} has had suspended extra seat(s) "
            f"for 7+ days due to insufficient credits. "
            f"Review and decide: top up manually, override, or escalate."
        ),
        severity      = "medium",
        status        = "open",
        affected_area = "seats",
        tenant_id     = tenant_id,
    )
    db.add(issue)
    db.commit()
