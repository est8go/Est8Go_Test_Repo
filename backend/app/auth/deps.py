from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.users.models import User
from app.core.security import SECRET_KEY, ALGORITHM

# This creates the 'Authorize' button in Swagger
security = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    # 1. Ensure token exists
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing security token. Please login first.",
        )

    token = credentials.credentials

    # 2. Decode JWT
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        token_tenant_id: int = payload.get("tenant_id")

        if user_id is None or token_tenant_id is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")

    except JWTError:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    # 3. Validate X-Tenant-Id Header (Multi-tenancy Wall)
    header_tenant = request.headers.get("x-tenant-id")
    if not header_tenant:
        raise HTTPException(status_code=400, detail="Missing X-Tenant-Id header")

    # 4. CROSS-CHECK: Does the header match the token?
    # This prevents Tenant 1 from using their token to see Tenant 2's data.
    if int(header_tenant) != int(token_tenant_id):
        raise HTTPException(
            status_code=403, detail="Tenant access denied (ID Mismatch)"
        )

    # 5. Load user from DB
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User account no longer exists")

    # 6. Final verification
    if user.tenant_id != int(header_tenant):
        raise HTTPException(status_code=403, detail="Cross-tenant access forbidden")

    return user
