from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.users.models import User
from app.core.security import verify_password, create_access_token
from app.auth.schemas import TokenResponse

router = APIRouter(prefix="/auth", tags=["Auth"])


# ---------------------------------------------------------
# LOGIN ENDPOINT — returns full role context for frontend routing
# ---------------------------------------------------------
@router.post("/login", response_model=TokenResponse)
def login(
    username: str = Form(..., description="Your registered email address"),
    password: str = Form(..., description="Your secure password"),
    db: Session = Depends(get_db),
):
    """
    EST8GO LOGIN: Returns token + role context for frontend redirect.
    Superusers → Super Admin Portal
    Regular users → Realtor Portal
    """
    # 1. Locate the User
    user = db.query(User).filter(User.email == username).first()

    # 2. Verify Credentials
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="The credentials provided do not match our records.",
        )

    # 3. Status Check
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is inactive.")

    # 4. Generate Token
    token_str = create_access_token(email=user.email, tenant_id=user.tenant_id)

    # 5. Determine Role for frontend routing
    role = (
        "superuser" if user.is_superuser else ("admin" if user.is_admin else "realtor")
    )

    return {
        "access_token": token_str,
        "token_type": "bearer",
        "role": role,
        "is_superuser": user.is_superuser,
        "tenant_id": user.tenant_id,
    }


# ---------------------------------------------------------
# STATUS CHECK
# ---------------------------------------------------------
@router.get("/me")
def get_me():
    return {"status": "Security channel is open and clean."}
