from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
import os, hmac, hashlib, logging, json, uuid

import httpx

from app.database.db import get_db
from app.auth.deps import get_current_user, require_superuser
from app.users.models import User
from app.credits.models import (
    CreditBundle, CreditTransaction, CreditLedger, CreditExpiry,
    CreditWallet, MmefTracking,
)
from app.credits.service import (
    get_balance, award_credits, add_purchased_credits,
    get_or_create_wallet, deduct_credits,
)

router = APIRouter(prefix="/credits", tags=["Credits"])
logger = logging.getLogger(__name__)


# ── GET BALANCE ───────────────────────────────────────────────────
@router.get("/balance")
def get_credit_balance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.tenant_id:
        raise HTTPException(400, "No tenant associated")
    balance = get_balance(current_user.tenant_id, db)

    expiring_soon = db.query(CreditExpiry).filter(
        CreditExpiry.tenant_id == current_user.tenant_id,
        CreditExpiry.expired   == False,
        CreditExpiry.expires_at != None,
        CreditExpiry.expires_at <= datetime.utcnow() + timedelta(days=14),
    ).all()

    return {
        **balance,
        "expiring_soon": [
            {
                "credits":    e.credits,
                "expires_at": e.expires_at.isoformat(),
                "days_left":  max(0, (e.expires_at - datetime.utcnow()).days),
            }
            for e in expiring_soon
        ],
    }


# ── GET BUNDLES ───────────────────────────────────────────────────
@router.get("/bundles")
def get_credit_bundles(db: Session = Depends(get_db)):
    bundles = (
        db.query(CreditBundle)
        .filter(CreditBundle.is_active == True)
        .order_by(CreditBundle.display_order)
        .all()
    )
    return [
        {
            "id":            b.id,
            "name":          b.name,
            "credits":       b.credits,
            "bonus_credits": b.bonus_credits,
            "price_ngn":     b.price_ngn,
            "price_display": f"₦{b.price_ngn:,}",
            "per_credit":    round(b.price_ngn / b.credits),
            "total_credits": b.credits + b.bonus_credits,
        }
        for b in bundles
    ]


# ── INITIATE PURCHASE ─────────────────────────────────────────────
class PurchaseRequest(BaseModel):
    bundle_id: int
    email: Optional[str] = None


@router.post("/purchase/initiate")
async def initiate_purchase(
    body: PurchaseRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.tenant_id:
        raise HTTPException(400, "No tenant associated")

    bundle = db.query(CreditBundle).filter(
        CreditBundle.id == body.bundle_id,
        CreditBundle.is_active == True,
    ).first()
    if not bundle:
        raise HTTPException(404, "Bundle not found")

    # Verify env key is loaded
    key = os.getenv("PAYSTACK_SECRET_KEY", "")
    logger.info(f"Paystack key present: {bool(key)} length: {len(key)}")

    reference    = f"est8go_{uuid.uuid4().hex[:16]}"
    email        = body.email or current_user.email
    amount_kobo  = bundle.price_ngn * 100
    logger.info(f"Initiating purchase: bundle={bundle.name} email={email} amount_kobo={amount_kobo} ref={reference}")

    txn = CreditTransaction(
        tenant_id     = current_user.tenant_id,
        bundle_id     = bundle.id,
        paystack_ref  = reference,
        amount_ngn    = bundle.price_ngn,
        credits       = bundle.credits,
        bonus_credits = bundle.bonus_credits,
        status        = "pending",
        month_year    = datetime.utcnow().strftime("%Y-%m"),
    )
    db.add(txn)
    db.commit()

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type":  "application/json",
    }
    payload = {
        "email":        email,
        "amount":       amount_kobo,
        "reference":    reference,
        "callback_url": f"{os.getenv('BASE_URL', '')}/public/credits/payment-success",
        "metadata": {
            "tenant_id":   current_user.tenant_id,
            "bundle_id":   bundle.id,
            "bundle_name": bundle.name,
            "credits":     bundle.credits,
        },
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.paystack.co/transaction/initialize",
            json=payload, headers=headers, timeout=30,
        )

    logger.error(f"Paystack full response: {resp.status_code} {resp.text}")
    data = resp.json()

    if not data.get("status"):
        raise HTTPException(
            502,
            f"Payment failed: {data.get('message', 'Unknown error')}",
        )

    return {
        "authorization_url": data["data"]["authorization_url"],
        "reference":         reference,
        "amount":            bundle.price_ngn,
        "credits":           bundle.credits,
        "bonus_credits":     bundle.bonus_credits,
    }


