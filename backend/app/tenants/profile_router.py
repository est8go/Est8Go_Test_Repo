from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.database.db import SessionLocal
from app.tenants.deps import get_tenant_id
from app.tenants.models import CompanyProfile
from app.users.models import User

router = APIRouter(prefix="/tenants", tags=["Company Profile"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_tenant_access(tenant_id: int, current_user: User):
    if current_user.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")


def _get_or_create_profile(db: Session, tenant_id: int) -> CompanyProfile:
    prof = db.query(CompanyProfile).filter(CompanyProfile.tenant_id == tenant_id).first()
    if prof:
        return prof

    prof = CompanyProfile(tenant_id=tenant_id)
    db.add(prof)
    db.commit()
    db.refresh(prof)
    return prof


@router.get("/me/profile")
def get_my_profile(
    tenant_id: int = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_tenant_access(tenant_id, current_user)
    prof = _get_or_create_profile(db, tenant_id)

    return {
        "tenant_id": tenant_id,
        "company_name": prof.company_name,
        "short_about": prof.short_about,
        "phone": prof.phone,
        "whatsapp": prof.whatsapp,
        "email": prof.email,
        "office_address": prof.office_address,
        "areas_covered": prof.areas_covered,
        "payment_options": prof.payment_options,
        "inspection_policy": prof.inspection_policy,
        "manager_name": prof.manager_name,
        "handoff_message": prof.handoff_message,
    }


@router.put("/me/profile")
def update_my_profile(
    payload: dict,
    tenant_id: int = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_tenant_access(tenant_id, current_user)
    prof = _get_or_create_profile(db, tenant_id)

    # Only allow known keys (defensive)
    allowed = {
        "company_name",
        "short_about",
        "phone",
        "whatsapp",
        "email",
        "office_address",
        "areas_covered",
        "payment_options",
        "inspection_policy",
        "manager_name",
        "handoff_message",
    }

    for k, v in (payload or {}).items():
        if k in allowed and isinstance(v, str):
            setattr(prof, k, v.strip())

    db.commit()
    db.refresh(prof)

    return {"status": "ok", "tenant_id": tenant_id}