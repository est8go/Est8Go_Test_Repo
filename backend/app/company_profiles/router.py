from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.database.db import SessionLocal
from app.tenants.deps import get_tenant_id
from app.users.models import User

from app.company_profiles.models import CompanyProfile
from app.company_profiles.schemas import (
    CompanyProfileOut,
    CompanyProfileUpdate,
    PublicCompanyProfileOut,
)

router = APIRouter(prefix="/tenants/me", tags=["Company Profile"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_tenant_access(tenant_id: int, current_user: User):
    if current_user.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")


def _default_profile(tenant_id: int) -> CompanyProfileOut:
    # UI-friendly default when no row exists yet
    return CompanyProfileOut(tenant_id=tenant_id)


@router.get("/profile", response_model=CompanyProfileOut)
def get_my_company_profile(
    tenant_id: int = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_tenant_access(tenant_id, current_user)

    row = db.query(CompanyProfile).filter(CompanyProfile.tenant_id == tenant_id).first()
    if not row:
        return _default_profile(tenant_id)

    return row


@router.put("/profile", response_model=CompanyProfileOut)
def upsert_my_company_profile(
    payload: CompanyProfileUpdate,
    tenant_id: int = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_tenant_access(tenant_id, current_user)

    row = db.query(CompanyProfile).filter(CompanyProfile.tenant_id == tenant_id).first()
    if not row:
        row = CompanyProfile(tenant_id=tenant_id)
        db.add(row)

    data = payload.model_dump(exclude_unset=True)

    # Defensive: ignore tenant_id/id if anyone tries to sneak it in
    data.pop("tenant_id", None)
    data.pop("id", None)

    for k, v in data.items():
        setattr(row, k, v)

    db.commit()
    db.refresh(row)
    return row


# -----------------------------
# Public read (safe fields only)
# -----------------------------
public_router = APIRouter(prefix="/public", tags=["Public Company Profile"])


@public_router.get("/company-profile", response_model=PublicCompanyProfileOut)
def public_get_company_profile(
    tenant_id: int,
    db: Session = Depends(get_db),
):
    row = db.query(CompanyProfile).filter(CompanyProfile.tenant_id == tenant_id).first()
    if not row:
        return PublicCompanyProfileOut(tenant_id=tenant_id)

    return row