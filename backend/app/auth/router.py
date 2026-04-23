from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

# Database & Security Imports
from app.database.db import get_db
from app.users.models import User
from app.core.security import verify_password, create_access_token
from app.auth.schemas import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["Auth"])


# ---------------------------------------------------------
# LOGIN ENDPOINT (Aligned with Multi-tenant Security)
# ---------------------------------------------------------
@router.post("/login", response_model=TokenResponse)
def login(
    data: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    Premium Login: Generates a token that locks the user to their specific tenant.
    """
    # 1. Find the user
    user = db.query(User).filter(User.email == data.email).first()

    if not user:
        raise HTTPException(
            status_code=401, detail="The credentials provided do not match our records."
        )

    # 2. Verify Password (72-byte safety check)
    is_valid = verify_password(data.password, user.hashed_password)

    if not is_valid:
        raise HTTPException(
            status_code=401, detail="The credentials provided do not match our records."
        )

    # 3. Security Status Check
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is inactive.")

    # 4. THE FIX: Generate Token with User ID and Tenant ID
    # This matches the new signature: create_access_token(user_id, tenant_id)
    access_token = create_access_token(user_id=user.id, tenant_id=user.tenant_id)

    return {"access_token": access_token, "token_type": "bearer"}


# ---------------------------------------------------------
# MINIMAL STATUS CHECK
# ---------------------------------------------------------
@router.get("/me")
def get_me():
    return {"status": "Auth system is operational and multi-tenant aware."}
