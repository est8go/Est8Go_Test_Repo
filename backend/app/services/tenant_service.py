from sqlalchemy.orm import Session
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.tenants.models import Tenant


def create_tenant_service(name: str, db: Session):
    tenant = Tenant(name=name)

    db.add(tenant)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Tenant name already exists")

    db.refresh(tenant)

    return {"id": tenant.id, "name": tenant.name}


def list_tenants_service(db: Session):
    tenants = db.query(Tenant).order_by(Tenant.id.asc()).all()

    return [{"id": t.id, "name": t.name} for t in tenants]


def get_tenant_profile(db: Session, tenant_id: int):
    """
    Retrieves the identity and persona of a tenant.
    """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()

    if tenant:
        return {
            "business_name": tenant.business_name or tenant.name,
            "tone": tenant.tone,
            "emoji": tenant.emoji,
            "slug": tenant.slug or "",
            "areas_covered": tenant.areas_covered or "Abuja",
            "coverage_cities": getattr(tenant, "coverage_cities", []) or [],
        }

    # Standard fallback if tenant is not found
    return {"business_name": "your realtor", "tone": "friendly", "emoji": "😊"}
