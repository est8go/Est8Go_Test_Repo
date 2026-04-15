from fastapi import Header, HTTPException, status, Request
from jose import jwt, JWTError

from app.core.config import settings

from fastapi import Header, HTTPException


def get_public_tenant_id(x_tenant_id: int = Header(...)):
    """
    Public routes: trust tenant via header only (paired with API key)
    """
    if not x_tenant_id:
        raise HTTPException(
            status_code=400,
            detail="X-Tenant-Id header missing",
        )

    return x_tenant_id


def get_tenant_id(
    request: Request,
    x_tenant_id: int = Header(...),  # 👈 THIS MAKES IT VISIBLE
):
    # 1. Get Authorization header
    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    token = auth_header.split(" ")[1]

    # 2. Decode JWT
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        token_tenant_id = payload.get("tenant_id")
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    if not token_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    # 3. CRITICAL CHECK
    if x_tenant_id != int(token_tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant mismatch",
        )

    return x_tenant_id