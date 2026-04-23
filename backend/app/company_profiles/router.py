from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.auth.deps import get_current_user
from app.company_profiles.models import CompanyProfile
from app.company_profiles.schemas import CompanyProfileOut, CompanyProfileUpdate

# We remove the trailing slash from the prefix for standard routing
router = APIRouter(prefix="/tenants/me/profile", tags=["Company Profile"])


@router.get("", response_model=CompanyProfileOut)
def get_my_profile(
    x_tenant_id: int = Header(..., alias="X-Tenant-Id"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Fetches the profile for the company ID provided in the header.
    """
    # 1. Fetch from database
    profile = (
        db.query(CompanyProfile).filter(CompanyProfile.tenant_id == x_tenant_id).first()
    )

    # 2. Precise Error Handling: This tells us IF the data is missing
    if not profile:
        raise HTTPException(
            status_code=404,
            detail=f"Identity record for Tenant ID {x_tenant_id} does not exist in the database.",
        )

    return profile


@router.patch("", response_model=CompanyProfileOut)
def update_my_profile(
    payload: CompanyProfileUpdate,
    x_tenant_id: int = Header(..., alias="X-Tenant-Id"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    profile = (
        db.query(CompanyProfile).filter(CompanyProfile.tenant_id == x_tenant_id).first()
    )

    if not profile:
        profile = CompanyProfile(
            tenant_id=x_tenant_id, company_name="Initial Registration"
        )
        db.add(profile)

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(profile, key, value)

    db.commit()
    db.refresh(profile)
    return profile
