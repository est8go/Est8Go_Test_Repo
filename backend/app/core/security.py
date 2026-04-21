import os
from datetime import datetime, timedelta
from typing import Any, Union
from jose import jwt
from passlib.context import CryptContext

# 1. Modern Security Context (Automated & Stable)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = os.getenv("SECRET_KEY", "est8go_ultra_secret_2024")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7


def get_password_hash(password: str) -> str:
    """Standard professional hashing. No manual truncation needed."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Standard professional verification. Handles all edge cases."""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def create_access_token(
    subject: Union[str, Any], expires_delta: timedelta = None
) -> str:
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    encoded_jwt = jwt.encode(
        {"exp": expire, "sub": str(subject)}, SECRET_KEY, algorithm=ALGORITHM
    )
    return encoded_jwt


# Alias for old code compatibility
hash_password = get_password_hash
