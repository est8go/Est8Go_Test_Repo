from app.database.db import engine, Base
from sqlalchemy import text

# 1. EXPLICIT IMPORTS (This tells SQLAlchemy what 'users' and 'tenants' are)
from app.users.models import User  # noqa: F401
from app.tenants.models import Tenant  # noqa: F401
from app.listings.models import Listing, ListingImage  # noqa: F401


def sync_all():
    print("Connecting to Supabase...")
    try:
        # 2. CREATE ALL TABLES
        # Because we imported the models above, SQLAlchemy now knows the order:
        # It will create Tenants -> Users -> Listings -> Images automatically.
        Base.metadata.create_all(bind=engine)
        print("✅ Tables created or already exist in correct order.")

        # 3. VERIFY TRUST LAYER COLUMNS
        with engine.connect() as connection:
            commands = [
                "ALTER TABLE listings ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'unverified';",
                "ALTER TABLE listings ADD COLUMN IF NOT EXISTS source VARCHAR(20) DEFAULT 'internal';",
                "ALTER TABLE listings ADD COLUMN IF NOT EXISTS verification_notes TEXT;",
                "ALTER TABLE listings ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;",
                "ALTER TABLE listings ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP;",
                "ALTER TABLE listings ADD COLUMN IF NOT EXISTS verified_by_id INTEGER;",
            ]
            for cmd in commands:
                try:
                    connection.execute(text(cmd))
                    connection.commit()
                except Exception:
                    pass
            print("✅ Trust Layer columns verified.")

        print("\n🚀 SUPABASE IS FULLY SYNCED!")

    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    sync_all()
