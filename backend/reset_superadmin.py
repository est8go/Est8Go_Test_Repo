from app.models_registry import register_all_models

register_all_models()

from app.database.db import get_db
from app.users.models import User
from app.core.security import hash_password

db = next(get_db())

user = db.query(User).filter(User.email == "est8go@gmail.com").first()

if not user:
    print("❌ User not found")
else:
    new_password = "Est8Go@2026"
    user.hashed_password = hash_password(new_password)
    db.commit()
    print(f"✅ Password reset for {user.email}")
    print(f"   New password: {new_password}")
