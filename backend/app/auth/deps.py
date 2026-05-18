from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.users.models import User, PLATFORM_ROLES
from app.core.security import SECRET_KEY, ALGORITHM

# Creates the 'Authorize' button in Swagger
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> User:
    """
    EST8GO AUTH GUARD v2.0
    ========================
    - Platform users (superuser, super_staff) → cross-tenant access, no tenant header needed
    - Tenant users (admin, realtor, staff etc) → locked to their own tenant via header check
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_email: str = payload.get("sub")

        if not user_email:
            raise HTTPException(status_code=401, detail="Invalid token.")

    except JWTError:
        raise HTTPException(status_code=401, detail="Session expired or invalid.")

    # Fetch user from database
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(status_code=401, detail="User account not found.")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive.")

    # Platform users (superuser, super_staff) bypass tenant checks entirely
    if user.is_platform_user or user.effective_role in PLATFORM_ROLES:
        return user

    # Tenant users must provide X-Tenant-Id header
    header_tenant = request.headers.get("x-tenant-id")
    if not header_tenant:
        raise HTTPException(status_code=400, detail="Missing X-Tenant-Id header.")

    # Enforce tenant isolation — users can only access their own tenant
    if int(header_tenant) != int(user.tenant_id):
        raise HTTPException(
            status_code=403,
            detail="Access denied: you can only access your own tenant data.",
        )

    return user


def require_platform_user(current_user: User = Depends(get_current_user)) -> User:
    """Guard: only superuser or super_staff can pass."""
    if (
        not current_user.is_platform_user
        and current_user.effective_role not in PLATFORM_ROLES
    ):
        raise HTTPException(
            status_code=403,
            detail="Platform staff access required.",
        )
    return current_user


def require_superuser(current_user: User = Depends(get_current_user)) -> User:
    """Guard: only the founder (superuser) can pass."""
    if current_user.effective_role != "superuser":
        raise HTTPException(
            status_code=403,
            detail="Superuser access required.",
        )
    return current_user


def require_tenant_admin(current_user: User = Depends(get_current_user)) -> User:
    """Guard: tenant admin or platform staff can pass."""
    allowed = ("superuser", "super_staff", "admin")
    if current_user.effective_role not in allowed:
        raise HTTPException(
            status_code=403,
            detail="Admin access required.",
        )
    return current_user
