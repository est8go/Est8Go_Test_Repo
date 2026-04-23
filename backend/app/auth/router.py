from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session

# Database & Security Imports
from app.database.db import get_db
from app.users.models import User
from app.core.security import verify_password, create_access_token
from app.auth.schemas import TokenResponse

router = APIRouter(prefix="/auth", tags=["Auth"])


# ---------------------------------------------------------
# CLEAN LOGIN ENDPOINT
# ---------------------------------------------------------
@router.post("/login", response_model=TokenResponse)
def login(
    # By using 'Form' instead of the generic OAuth2 tool,
    # we remove all the messy 'client_id' and 'scope' boxes from Swagger.
    username: str = Form(..., description="Your registered email address"),
    password: str = Form(..., description="Your secure password"),
    db: Session = Depends(get_db),
):
    """
    PREMIUM LOGIN: Optimized for est8go Service Limited.
    Only shows Email and Password fields.
    """
    # 1. Locate the User
    user = db.query(User).filter(User.email == username).first()

    # 2. Verify Credentials
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=401, detail="The credentials provided do not match our records."
        )

    # 3. Status Check
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is inactive.")

    # 4. Success: Generate Secure Multi-tenant Token
    token_str = create_access_token(email=user.email, tenant_id=user.tenant_id)

    return {"access_token": token_str, "token_type": "bearer"}


# ---------------------------------------------------------
# MINIMAL STATUS CHECK
# ---------------------------------------------------------
@router.get("/me")
def get_me():
    return {"status": "Security channel is open and clean."}