# ── PAYSTACK WEBHOOK ──────────────────────────────────────────────
@router.post("/webhook/paystack")
async def paystack_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    payload   = await request.body()
    signature = request.headers.get("x-paystack-signature", "")

    secret   = os.getenv("PAYSTACK_SECRET_KEY", "")
    expected = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha512,
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        logger.warning("Invalid Paystack webhook signature")
        raise HTTPException(400, "Invalid signature")

    event = json.loads(payload)

    if event.get("event") == "charge.success":
        data      = event["data"]
        reference = data.get("reference")

        txn = db.query(CreditTransaction).filter(
            CreditTransaction.paystack_ref == reference,
            CreditTransaction.status       == "pending",
        ).first()

        if not txn:
            logger.warning(f"Transaction not found: {reference}")
            return {"status": "ok"}

        txn.status       = "completed"
        txn.completed_at = datetime.utcnow()
        db.commit()

        result = add_purchased_credits(
            tenant_id     = txn.tenant_id,
            credits       = txn.credits,
            bonus_credits = txn.bonus_credits,
            amount_ngn    = txn.amount_ngn,
            paystack_ref  = reference,
            db            = db,
        )

        logger.info(
            f"Credits added: tenant={txn.tenant_id} credits={txn.credits} ref={reference}"
        )

        # Send confirmation email (non-fatal if it fails)
        try:
            from app.services.email_service import _send, _base_template
            from app.users.models import User as UserModel

            user = db.query(UserModel).filter_by(tenant_id=txn.tenant_id).first()
            if user:
                bonus_note = (
                    f" (+{txn.bonus_credits} bonus)" if txn.bonus_credits else ""
                )
                body = f"""
                <p style="font-size:14px;color:#475569;font-family:Arial,sans-serif">
                  Your Est8 Credits have been added to your wallet.
                </p>
                <p style="font-size:28px;font-weight:800;color:#10B981;
                          margin:16px 0;font-family:Arial,sans-serif">
                  +{txn.credits} Credits{bonus_note}
                </p>
                <p style="font-size:14px;color:#475569;font-family:Arial,sans-serif">
                  Amount paid: <strong>₦{txn.amount_ngn:,}</strong>
                </p>
                <a href="{os.getenv('BASE_URL', '')}/public/realtor-portal"
                   style="display:inline-block;background:#4338CA;color:#ffffff;
                          text-decoration:none;padding:14px 28px;border-radius:12px;
                          font-weight:700;font-size:14px;margin:8px 0 20px;
                          font-family:Arial,sans-serif">
                  View My Wallet
                </a>"""
                _send(
                    user.email,
                    "Your Est8 Credits are ready",
                    _base_template("Credits Added", body),
                )
        except Exception as e:
            logger.error(f"Credit confirmation email failed: {e}")

    return {"status": "ok"}


# ── TRANSACTION HISTORY ───────────────────────────────────────────
@router.get("/history")
def get_credit_history(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.tenant_id:
        raise HTTPException(400, "No tenant associated")

    entries = (
        db.query(CreditLedger)
        .filter(CreditLedger.tenant_id == current_user.tenant_id)
        .order_by(CreditLedger.created_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "event_type":       e.event_type,
            "credits_debited":  e.credits_debited,
            "credits_credited": e.credits_credited,
            "balance_after":    e.balance_after,
            "action_type":      e.action_type,
            "reference":        e.reference,
            "created_at":       e.created_at.isoformat(),
        }
        for e in entries
    ]


# ── ADMIN: AWARD CREDITS ──────────────────────────────────────────
class AwardRequest(BaseModel):
    tenant_id:   int
    credits:     int
    credit_type: str = "purchased"
    reason:      str = "admin_award"
    expiry_days: Optional[int] = None


@router.post("/admin/award")
def admin_award_credits(
    body: AwardRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superuser),
):
    result = award_credits(
        tenant_id   = body.tenant_id,
        credits     = body.credits,
        credit_type = body.credit_type,
        reason      = body.reason,
        expiry_days = body.expiry_days,
        awarded_by  = current_user.id,
        db          = db,
    )
    return result


# ── ADMIN: ALL WALLETS ────────────────────────────────────────────
@router.get("/admin/wallets")
def admin_get_all_wallets(
    db: Session = Depends(get_db),
    _: User = Depends(require_superuser),
):
    from app.tenants.models import Tenant

    wallets = db.query(CreditWallet).all()
    result  = []
    for w in wallets:
        tenant = db.query(Tenant).filter(Tenant.id == w.tenant_id).first()
        result.append({
            "tenant_id":         w.tenant_id,
            "tenant_name":       tenant.business_name if tenant else "—",
            "purchased_balance": w.purchased_balance,
            "bonus_balance":     w.bonus_balance,
            "available":         w.purchased_balance + w.bonus_balance,
            "total_spent":       w.total_spent,
            "is_dormant":        w.is_dormant,
            "last_activity_at":  w.last_activity_at.isoformat() if w.last_activity_at else None,
        })
    return result
