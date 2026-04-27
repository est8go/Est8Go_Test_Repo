import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# Get your database URL from .env
DATABASE_URL = os.getenv("DATABASE_URL")


def cleanup():
    # We use a raw engine to avoid SQLAlchemy Model relationship errors
    engine = create_engine(DATABASE_URL)

    print("🧹 STARTING RAW SQL CLEANUP...")

    with engine.connect() as connection:
        # Start a transaction
        trans = connection.begin()
        try:
            # 1. Delete Listings
            connection.execute(text("DELETE FROM listings WHERE id IN (991, 992)"))

            # 2. Delete Tenants
            connection.execute(text("DELETE FROM tenants WHERE id IN (101, 102)"))

            # 3. Delete Conversations
            connection.execute(
                text("DELETE FROM conversations WHERE tenant_id IN (101, 102)")
            )

            trans.commit()
            print("✅ Test data surgically removed. Database is clean.")
        except Exception as e:
            trans.rollback()
            print(f"❌ Cleanup failed: {e}")


if __name__ == "__main__":
    cleanup()
