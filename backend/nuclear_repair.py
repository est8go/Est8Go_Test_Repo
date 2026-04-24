import sys
import os

# Ensure the script can see the 'app' folder
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.database.db import SessionLocal
from app.users.models import User
from app.core.security import get_password_hash

# THE FIX: Import the registry to wire the 'Tenant' and 'User' together
from app.models_registry import register_all_models


def repair_all_admins():
    # 1. Start the Handshake (Fixes the 'Tenant not found' error)
    register_all_models()

    db: Session = SessionLocal()

    accounts = [
        {"email": "est8go@gmail.com", "role": "superuser", "tenant": 1, "super": True},
        {
            "email": "admin@bravieshomz.com",
            "role": "admin",
            "tenant": 1,
            "super": False,
        },
        {"email": "admin@trusthomes.com", "role": "admin", "tenant": 2, "super": False},
    ]

    try:
        print("🛠 Starting Handshake and Triple-Admin Repair...")

        for acc in accounts:
            user = db.query(User).filter(User.email == acc["email"]).first()

            if not user:
                # Create if missing
                user = User(email=acc["email"], tenant_id=acc["tenant"])
                db.add(user)

            # Apply modern security
            user.hashed_password = get_password_hash("test123")
            user.role = acc["role"]
            user.is_active = True
            user.is_admin = True
            user.is_superuser = acc["super"]

            print(f"✅ Repaired: {acc['email']}")

        db.commit()
        print("\n🚀 SUCCESS! All 3 accounts are live with password: test123")

    except Exception as e:
        print(f"❌ Repair Failed: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    repair_all_admins()
