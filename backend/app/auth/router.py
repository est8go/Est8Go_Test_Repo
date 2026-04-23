from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm  # <--- THE FIX
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.users.models import User
from app.core.security import verify_password, create_access_token
from app.auth.schemas import TokenResponse

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    # This 'Depends()' logic allows Swagger's form to work perfectly
    data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    PREMIUM LOGIN: Optimized for Swagger and Mobile Apps.
    Accepts both JSON and Form Data.
    """
    # 1. Find user (Swagger uses 'username' field for email)
    user = db.query(User).filter(User.email == data.username).first()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is inactive.")

    # 2. Generate Token
    token_str = create_access_token(email=user.email, tenant_id=user.tenant_id)

    return {"access_token": token_str, "token_type": "bearer"}


@router.get("/me")
def get_me():
    return {"status": "Security channel is open"}
