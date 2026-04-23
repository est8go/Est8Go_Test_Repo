from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.users.models import User
from app.core.security import SECRET_KEY, ALGORITHM

# oauth2_scheme handles the 'Authorize' button in Swagger
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    request: Request, db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_email: str = payload.get("sub")
        token_tenant_id: int = payload.get("tenant_id")

        if not user_email:
            raise HTTPException(status_code=401, detail="Invalid token")

    except JWTError:
        raise HTTPException(status_code=401, detail="Session expired")

    header_tenant = request.headers.get("x-tenant-id")
    if not header_tenant:
        raise HTTPException(status_code=400, detail="Missing X-Tenant-Id header")

    # Verify Token matches Header
    if int(header_tenant) != int(token_tenant_id):
        raise HTTPException(status_code=403, detail="Tenant ID mismatch")

    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user
