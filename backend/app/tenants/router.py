from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.db import SessionLocal
from app.services.tenant_service import (
    create_tenant_service,
    list_tenants_service,
)

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