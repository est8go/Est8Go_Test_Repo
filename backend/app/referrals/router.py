import os
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.database.db import get_db
from app.auth.deps import get_current_user
from app.tenants.signup_models import ReferralCode, ReferralConversion
from app.users.models import User

router = APIRouter(prefix="/referrals", tags=["Referrals"])
BASE_URL = os.getenv("BASE_URL", "https://est8go-api.onrender.com")


@router.get("/my-code")
def get_my_referral_code(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.tenant_id:
        raise HTTPException(400, "No tenant associated")

    code = db.query(ReferralCode).filter(
        ReferralCode.tenant_id == current_user.tenant_id,
        ReferralCode.is_active == True,
    ).first()

    if not code:
        new_code = secrets.token_urlsafe(6).upper()[:8]
        code = ReferralCode(
            code            = new_code,
            tenant_id       = current_user.tenant_id,
            commission_rate = 5,
            is_active       = True,
        )
        db.add(code)
        db.commit()
        db.refresh(code)

    conversions = db.query(ReferralConversion).filter(
        ReferralConversion.referral_code_id == code.id
    ).all()

    total_commission   = sum(c.commission_earned for c in conversions)
    paid_commission    = sum(c.commission_earned for c in conversions if c.paid_at)

    return {
        "code":               code.code,
        "commission_rate":    code.commission_rate,
        "uses_count":         code.uses_count,
        "total_commission":   total_commission,
        "paid_commission":    paid_commission,
        "pending_commission": total_commission - paid_commission,
        "share_url":          f"{BASE_URL}/public/onboarding?ref={code.code}",
    }
