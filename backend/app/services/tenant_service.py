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

    return {
        "id": tenant.id,
        "name": tenant.name
    }


def list_tenants_service(db: Session):
    tenants = db.query(Tenant).order_by(Tenant.id.asc()).all()

    return [
        {"id": t.id, "name": t.name}
        for t in tenants
    ]


def get_tenant_or_404(tenant_id: int, db: Session):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    return tenant