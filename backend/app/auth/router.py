from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

# Database & Security Imports
from app.database.db import get_db
from app.users.models import User
from app.core.security import verify_password, create_access_token
from app.auth.schemas import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["Auth"])


# ---------------------------------------------------------
# LOGIN ENDPOINT (Premium Safety Version)
# ---------------------------------------------------------
@router.post("/login", response_model=TokenResponse)
def login(
    data: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    High-performance login with Bcrypt 72-byte safety guard.
    """
    # 1. Find the user
    user = db.query(User).filter(User.email == data.email).first()

    if not user:
        raise HTTPException(
            status_code=401, detail="The credentials provided do not match our records."
        )

    # 2. VERIFY PASSWORD (With the 72-character safety truncation)
    # We cut the user's typed password to 72 chars to prevent Bcrypt crashes
    is_valid = verify_password(data.password[:72], user.hashed_password)

    if not is_valid:
        raise HTTPException(
            status_code=401, detail="The credentials provided do not match our records."
        )

    # 3. Security Checks
    if not user.is_active:
        raise HTTPException(
            status_code=400, detail="Account is inactive. Please contact support."
        )

    # 4. Success: Generate Secure JWT Token
    access_token = create_access_token(subject=user.email)

    return {"access_token": access_token, "token_type": "bearer"}


# ---------------------------------------------------------
# HELPER: CURRENT USER (Minimal Status Check)
# ---------------------------------------------------------
@router.get("/me")
def get_me():
    return {"status": "Auth system is operational", "security": "72-byte guard active"}
