from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from app.database.db import get_db
from app.auth.deps import get_current_user
from app.company_profiles.models import CompanyProfile
from app.company_profiles.schemas import CompanyProfileOut, CompanyProfileUpdate

router = APIRouter(prefix="/tenants/me/profile", tags=["Company Profile"])


@router.get("", response_model=CompanyProfileOut)
def get_my_profile(
    x_tenant_id: int = Header(..., alias="X-Tenant-Id"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # 🛡️ SUPERUSER LOGIC: Use the header ID if superuser, otherwise lock to their own ID
    target_tenant_id = (
        x_tenant_id if current_user.is_superuser else current_user.tenant_id
    )

    profile = (
        db.query(CompanyProfile)
        .filter(CompanyProfile.tenant_id == target_tenant_id)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.patch("", response_model=CompanyProfileOut)
def update_my_profile(
    payload: CompanyProfileUpdate,
    x_tenant_id: int = Header(..., alias="X-Tenant-Id"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # 🛡️ SUPERUSER LOGIC
    target_tenant_id = (
        x_tenant_id if current_user.is_superuser else current_user.tenant_id
    )

    profile = (
        db.query(CompanyProfile)
        .filter(CompanyProfile.tenant_id == target_tenant_id)
        .first()
    )

    if not profile:
        # Create a fresh profile for the target company
        profile = CompanyProfile(
            tenant_id=target_tenant_id, company_name=payload.company_name or "New Firm"
        )
        db.add(profile)

    # Apply the updates from Swagger
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(profile, key, value)

    try:
        db.commit()
        db.refresh(profile)
        return profile
    except Exception as e:
        db.rollback()
        print(f"❌ PROFILE SAVE ERROR: {e}")
        raise HTTPException(
            status_code=500, detail="Database integrity error. Check Render logs."
        )
