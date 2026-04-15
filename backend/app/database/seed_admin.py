from sqlalchemy.exc import IntegrityError
from app.database.db import SessionLocal
from app.tenants.models import Tenant
from app.users.models import User
from app.core.security import hash_password


DEFAULT_TENANT_NAME = "Bravies Homz"
DEFAULT_ADMIN_EMAIL = "admin@bravieshomz.com"
DEFAULT_ADMIN_PASSWORD = "test123"


def seed_admin(
    tenant_name: str = DEFAULT_TENANT_NAME,
    admin_email: str = DEFAULT_ADMIN_EMAIL,
    admin_password: str = DEFAULT_ADMIN_PASSWORD,
):
    db = SessionLocal()
    try:
        # 1) Ensure tenant exists (create if missing)
        tenant = db.query(Tenant).filter(Tenant.name == tenant_name).first()
        if not tenant:
            tenant = Tenant(name=tenant_name)
            db.add(tenant)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                tenant = db.query(Tenant).filter(Tenant.name == tenant_name).first()
            db.refresh(tenant)

        # 2) Ensure admin exists for that tenant
        existing = (
            db.query(User)
            .filter(User.tenant_id == tenant.id, User.email == admin_email)
            .first()
        )
        if existing:
            print(f"✅ Admin already exists: {existing.email} (tenant_id={tenant.id})")
            return

        admin = User(
            tenant_id=tenant.id,
            email=admin_email,
            hashed_password=hash_password(admin_password),
            role="admin",
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        print(f"✅ Admin created: {admin.email} (tenant_id={tenant.id})")

    finally:
        db.close()


if __name__ == "__main__":
    seed_admin()