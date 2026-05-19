"""
EST8GO — Superuser Password Reset Script
=========================================
Run this script ONCE on your local machine or Render shell to reset
the superuser password and get the correct bcrypt hash.

HOW TO RUN:
  1. Open PowerShell in your backend folder
  2. Activate your virtual environment:
       .venv\Scripts\activate
  3. Run:
       python reset_superuser.py

It will print the SQL to run in Supabase.
"""

from passlib.context import CryptContext
from app.database.db import SessionLocal
from app.users.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── SET YOUR NEW PASSWORD HERE ──────────────────────
NEW_PASSWORD = "Est8Go@2026#Secure"
SUPERUSER_EMAIL = "est8go@gmail.com"
# ────────────────────────────────────────────────────


def reset_superuser():
    hashed = pwd_context.hash(NEW_PASSWORD[:72])

    print("\n" + "=" * 60)
    print("EST8GO SUPERUSER PASSWORD RESET")
    print("=" * 60)
    print(f"\nEmail:    {SUPERUSER_EMAIL}")
    print(f"Password: {NEW_PASSWORD}")
    print(f"Hash:     {hashed}")

    print("\n=== OPTION 1: Run this SQL in Supabase ===")
    print(f"""
UPDATE users SET
  hashed_password  = '{hashed}',
  role             = 'superuser',
  is_platform_user = true,
  is_superuser     = true,
  tenant_id        = NULL,
  is_active        = true
WHERE email = '{SUPERUSER_EMAIL}';
""")

    print("=== OPTION 2: Direct DB update ===")
    try:
        db = SessionLocal()
        user = db.query(User).filter(User.email == SUPERUSER_EMAIL).first()
        if not user:
            print(f"❌ User {SUPERUSER_EMAIL} not found in database.")
            return

        user.hashed_password = hashed
        user.role = "superuser"
        user.is_platform_user = True
        user.is_superuser = True
        user.tenant_id = None
        user.is_active = True
        db.commit()

        print(f"✅ Password reset successfully for {SUPERUSER_EMAIL}")
        print(f"✅ Login with: {NEW_PASSWORD}")
    except Exception as e:
        print(f"❌ DB update failed: {e}")
        print("   Use the SQL option above instead.")
    finally:
        db.close()


if __name__ == "__main__":
    reset_superuser()
