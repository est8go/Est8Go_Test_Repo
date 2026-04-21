from sqlalchemy.orm import Session
from app.database.db import SessionLocal
from app.users.models import User
from app.tenants.models import Tenant
from app.core.security import get_password_hash


def repair():
    db: Session = SessionLocal()
    email = "admin@bravieshomz.com"
    password = "test123"  # Modern, safe password

    try:
        print("🚀 Starting Nuclear Repair...")

        # 1. Fix Tenant First
        tenant = db.query(Tenant).filter(Tenant.id == 1).first()
        if not tenant:
            tenant = Tenant(id=1, name="Bravies Homz", plan="pilot")
            db.add(tenant)
        else:
            tenant.plan = "pilot"

        db.commit()
        print("✅ Tenant is Healthy.")

        # 2. Fix User with MODERN hashing
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(email=email, tenant_id=1)
            db.add(user)

        # This uses the REAL code logic to hash, ensuring NO 'Malformed' errors
        user.hashed_password = get_password_hash(password)
        user.is_active = True
        user.is_admin = True
        user.is_superuser = True

        db.commit()
        print(f"✅ User {email} is Healthy and Verified.")
        print(f"\n🚀 SUCCESS! Use password: {password}")

    except Exception as e:
        print(f"❌ Repair Failed: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    repair()
