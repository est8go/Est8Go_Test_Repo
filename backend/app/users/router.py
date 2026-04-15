from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database.db import SessionLocal
from app.users.models import User
from app.core.security import hash_password
from app.auth.deps import get_current_user
from app.tenants.deps import get_tenant_id

router = APIRouter(prefix="/users", tags=["Users"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/")
def create_user(
    email: str,
    password: str,
    role: str = "staff",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # only admin can create users
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    if role not in ("admin", "staff"):
        raise HTTPException(status_code=400, detail="Invalid role")

    user = User(
        tenant_id=current_user.tenant_id,  # force same tenant
        email=email,
        hashed_password=hash_password(password),
        role=role,
    )

    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="User already exists")

    db.refresh(user)
    return {
        "id": user.id,
        "email": user.email,
        "tenant_id": user.tenant_id,
        "role": user.role,
    }


@router.get("/")
def list_users(
    tenant_id: int = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # only admin can list users
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    users = (
        db.query(User)
        .filter(User.tenant_id == tenant_id)
        .order_by(User.id.asc())
        .all()
    )
    return [
        {"id": u.id, "email": u.email, "tenant_id": u.tenant_id, "role": u.role}
        for u in users
    ]