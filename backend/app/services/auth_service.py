from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.users.models import User
from app.core.security import verify_password, create_access_token


def login_user(email: str, password: str, db: Session):
    # 1. Find user
    user = db.query(User).filter(User.email == email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # 2. Verify password
    if not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # 3. Create token
    token = create_access_token(
        data={
            "sub": str(user.id),
            "tenant_id": user.tenant_id,
        }
    )

    # 4. Return response
    return {
        "access_token": token,
        "token_type": "bearer",
    }