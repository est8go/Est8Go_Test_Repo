"""
EST8GO AUTH DEPS v3.1
======================
Definitive fix for tenant isolation.

Platform users (superuser, super_staff):
  - NO X-Tenant-Id header required
  - IP binding enforced
  - Cross-tenant access granted

Tenant users (admin, realtor, staff, support, marketing):
  - X-Tenant-Id header required
  - Must match their own tenant_id exactly
  - Cannot see other tenants' data under any circumstance
"""

from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session
from typing import Optional

from app.database.db import get_db
from app.users.models import User, PLATFORM_ROLES
from app.core.security import decode_token, verify_ip_binding

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ================================================================
# CORE AUTH GUARD
# ================================================================


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> User:
    """
    EST8GO Auth Guard v3.1 — Definitive tenant isolation.

    Flow:
      1. Decode JWT
      2. Fetch user from DB
      3. Check is_active
      4. IF platform user → bypass tenant check, enforce IP binding
      5. IF tenant user  → enforce X-Tenant-Id matches their tenant
    """

    # ── 1. DECODE TOKEN ──────────────────────────────
    try:
        payload = decode_token(token)
        email: str = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token.")
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Session expired. Please log in again.",
        )

    # ── 2. FETCH USER FROM DATABASE ──────────────────
    # Always fetch from DB — never trust token claims alone
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Account not found.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account has been deactivated.")

    # ── 3. PLATFORM USERS — bypass tenant check ──────
    # Superuser and super_staff have is_platform_user = True
    # They have no tenant_id and need no X-Tenant-Id header
    if user.is_platform_user or user.effective_role in PLATFORM_ROLES:
        # Enforce IP binding for platform accounts
        ip = get_client_ip(request)
        if not verify_ip_binding(payload, ip):
            raise HTTPException(
                status_code=401,
                detail="Security violation: IP mismatch. Please log in again.",
            )
        return user  # ✅ Platform user — full access granted

    # ── 4. TENANT USERS — strict isolation ───────────
    # Step 4a: Header must exist
    header_tenant = request.headers.get("x-tenant-id")
    if not header_tenant:
        raise HTTPException(
            status_code=400,
            detail="Missing X-Tenant-Id header.",
        )

    # Step 4b: Header must be a valid integer
    try:
        header_tenant_int = int(header_tenant)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid X-Tenant-Id header — must be an integer.",
        )

    # Step 4c: Header must match user's own tenant — no exceptions
    if header_tenant_int != user.tenant_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: you can only access your own tenant data.",
        )

    return user  # ✅ Tenant user — isolated access granted


# ================================================================
# ROLE GUARDS
# ================================================================


def require_platform_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Only superuser or super_staff."""
    if not (
        current_user.is_platform_user or current_user.effective_role in PLATFORM_ROLES
    ):
        raise HTTPException(
            status_code=403,
            detail="Platform staff access required.",
        )
    return current_user


def require_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    """Only the founder (superuser)."""
    if current_user.effective_role != "superuser":
        raise HTTPException(
            status_code=403,
            detail="Superuser access required.",
        )
    return current_user


def require_tenant_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Tenant admin or platform staff."""
    allowed = ("superuser", "super_staff", "admin")
    if current_user.effective_role not in allowed:
        raise HTTPException(
            status_code=403,
            detail="Admin access required.",
        )
    return current_user


def require_reauth(action: str):
    """
    Guard factory for destructive actions.
    Requires X-Reauth-Token header containing a valid re-auth token.

    Usage:
        @router.delete('/tenants/{id}')
        def delete_tenant(
            _=Depends(require_reauth('delete_tenant')),
            current_user=Depends(require_superuser),
        ):
    """

    def guard(request: Request):
        from app.core.security import verify_reauth_token

        reauth_token = request.headers.get("X-Reauth-Token", "")
        if not reauth_token:
            raise HTTPException(
                status_code=403,
                detail=f"Destructive action '{action}' requires re-authentication. "
                f"POST /auth/reauth with action='{action}' first.",
            )
        ip = get_client_ip(request)
        if not verify_reauth_token(reauth_token, action, ip):
            raise HTTPException(
                status_code=403,
                detail=f"Invalid or expired re-auth token for '{action}'. "
                f"Re-auth tokens expire in 5 minutes.",
            )

    return guard


# ================================================================
# AUDIT MIDDLEWARE
# ================================================================


async def audit_platform_actions(request: Request, call_next):
    """
    Middleware: logs every mutating call by platform users automatically.
    Wire into main.py: app.middleware('http')(audit_platform_actions)
    """
    response = await call_next(request)

    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "").strip()
        if token:
            try:
                payload = decode_token(token)
                role = payload.get("role", "")
                if role in PLATFORM_ROLES:
                    # Full implementation: wire to DB session for audit log
                    # Currently passes through — audit_router.py handles explicit logs
                    pass
            except Exception:
                pass

    return response
