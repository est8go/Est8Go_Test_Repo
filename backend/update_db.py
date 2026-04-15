from sqlalchemy import text
from app.database.db import SessionLocal


def update_tables():
    db = SessionLocal()
    print("Checking Supabase columns...")

    # These are the new 'Trust Layer' commands for Supabase
    commands = [
        "ALTER TABLE listings ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'unverified';",
        "ALTER TABLE listings ADD COLUMN IF NOT EXISTS source VARCHAR(20) DEFAULT 'internal';",
        "ALTER TABLE listings ADD COLUMN IF NOT EXISTS verification_notes TEXT;",
        "ALTER TABLE listings ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;",
        "ALTER TABLE listings ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP;",
        "ALTER TABLE listings ADD COLUMN IF NOT EXISTS verified_by_id INTEGER;",
    ]

    commands = [
        # ... keep your existing commands ...
        """
        CREATE TABLE IF NOT EXISTS listing_images (
            id SERIAL PRIMARY KEY,
            listing_id INTEGER REFERENCES listings(id) ON DELETE CASCADE,
            url VARCHAR(500) NOT NULL,
            is_main BOOLEAN DEFAULT FALSE
        );
        """
    ]

    try:
        for cmd in commands:
            db.execute(text(cmd))
            print(f"✅ Executed: {cmd[:30]}...")
        db.commit()
        print("\n🚀 Supabase is now synced with the Trust Layer!")
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    update_tables()
