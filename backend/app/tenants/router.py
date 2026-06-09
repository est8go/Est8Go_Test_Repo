from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List
from sqlalchemy.orm import Session

from app.database.db import SessionLocal
from app.services.tenant_service import (
    create_tenant_service,
    list_tenants_service,
)
from app.tenants.models import Tenant
from app.auth.deps import require_superuser

router = APIRouter(prefix="/tenants", tags=["Tenants"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/")
def create_tenant(name: str, db: Session = Depends(get_db)):
    return create_tenant_service(name, db)


@router.get("/")
def list_tenants(db: Session = Depends(get_db)):
    return list_tenants_service(db)


class CoverageCitiesPayload(BaseModel):
    cities: List[str] = []


@router.patch("/{tenant_id}/coverage-cities")
def update_coverage_cities(
    tenant_id: int,
    payload: CoverageCitiesPayload,
    db: Session = Depends(get_db),
    current_user=Depends(require_superuser),
):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    tenant.coverage_cities = payload.cities
    db.commit()
    return {"tenant_id": tenant_id, "coverage_cities": payload.cities}