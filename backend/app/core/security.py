import os
from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext

# 1. Setup Modern Security Context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 2. Configuration (Fetched from Render/Local .env)
SECRET_KEY = os.getenv("SECRET_KEY", "est8go_ultra_secret_2024")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 1 Week


def get_password_hash(password: str) -> str:
    """Hashes password with professional safety truncation at 72 bytes."""
    return pwd_context.hash(password[:72])


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Safely verifies password against the database hash."""
    try:
        return pwd_context.verify(plain_password[:72], hashed_password)
    except Exception:
        return False


def create_access_token(user_id: int, tenant_id: int) -> str:
    """
    PREMIUM TOKEN GENERATION:
    Includes both User Identity and Tenant Identity for cross-tenant safety.
    """
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"exp": expire, "sub": str(user_id), "tenant_id": tenant_id}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# Alias for compatibility with existing business logic
hash_password = get_password_hash
