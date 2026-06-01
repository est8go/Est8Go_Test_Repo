from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database.db import get_db
from app.users.models import User, TENANT_ROLES
from app.core.security import hash_password
from app.auth.deps import get_current_user, require_tenant_admin, require_superuser
from app.tenants.models import Tenant
from app.credits.seat_service import (
    check_can_add_staff,
    get_base_seat_limit,
    purchase_extra_seat,
    EXTRA_SEAT_COST,
)

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
    business_name: str | None = None  # from tenants table
    tenant_plan: str | None = None  # pilot | starter | growth | enterprise

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
    Enforces plan seat limits. Extra seats cost 800 credits/month.
    Only tenant admins and platform staff can do this.
    """
    if payload.role not in TENANT_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role '{payload.role}'. Must be one of: {', '.join(TENANT_ROLES)}",
        )

    # ── SEAT LIMIT ENFORCEMENT ───────────────────────────────────
    tenant = db.query(Tenant).filter(
        Tenant.id == current_user.tenant_id
    ).first()

    if not tenant:
        raise HTTPException(400, "Tenant not found.")

    allowed, reason = check_can_add_staff(current_user.tenant_id, db)

    needs_extra_seat = False

    if not allowed:
        is_freelance = tenant.tenant_type == "freelance"
        base_limit = get_base_seat_limit(tenant.plan)
        is_enterprise = base_limit is None

        if is_freelance:
            raise HTTPException(status_code=403, detail=reason)

        if not is_enterprise:
            # Check if tenant has enough credits to buy an extra seat
            from app.credits.service import get_or_create_wallet
            wallet = get_or_create_wallet(current_user.tenant_id, db)
            available = (
                wallet.purchased_balance + wallet.bonus_balance - wallet.reserved
            )
            if available < EXTRA_SEAT_COST:
                raise HTTPException(
                    status_code=402,
                    detail=(
                        f"{reason} "
                        f"Extra seats cost {EXTRA_SEAT_COST} credits/month. "
                        f"You have {available} credits available. "
                        f"Top up your credits to add more staff."
                    ),
                )
            needs_extra_seat = True
        # enterprise: unlimited seats — fall through, needs_extra_seat stays False

    # ── CREATE USER ──────────────────────────────────────────────
    user = User(
        tenant_id        = current_user.tenant_id,
        email            = payload.email,
        hashed_password  = hash_password(payload.password),
        role             = payload.role,
        first_name       = payload.first_name,
        phone_number     = payload.phone_number,
        is_active        = True,
        is_platform_user = False,
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

    # ── PURCHASE EXTRA SEAT IF NEEDED ────────────────────────────
    if needs_extra_seat:
        try:
            purchase_extra_seat(
                tenant_id    = current_user.tenant_id,
                user_id      = user.id,
                db           = db,
                purchased_by = current_user.id,
            )
        except ValueError as e:
            # Roll back user creation if seat purchase fails
            db.delete(user)
            db.commit()
            raise HTTPException(status_code=402, detail=str(e))

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
def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns the currently authenticated user's profile with tenant context."""
    from app.tenants.models import Tenant

    # Build response with tenant fields resolved
    tenant_type = None
    business_name = None
    tenant_plan = None
    if current_user.tenant_id:
        tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
        if tenant:
            tenant_type = tenant.tenant_type
            business_name = tenant.business_name or tenant.name
            tenant_plan = tenant.plan
    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.effective_role,
        "first_name": current_user.first_name,
        "tenant_id": current_user.tenant_id,
        "is_active": current_user.is_active,
        "is_platform_user": current_user.is_platform_user,
        "tenant_type": tenant_type,
        "business_name": business_name,
        "tenant_plan": tenant_plan,
    }


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
