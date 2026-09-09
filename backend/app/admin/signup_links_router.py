import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database.db import get_db
from app.auth.deps import require_superuser
from app.tenants.signup_models import TenantSignupLink
from app.services.email_service import send_tenant_signup_link
from app.users.models import User

router = APIRouter(prefix="/admin/signup-links", tags=["Signup Links"])
BASE_URL = os.getenv("BASE_URL", "https://api.est8go.com")


class CreateLinkBody(BaseModel):
    plan:          str           = "Starter"
    invited_email: Optional[str] = None
    expiry_hours:  int           = 48
    max_uses:      int           = 1


@router.post("")
def create_signup_link(
    body: CreateLinkBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superuser),
):
    code = secrets.token_urlsafe(24)
    link = TenantSignupLink(
        code          = code,
        plan          = body.plan,
        created_by    = current_user.id,
        invited_email = body.invited_email,
        max_uses      = body.max_uses,
        expires_at    = datetime.utcnow() + timedelta(hours=body.expiry_hours),
    )
    db.add(link)
    db.commit()

    signup_url = f"{BASE_URL}/public/onboarding/{code}"

    if body.invited_email:
        send_tenant_signup_link(
            to_email     = body.invited_email,
            signup_url   = signup_url,
            plan         = body.plan,
            expiry_hours = body.expiry_hours,
            invited_by   = current_user.email,
        )

    return {
        "code":       code,
        "signup_url": signup_url,
        "plan":       body.plan,
        "expires_at": link.expires_at.isoformat(),
    }


@router.get("")
def list_signup_links(
    db: Session = Depends(get_db),
    _: User = Depends(require_superuser),
):
    links = db.query(TenantSignupLink).order_by(
        TenantSignupLink.created_at.desc()
    ).limit(50).all()
    now = datetime.utcnow()
    return [
        {
            "id":            l.id,
            "code":          l.code,
            "plan":          l.plan,
            "invited_email": l.invited_email,
            "signup_url":    f"{BASE_URL}/public/onboarding/{l.code}",
            "uses_count":    l.uses_count,
            "max_uses":      l.max_uses,
            "expires_at":    l.expires_at.isoformat() if l.expires_at else None,
            "used_at":       l.used_at.isoformat() if l.used_at else None,
            "is_active":     (
                l.is_active
                and l.uses_count < l.max_uses
                and (not l.expires_at or l.expires_at > now)
            ),
            "created_at":    l.created_at.isoformat() if l.created_at else None,
        }
        for l in links
    ]


@router.delete("/{link_id}")
def revoke_signup_link(
    link_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_superuser),
):
    link = db.query(TenantSignupLink).filter(TenantSignupLink.id == link_id).first()
    if not link:
        raise HTTPException(404, "Link not found")
    link.is_active = False
    db.commit()
    return {"success": True}
