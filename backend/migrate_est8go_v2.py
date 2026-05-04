"""
EST8GO DATABASE MIGRATION — v2.0
================================
Adds:
  1. Tenants     — channel identifiers + areas_covered
  2. tenant_channels — multiple numbers per company (new table)
  3. Conversations   — bot control, buyer role, lead score, funnel stage
  4. Listings        — GPS expiry, document score
  5. Users           — clean role enforcement

Run from your backend folder:
  python migrate_est8go_v2.py

Safe to run multiple times — checks before adding.
"""

from sqlalchemy import text
from app.database.db import engine


def column_exists(conn, table: str, column: str) -> bool:
    result = conn.execute(
        text("""
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = :table
        AND column_name = :column
    """),
        {"table": table, "column": column},
    )
    return result.scalar() > 0


def table_exists(conn, table: str) -> bool:
    result = conn.execute(
        text("""
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name = :table
    """),
        {"table": table},
    )
    return result.scalar() > 0


def add_column_if_missing(conn, table: str, column: str, definition: str):
    if not column_exists(conn, table, column):
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
        print(f"  ✅ Added: {table}.{column}")
    else:
        print(f"  ⏭️  Exists: {table}.{column}")


def run_migration():
    print("\n🚀 EST8GO MIGRATION v2.0 STARTING...\n")

    with engine.begin() as conn:

        # ================================================================
        # 1. TENANTS — Channel Identifiers & Areas
        # ================================================================
        print("📋 [1/5] Upgrading tenants table...")

        add_column_if_missing(conn, "tenants", "areas_covered", "TEXT DEFAULT 'Abuja'")
        add_column_if_missing(conn, "tenants", "business_name", "TEXT")
        add_column_if_missing(
            conn, "tenants", "whatsapp_phone_number_id", "VARCHAR(100) UNIQUE"
        )
        add_column_if_missing(
            conn, "tenants", "facebook_page_id", "VARCHAR(100) UNIQUE"
        )
        add_column_if_missing(
            conn, "tenants", "instagram_account_id", "VARCHAR(100) UNIQUE"
        )
        add_column_if_missing(conn, "tenants", "is_active", "BOOLEAN DEFAULT TRUE")
        add_column_if_missing(conn, "tenants", "created_at", "TIMESTAMP DEFAULT NOW()")

        # ================================================================
        # 2. TENANT CHANNELS — Multiple Numbers Per Company
        # ================================================================
        print("\n📋 [2/5] Creating tenant_channels table...")

        if not table_exists(conn, "tenant_channels"):
            conn.execute(text("""
                CREATE TABLE tenant_channels (
                    id          SERIAL PRIMARY KEY,
                    tenant_id   INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    platform    VARCHAR(20) NOT NULL,
                    platform_id VARCHAR(100) NOT NULL UNIQUE,
                    label       VARCHAR(100),
                    is_active   BOOLEAN DEFAULT TRUE,
                    created_at  TIMESTAMP DEFAULT NOW(),
                    updated_at  TIMESTAMP DEFAULT NOW(),
                    CONSTRAINT valid_platform CHECK (
                        platform IN ('whatsapp', 'instagram', 'facebook')
                    )
                )
            """))
            conn.execute(text("""
                CREATE INDEX idx_tenant_channels_platform_id
                ON tenant_channels(platform_id)
                WHERE is_active = TRUE
            """))
            print("  ✅ Created: tenant_channels table")
            print("  ✅ Created: index on platform_id")
        else:
            print("  ⏭️  Exists: tenant_channels table")

        # ================================================================
        # 3. CONVERSATIONS — Bot Control, Roles, Funnel Tracking
        # ================================================================
        print("\n📋 [3/5] Upgrading conversations table...")

        add_column_if_missing(
            conn, "conversations", "is_bot_active", "BOOLEAN DEFAULT TRUE"
        )
        add_column_if_missing(
            conn, "conversations", "buyer_role", "VARCHAR(20) DEFAULT 'buyer'"
        )
        add_column_if_missing(conn, "conversations", "lead_score", "INTEGER DEFAULT 0")
        add_column_if_missing(
            conn, "conversations", "funnel_stage", "VARCHAR(30) DEFAULT 'awareness'"
        )
        add_column_if_missing(
            conn, "conversations", "last_active_at", "TIMESTAMP DEFAULT NOW()"
        )
        add_column_if_missing(
            conn, "conversations", "session_count", "INTEGER DEFAULT 1"
        )
        add_column_if_missing(conn, "conversations", "assigned_realtor_id", "INTEGER")

        # Add constraint for valid buyer roles
        try:
            conn.execute(text("""
                ALTER TABLE conversations
                ADD CONSTRAINT valid_buyer_role
                CHECK (buyer_role IN ('buyer', 'investor', 'developer', 'unknown'))
            """))
            print("  ✅ Added: buyer_role constraint")
        except Exception:
            print("  ⏭️  Exists: buyer_role constraint")

        # Add constraint for valid funnel stages
        try:
            conn.execute(text("""
                ALTER TABLE conversations
                ADD CONSTRAINT valid_funnel_stage
                CHECK (funnel_stage IN (
                    'awareness', 'verification', 'commitment', 'handshake', 'closed'
                ))
            """))
            print("  ✅ Added: funnel_stage constraint")
        except Exception:
            print("  ⏭️  Exists: funnel_stage constraint")

        # ================================================================
        # 4. LISTINGS — GPS Expiry & Document Score
        # ================================================================
        print("\n📋 [4/5] Upgrading listings table...")

        add_column_if_missing(conn, "listings", "gps_verified_at", "TIMESTAMP")
        add_column_if_missing(conn, "listings", "gps_expires_at", "TIMESTAMP")
        add_column_if_missing(conn, "listings", "document_score", "INTEGER DEFAULT 0")
        add_column_if_missing(conn, "listings", "cof_uploaded", "BOOLEAN DEFAULT FALSE")
        add_column_if_missing(
            conn, "listings", "deed_uploaded", "BOOLEAN DEFAULT FALSE"
        )
        add_column_if_missing(
            conn, "listings", "survey_uploaded", "BOOLEAN DEFAULT FALSE"
        )
        add_column_if_missing(conn, "listings", "witness_count", "INTEGER DEFAULT 0")
        add_column_if_missing(
            conn, "listings", "trust_grade", "VARCHAR(20) DEFAULT 'ungraded'"
        )

        # Auto-set gps_expires_at = gps_verified_at + 60 days for existing rows
        conn.execute(text("""
            UPDATE listings
            SET gps_expires_at = verified_at + INTERVAL '60 days'
            WHERE verified_at IS NOT NULL
            AND gps_expires_at IS NULL
        """))
        print("  ✅ Backfilled: gps_expires_at for existing verified listings")

        # ================================================================
        # 5. USERS — Clean Role Column
        # ================================================================
        print("\n📋 [5/5] Upgrading users table...")

        add_column_if_missing(conn, "users", "user_role", "VARCHAR(30) DEFAULT 'buyer'")
        add_column_if_missing(conn, "users", "tenant_id", "INTEGER")

        # Add constraint for valid user roles
        try:
            conn.execute(text("""
                ALTER TABLE users
                ADD CONSTRAINT valid_user_role
                CHECK (user_role IN (
                    'super_admin', 'tenant_admin', 'realtor', 'buyer', 'investor'
                ))
            """))
            print("  ✅ Added: user_role constraint")
        except Exception:
            print("  ⏭️  Exists: user_role constraint")

        # ================================================================
        # FINAL VERIFICATION
        # ================================================================
        print("\n🔍 VERIFYING MIGRATION...")

        checks = [
            ("tenants", "whatsapp_phone_number_id"),
            ("tenants", "areas_covered"),
            ("conversations", "is_bot_active"),
            ("conversations", "funnel_stage"),
            ("conversations", "lead_score"),
            ("listings", "gps_expires_at"),
            ("listings", "trust_grade"),
            ("listings", "document_score"),
            ("users", "user_role"),
        ]

        all_good = True
        for table, col in checks:
            exists = column_exists(conn, table, col)
            status = "✅" if exists else "❌"
            print(f"  {status} {table}.{col}")
            if not exists:
                all_good = False

        tenant_channels_ok = table_exists(conn, "tenant_channels")
        status = "✅" if tenant_channels_ok else "❌"
        print(f"  {status} tenant_channels table")
        if not tenant_channels_ok:
            all_good = False

    print("\n" + ("=" * 50))
    if all_good:
        print("🎉 MIGRATION COMPLETE — All changes verified.")
    else:
        print("⚠️  MIGRATION INCOMPLETE — Check errors above.")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    run_migration()
