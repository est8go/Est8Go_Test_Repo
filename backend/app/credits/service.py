from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
import logging

from app.credits.models import (
    CreditWallet, CreditLedger, CreditExpiry,
    CreditTransaction, LedgerEvent,
)

logger = logging.getLogger(__name__)

# ── ACTION PRICE MAP ──────────────────────────────────────────────
ACTION_COSTS = {
    "GPS_VERIFICATION":      0,
    "AI_VISION_AUDIT":       5,
    "DOCUMENT_UPLOAD":       3,
    "DOCUMENT_ANALYSIS":     10,
    "PRIORITY_VERIFICATION": 25,
    "WHATSAPP_SETUP":        50,
    "REEL_GENERATION":       10,
    "TRUST_CERTIFICATE":     20,
    "FEATURED_LISTING":      10,
    "HOMEPAGE_BOOST":        15,
    "BROADCAST_100":         2,
    "CAC_VERIFICATION":      20,
    "ID_VERIFICATION":       15,
    "PHYSICAL_INSPECTION":   50,
    "AI_CAPTION":            3,
    "FLYER_GENERATOR":       5,
}

TIER_DISCOUNTS = {
    "PILOT":      1.0,
    "ACCESS":     0.0,
    "GROWTH":     0.10,
    "BUSINESS":   0.15,
    "ENTERPRISE": 0.25,
}

MMEF_THRESHOLDS = {
    "CORE":   2500,
    "GROWTH": 6000,
}


def get_or_create_wallet(tenant_id: int, db: Session) -> CreditWallet:
    wallet = db.query(CreditWallet).filter(
        CreditWallet.tenant_id == tenant_id
    ).first()
    if not wallet:
        wallet = CreditWallet(tenant_id=tenant_id)
        db.add(wallet)
        db.commit()
        db.refresh(wallet)
    return wallet


def get_balance(tenant_id: int, db: Session) -> dict:
    wallet = get_or_create_wallet(tenant_id, db)
    available = wallet.purchased_balance + wallet.bonus_balance
    return {
        "purchased":   wallet.purchased_balance,
        "bonus":       wallet.bonus_balance,
        "reserved":    wallet.reserved,
        "available":   available - wallet.reserved,
        "total_spent": wallet.total_spent,
    }


def get_action_cost(action: str, tier: str = "ACCESS") -> int:
    base = ACTION_COSTS.get(action.upper(), 0)
    if base == 0:
        return 0
    discount = TIER_DISCOUNTS.get(tier, 0.0)
    final = base * (1 - discount)
    return max(1, int(final))


def log_ledger(
    tenant_id: int,
    event_type: LedgerEvent,
    debited: int,
    credited: int,
    balance_after: int,
    credit_type: str = "purchased",
    reference: str = None,
    action_type: str = None,
    metadata: dict = None,
    created_by: int = None,
    db: Session = None,
):
    entry = CreditLedger(
        tenant_id        = tenant_id,
        event_type       = event_type,
        credits_debited  = debited,
        credits_credited = credited,
        balance_after    = balance_after,
        credit_type      = credit_type,
        reference        = reference,
        action_type      = action_type,
        ledger_metadata  = metadata,
        created_by       = created_by,
    )
    db.add(entry)


def award_credits(
    tenant_id: int,
    credits: int,
    credit_type: str = "purchased",
    reason: str = "admin_award",
    expiry_days: int = None,
    awarded_by: int = None,
    db: Session = None,
) -> dict:
    wallet = get_or_create_wallet(tenant_id, db)

    if credit_type == "purchased":
        wallet.purchased_balance += credits
        wallet.total_awarded     += credits
    else:
        wallet.bonus_balance += credits
        wallet.total_awarded += credits
        if expiry_days:
            expiry = CreditExpiry(
                tenant_id   = tenant_id,
                credits     = credits,
                credit_type = credit_type,
                expires_at  = datetime.utcnow() + timedelta(days=expiry_days),
            )
            db.add(expiry)

    wallet.last_activity_at = datetime.utcnow()
    balance_after = wallet.purchased_balance + wallet.bonus_balance

    if reason == "welcome":
        event = LedgerEvent.WELCOME
    elif reason == "admin_award":
        event = LedgerEvent.AWARD
    else:
        event = LedgerEvent.BONUS

    log_ledger(
        tenant_id     = tenant_id,
        event_type    = event,
        debited       = 0,
        credited      = credits,
        balance_after = balance_after,
        credit_type   = credit_type,
        reference     = reason,
        created_by    = awarded_by,
        db            = db,
    )
    db.commit()
    return {"awarded": credits, "new_balance": balance_after}


def deduct_credits(
    tenant_id: int,
    action: str,
    tier: str = "ACCESS",
    reference: str = None,
    db: Session = None,
) -> dict:
    cost = get_action_cost(action, tier)
    if cost == 0:
        return {"cost": 0, "deducted": False}

    wallet = get_or_create_wallet(tenant_id, db)
    available = wallet.purchased_balance + wallet.bonus_balance - wallet.reserved

    if available < cost:
        raise ValueError(
            f"Not enough credits. This action costs {cost} credits. "
            f"You have {available} available."
        )

    # Deduct bonus first, then purchased
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

    wallet.total_spent      += cost
    wallet.last_activity_at  = datetime.utcnow()
    balance_after = wallet.purchased_balance + wallet.bonus_balance

    log_ledger(
        tenant_id     = tenant_id,
        event_type    = LedgerEvent.COMMIT,
        debited       = cost,
        credited      = 0,
        balance_after = balance_after,
        credit_type   = credit_type,
        reference     = reference,
        action_type   = action,
        db            = db,
    )
    db.commit()
    return {"cost": cost, "deducted": True, "balance_after": balance_after}


def add_purchased_credits(
    tenant_id: int,
    credits: int,
    bonus_credits: int = 0,
    amount_ngn: int = 0,
    paystack_ref: str = None,
    db: Session = None,
) -> dict:
    wallet = get_or_create_wallet(tenant_id, db)
    wallet.purchased_balance += credits
    wallet.total_purchased   += credits
    wallet.last_activity_at   = datetime.utcnow()
    wallet.is_dormant         = False

    balance_after = wallet.purchased_balance + wallet.bonus_balance

    log_ledger(
        tenant_id     = tenant_id,
        event_type    = LedgerEvent.TOPUP,
        debited       = 0,
        credited      = credits,
        balance_after = balance_after,
        credit_type   = "purchased",
        reference     = paystack_ref,
        metadata      = {"amount_ngn": amount_ngn},
        db            = db,
    )

    if bonus_credits > 0:
        wallet.bonus_balance += bonus_credits
        expiry = CreditExpiry(
            tenant_id   = tenant_id,
            credits     = bonus_credits,
            credit_type = "bonus",
            expires_at  = datetime.utcnow() + timedelta(days=90),
        )
        db.add(expiry)
        balance_after += bonus_credits
        log_ledger(
            tenant_id     = tenant_id,
            event_type    = LedgerEvent.BONUS,
            debited       = 0,
            credited      = bonus_credits,
            balance_after = balance_after,
            credit_type   = "bonus",
            reference     = paystack_ref,
            db            = db,
        )

    db.commit()
    return {
        "credits_added":       credits,
        "bonus_credits_added": bonus_credits,
        "new_balance":         balance_after,
    }
