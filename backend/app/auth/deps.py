from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.users.models import User
from app.core.security import SECRET_KEY, ALGORITHM

# This tool creates the 'Authorize' button in Swagger
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    request: Request, db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    """
    PREMIUM SECURITY GUARD:
    Allows Superusers (Landlords) access to everything.
    Locks Tenants (Realtors) into their own data.
    """
    try:
        # 1. Decode the Token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_email: str = payload.get("sub")
        token_tenant_id: int = payload.get("tenant_id")

        if not user_email:
            raise HTTPException(status_code=401, detail="Invalid token")

    except JWTError:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    # 2. Fetch User from Database
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(status_code=401, detail="User account not found")

    # 3. Get the X-Tenant-Id from the Swagger Header
    header_tenant = request.headers.get("x-tenant-id")
    if not header_tenant:
        raise HTTPException(status_code=400, detail="Missing X-Tenant-Id header")

    # 4. THE MASTER KEY LOGIC (The Fix)
    # If you are NOT a superuser, we enforce the strict mismatch check.
    # If you ARE a superuser, we skip this check so you can manage other tenants.
    if not user.is_superuser:
        if int(header_tenant) != int(token_tenant_id):
            raise HTTPException(
                status_code=403,
                detail="Tenant ID mismatch: Realtors can only access their own data.",
            )

    return user
