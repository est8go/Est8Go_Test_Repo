import os
from datetime import datetime, timedelta
from typing import Any, Union  # (Optional is removed)
from jose import jwt
from passlib.context import CryptContext

# 1. Setup Security Context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = os.getenv("SECRET_KEY", "bravies_homz_secret_2024")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 1 Week


def get_password_hash(password: str) -> str:
    """Hashes password with a 72-character limit for Bcrypt safety."""
    return pwd_context.hash(password[:72])


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies password using the 72-character safety limit."""
    return pwd_context.verify(plain_password[:72], hashed_password)


def create_access_token(
    subject: Union[str, Any], expires_delta: timedelta = None
) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
