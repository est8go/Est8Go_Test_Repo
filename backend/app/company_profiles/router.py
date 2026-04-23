from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from app.database.db import get_db
from app.auth.deps import get_current_user  # Ensure this is imported
from app.company_profiles.models import CompanyProfile
from app.company_profiles.schemas import CompanyProfileOut, CompanyProfileUpdate

router = APIRouter(prefix="/tenants/me/profile", tags=["Company Profile"])


@router.get("/", response_model=CompanyProfileOut)
def get_my_profile(
    x_tenant_id: int = Header(..., alias="X-Tenant-Id"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),  # RE-ENABLED
):
    # Standard multi-tenant security logic
    profile = (
        db.query(CompanyProfile).filter(CompanyProfile.tenant_id == x_tenant_id).first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.patch("/", response_model=CompanyProfileOut)
def update_my_profile(
    payload: CompanyProfileUpdate,
    x_tenant_id: int = Header(..., alias="X-Tenant-Id"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),  # RE-ENABLED
):
    profile = (
        db.query(CompanyProfile).filter(CompanyProfile.tenant_id == x_tenant_id).first()
    )
    if not profile:
        profile = CompanyProfile(tenant_id=x_tenant_id, company_name="New Firm")
        db.add(profile)

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(profile, key, value)

    db.commit()
    db.refresh(profile)
    return profile
