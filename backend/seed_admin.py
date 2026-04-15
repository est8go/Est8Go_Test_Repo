from __future__ import annotations

import os
from typing import Optional

from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.database.db import SessionLocal
from app.tenants.models import Tenant
from app.users.models import User


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _env(name: str, default: Optional[str] = None) -> str:
    v = os.getenv(name)
    return v if v not in (None, "") else (default or "")


def _hash_password(password: str) -> str:
    return pwd_context.hash(password)


def _set_if_exists(obj, key: str, value) -> None:
    """
    Defensive: set attribute only if the model actually has that field.
    Prevents errors like: 'is_active' invalid keyword argument.
    """
    if hasattr(obj, key):
        setattr(obj, key, value)


def main() -> None:
    # You can override these in .env if you want
    TENANT_NAME = _env("SEED_TENANT_NAME", "Bravies Homz")
    ADMIN_EMAIL = _env("SEED_ADMIN_EMAIL", "admin@bravieshomz.com")
    ADMIN_PASSWORD = _env("SEED_ADMIN_PASSWORD", "test123")

    db: Session = SessionLocal()
    try:
        # 1) Ensure tenant exists
        tenant = db.query(Tenant).filter(Tenant.name == TENANT_NAME).first()
        if not tenant:
            tenant = Tenant(name=TENANT_NAME)
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
            print(f"[OK] Tenant created: {tenant.name} (id={tenant.id})")
        else:
            print(f"[OK] Tenant exists: {tenant.name} (id={tenant.id})")

        # 2) Ensure admin user exists
        user = db.query(User).filter(User.email == ADMIN_EMAIL).first()
        if user:
            print(f"[OK] User already exists: {ADMIN_EMAIL} (tenant_id={getattr(user, 'tenant_id', None)})")
            return

        user = User()
        _set_if_exists(user, "email", ADMIN_EMAIL)
        _set_if_exists(user, "tenant_id", tenant.id)

        # Password field name varies across projects: try common ones
        hashed = _hash_password(ADMIN_PASSWORD)
        if hasattr(user, "hashed_password"):
            user.hashed_password = hashed
        elif hasattr(user, "password_hash"):
            user.password_hash = hashed
        elif hasattr(user, "password"):
            # not recommended, but some MVPs store plain 'password' column
            user.password = hashed
        else:
            raise RuntimeError(
                "Your User model has no hashed password field. "
                "Expected one of: hashed_password / password_hash / password."
            )

        # Optional flags if your model supports them
        _set_if_exists(user, "is_superuser", True)
        _set_if_exists(user, "is_admin", True)
        _set_if_exists(user, "role", "admin")

        db.add(user)
        db.commit()
        db.refresh(user)

        print(f"[OK] Admin user created: {ADMIN_EMAIL}")
        print(f"     tenant_id: {getattr(user, 'tenant_id', None)}")
        print(f"     user_id: {getattr(user, 'id', None)}")
        print(f"     password: {ADMIN_PASSWORD}  (change later)")

    finally:
        db.close()


if __name__ == "__main__":
    main()