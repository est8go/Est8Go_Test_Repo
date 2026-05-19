"""
EST8GO AUTH ROUTER v3.0
========================
Fort-Knox login with:
  - Account lockout (5 failed attempts → 30 min lock)
  - IP binding for platform users
  - Role-based token expiry
  - Suspicious login detection
  - Re-auth endpoint for destructive actions
  - Full audit trail on every login event
"""

from fastapi import APIRouter, Depends, HTTPException, Form, Request
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.users.models import User
from app.core.security import (
    verify_password,
    create_access_token,
    create_reauth_token,
    verify_reauth_token,
    is_account_locked,
    get_lockout_remaining,
    record_failed_attempt,
    clear_failed_attempts,
    MAX_FAILED_ATTEMPTS,
)
from app.auth.schemas import TokenResponse
from app.auth.deps import get_current_user
from app.database.audit import log_action

router = APIRouter(prefix="/auth", tags=["Auth"])


def get_client_ip(request: Request) -> str:
    """Extract real client IP, respecting reverse proxy headers."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ================================================================
# LOGIN
# ================================================================


@router.post("/login", response_model=TokenResponse)
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    EST8GO Secure Login v3.0
    - Account lockout after 5 failed attempts
    - IP binding for superuser/super_staff tokens
    - Role-based token expiry
    - Full audit trail
    """
    ip = get_client_ip(request)

    # ── 1. LOCKOUT CHECK ─────────────────────────────
    if is_account_locked(username):
        remaining = get_lockout_remaining(username)
        minutes = remaining // 60
        seconds = remaining % 60
        raise HTTPException(
            status_code=429,
            detail=f"Account temporarily locked due to too many failed attempts. "
            f"Try again in {minutes}m {seconds}s.",
        )

    # ── 2. FIND USER ─────────────────────────────────
    user = db.query(User).filter(User.email == username).first()

    # ── 3. VERIFY CREDENTIALS ────────────────────────
    if not user or not verify_password(password, user.hashed_password):
        attempts = record_failed_attempt(username)
        remaining_attempts = MAX_FAILED_ATTEMPTS - attempts

        # Log failed attempt
        log_action(
            db,
            actor=None,
            action="login_failed",
            target_table="users",
            target_id=user.id if user else None,
            new_value={"email": username, "ip": ip, "attempts": attempts},
            ip_address=ip,
        )

        if remaining_attempts <= 0:
            raise HTTPException(
                status_code=429,
                detail=f"Account locked for {30} minutes due to too many failed attempts.",
            )

        raise HTTPException(
            status_code=401,
            detail=f"Invalid credentials. {remaining_attempts} attempt(s) remaining before lockout.",
        )

    # ── 4. STATUS CHECK ──────────────────────────────
    if not user.is_active:
        raise HTTPException(
            status_code=403, detail="This account has been deactivated."
        )

    # ── 5. CLEAR FAILED ATTEMPTS ─────────────────────
    clear_failed_attempts(username)

    # ── 6. GENERATE TOKEN WITH ROLE-BASED EXPIRY ─────
    role = user.effective_role
    token = create_access_token(
        email=user.email,
        role=role,
        tenant_id=user.tenant_id,
        ip_address=ip,  # IP bound for superuser/super_staff
    )

    # ── 7. LOG SUCCESSFUL LOGIN ──────────────────────
    log_action(
        db,
        actor=user,
        action="login_success",
        target_table="users",
        target_id=user.id,
        new_value={"ip": ip, "role": role},
        ip_address=ip,
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": role,
        "is_superuser": role == "superuser",
        "tenant_id": user.tenant_id,
    }


# ================================================================
# RE-AUTHENTICATION — for destructive actions
# ================================================================


@router.post("/reauth")
def request_reauth(
    request: Request,
    password: str = Form(...),
    action: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Request a short-lived re-auth token to authorise ONE destructive action.
    Token expires in 5 minutes and is single-use by action name.

    Actions requiring re-auth:
      delete_tenant | trust_override | deactivate_staff |
      change_billing | create_superuser | export_data
    """
    DESTRUCTIVE_ACTIONS = {
        "delete_tenant",
        "trust_override",
        "deactivate_staff",
        "change_billing",
        "create_superuser",
        "export_data",
        "tenant_suspension",
        "bulk_operation",
    }

    if action not in DESTRUCTIVE_ACTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown action '{action}'. Re-auth not required for this operation.",
        )

    # Verify password again
    if not verify_password(password, current_user.hashed_password):
        ip = get_client_ip(request)
        log_action(
            db,
            actor=current_user,
            action="reauth_failed",
            target_table="users",
            target_id=current_user.id,
            new_value={"attempted_action": action, "ip": ip},
            ip_address=ip,
        )
        raise HTTPException(status_code=401, detail="Password verification failed.")

    ip = get_client_ip(request)
    token = create_reauth_token(
        email=current_user.email,
        action=action,
        ip_address=ip,
    )

    log_action(
        db,
        actor=current_user,
        action="reauth_granted",
        target_table="users",
        target_id=current_user.id,
        new_value={"action": action, "ip": ip},
        ip_address=ip,
    )

    return {
        "reauth_token": token,
        "action": action,
        "expires_in": 300,  # 5 minutes in seconds
        "message": f"Re-auth token granted for '{action}'. Valid for 5 minutes.",
    }


# ================================================================
# STATUS CHECK
# ================================================================


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.effective_role,
        "is_platform_user": current_user.is_platform_user,
        "tenant_id": current_user.tenant_id,
        "first_name": current_user.first_name,
        "is_active": current_user.is_active,
    }
