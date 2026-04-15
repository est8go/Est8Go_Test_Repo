from app.database.db import SessionLocal
from app.users.models import User
from app.core.security import hash_password
from app.tenants.models import Tenant  # noqa: F401



def reset_password(email: str, new_password: str) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise RuntimeError(f"User not found: {email}")

        user.hashed_password = hash_password(new_password)
        db.commit()
        print(f"✅ Password reset (hashed) for: {email}")
    finally:
        db.close()


if __name__ == "__main__":
    reset_password("admin@bravieshomz.com", "test123")
