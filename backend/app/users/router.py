from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database.db import get_db
from app.users.models import User, TENANT_ROLES
from app.core.security import hash_password
from app.auth.deps import get_current_user, require_tenant_admin, require_superuser

router = APIRouter(prefix="/users", tags=["Users"])


# ================================================================
# SCHEMAS
# ================================================================


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    role: str = "realtor"
    first_name: str | None = None
    phone_number: str | None = None


class CreatePlatformUserRequest(BaseModel):
    email: EmailStr
    password: str
    role: str = "super_staff"
    first_name: str | None = None


class UserResponse(BaseModel):
    id: int
    email: str
    role: str
    first_name: str | None
    tenant_id: int | None
    is_active: bool
    is_platform_user: bool
    tenant_type: str | None = None  # agency | freelance | developer | investor

    class Config:
        from_attributes = True


# ================================================================
# CREATE USER (tenant admin creates users inside their tenant)
# ================================================================


@router.post("/", response_model=UserResponse)
def create_user(
    payload: CreateUserRequest,
    current_user: User = Depends(require_tenant_admin),
    db: Session = Depends(get_db),
):
    """
    Create a new user inside the current tenant.
    Only tenant admins and platform staff can do this.
    """
    if payload.role not in TENANT_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role '{payload.role}'. Must be one of: {', '.join(TENANT_ROLES)}",
        )

    user = User(
        tenant_id=current_user.tenant_id,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        first_name=payload.first_name,
        phone_number=payload.phone_number,
        is_active=True,
        is_platform_user=False,
    )

    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="A user with this email already exists."
        )

    db.refresh(user)
    return user


# ================================================================
# CREATE PLATFORM STAFF (superuser only)
# ================================================================


@router.post("/platform", response_model=UserResponse)
def create_platform_user(
    payload: CreatePlatformUserRequest,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    """
    Create an Est8Go platform staff account.
    Only the superuser (founder) can do this.
    """
    if payload.role not in ("superuser", "super_staff"):
        raise HTTPException(
            status_code=400,
            detail="Platform users must have role 'superuser' or 'super_staff'.",
        )

    user = User(
        tenant_id=None,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        first_name=payload.first_name,
        is_active=True,
        is_platform_user=True,
    )

    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="A user with this email already exists."
        )

    db.refresh(user)
    return user


# ================================================================
# LIST USERS
# ================================================================


@router.get("/", response_model=list[UserResponse])
def list_users(
    current_user: User = Depends(require_tenant_admin),
    db: Session = Depends(get_db),
):
    """
    List all users in the current user's tenant.
    Platform staff see all users across all tenants.
    """
    query = db.query(User)

    if not current_user.is_platform_user:
        query = query.filter(User.tenant_id == current_user.tenant_id)

    return query.order_by(User.id.asc()).all()


# ================================================================
# GET CURRENT USER PROFILE
# ================================================================


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Returns the currently authenticated user's profile."""
    return current_user


# ================================================================
# DEACTIVATE USER
# ================================================================


@router.patch("/{user_id}/deactivate")
def deactivate_user(
    user_id: int,
    current_user: User = Depends(require_tenant_admin),
    db: Session = Depends(get_db),
):
    """Deactivate a user. Admins can only deactivate users in their own tenant."""
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if not current_user.is_platform_user and user.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied.")

    if user.effective_role == "superuser":
        raise HTTPException(
            status_code=403, detail="Cannot deactivate the superuser account."
        )

    user.is_active = False
    db.commit()

    return {"message": f"User {user.email} has been deactivated."}
