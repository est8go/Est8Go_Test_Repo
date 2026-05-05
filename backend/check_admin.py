from app.models_registry import register_all_models

register_all_models()

from app.database.db import get_db
from app.users.models import User

db = next(get_db())
admins = db.query(User).filter(User.is_superuser == True).all()

if not admins:
    print("❌ No superusers found in database")
else:
    for a in admins:
        print(
            f"Email: {a.email} | Superuser: {a.is_superuser} | Active: {a.is_active} | Tenant: {a.tenant_id}"
        )
