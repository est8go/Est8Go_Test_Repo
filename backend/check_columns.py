from sqlalchemy import text
from app.database.db import SessionLocal


def fix():
    db = SessionLocal()
    print("Checking for missing columns...")
    try:
        # We force-add every column the Listing model expects
        commands = [
            "ALTER TABLE listings ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'unverified';",
            "ALTER TABLE listings ADD COLUMN IF NOT EXISTS source VARCHAR(20) DEFAULT 'internal';",
            "ALTER TABLE listings ADD COLUMN IF NOT EXISTS description TEXT;",
            "ALTER TABLE listings ADD COLUMN IF NOT EXISTS location VARCHAR(255);",
            "ALTER TABLE listings ADD COLUMN IF NOT EXISTS price BIGINT;",
            "ALTER TABLE listings ADD COLUMN IF NOT EXISTS property_type VARCHAR(50);",
            "ALTER TABLE listings ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;",
        ]
        for cmd in commands:
            db.execute(text(cmd))
        db.commit()
        print("✅ Columns verified and fixed!")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    fix()
