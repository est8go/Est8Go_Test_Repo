from sqlalchemy import text
from app.database.db import SessionLocal


def sync():
    db = SessionLocal()
    print("🚀 Starting Direct SQL Sync to Supabase...")

    # We build the tables in order: Tenants -> Users -> Listings -> Images
    sql_commands = [
        # 1. Create Tenants
        """
        CREATE TABLE IF NOT EXISTS tenants (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL
        );
        """,
        # 2. Create Users
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER REFERENCES tenants(id),
            email VARCHAR(255) UNIQUE NOT NULL,
            hashed_password VARCHAR(255),
            is_active BOOLEAN DEFAULT TRUE,
            is_admin BOOLEAN DEFAULT FALSE,
            is_superuser BOOLEAN DEFAULT FALSE
        );
        """,
        # 3. Create Listings
        """
        CREATE TABLE IF NOT EXISTS listings (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER REFERENCES tenants(id),
            title VARCHAR(255),
            description TEXT,
            location VARCHAR(255),
            price BIGINT,
            property_type VARCHAR(50),
            status VARCHAR(50) DEFAULT 'unverified',
            source VARCHAR(20) DEFAULT 'internal',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            verified_at TIMESTAMP,
            verified_by_id INTEGER REFERENCES users(id),
            verification_notes TEXT
        );
        """,
        # 4. Create Listing Images
        """
        CREATE TABLE IF NOT EXISTS listing_images (
            id SERIAL PRIMARY KEY,
            listing_id INTEGER REFERENCES listings(id) ON DELETE CASCADE,
            url VARCHAR(500) NOT NULL,
            is_main BOOLEAN DEFAULT FALSE
        );
        """,
    ]

    try:
        for cmd in sql_commands:
            db.execute(text(cmd))
            db.commit()
            print("✅ Step complete.")

        print("\n🎉 SUPABASE IS FULLY BUILT AND SYNCED!")
    except Exception as e:
        print(f"❌ Error during SQL execution: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    sync()
