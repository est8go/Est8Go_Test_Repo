from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.db import get_db
from app.auth.deps import get_current_user
from app.company_profiles.models import CompanyProfile
from app.company_profiles.schemas import CompanyProfileOut, CompanyProfileUpdate

router = APIRouter(prefix="/tenants/me/profile", tags=["Company Profile"])


@router.get("/", response_model=CompanyProfileOut)
def get_my_profile(
    db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    profile = (
        db.query(CompanyProfile)
        .filter(CompanyProfile.tenant_id == current_user.tenant_id)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.patch("/", response_model=CompanyProfileOut)
def update_my_profile(
    payload: CompanyProfileUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    profile = (
        db.query(CompanyProfile)
        .filter(CompanyProfile.tenant_id == current_user.tenant_id)
        .first()
    )
    if not profile:
        profile = CompanyProfile(
            tenant_id=current_user.tenant_id, company_name="New Firm"
        )
        db.add(profile)

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(profile, key, value)

    db.commit()
    db.refresh(profile)
    return profile
