from app.models_registry import register_all_models
register_all_models()

from app.database.db import engine, SessionLocal
from sqlalchemy import text

def run(conn, label, sql):
    try:
        conn.execute(text("SAVEPOINT sp_" + label))
        conn.execute(text(sql))
        conn.execute(text("RELEASE SAVEPOINT sp_" + label))
        print("[OK] " + label)
    except Exception as e:
        conn.execute(text("ROLLBACK TO SAVEPOINT sp_" + label))
        print("[SKIP] " + label + ": " + str(e).split("\n")[0])

with engine.connect() as conn:
    run(conn, "role_expires_at",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS role_expires_at TIMESTAMP NULL")

    run(conn, "previous_role",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS previous_role VARCHAR(50) NULL")

    run(conn, "password_reset_tokens",
        "CREATE TABLE IF NOT EXISTS password_reset_tokens ("
        "id SERIAL PRIMARY KEY,"
        "user_id INTEGER NOT NULL REFERENCES users(id),"
        "token VARCHAR(128) UNIQUE NOT NULL,"
        "expires_at TIMESTAMP NOT NULL,"
        "used_at TIMESTAMP NULL,"
        "created_at TIMESTAMP DEFAULT NOW()"
        ")")

    run(conn, "role_change_requests",
        "CREATE TABLE IF NOT EXISTS role_change_requests ("
        "id SERIAL PRIMARY KEY,"
        "requester_id INTEGER NOT NULL REFERENCES users(id),"
        "\"current_role\" VARCHAR(50) NOT NULL,"
        "requested_role VARCHAR(50) NOT NULL,"
        "reason TEXT,"
        "status VARCHAR(20) DEFAULT 'pending',"
        "approved_by INTEGER REFERENCES users(id),"
        "expiry_hours INTEGER DEFAULT 24,"
        "activated_at TIMESTAMP NULL,"
        "expires_at TIMESTAMP NULL,"
        "actioned_at TIMESTAMP NULL,"
        "created_at TIMESTAMP DEFAULT NOW()"
        ")")

    run(conn, "tenant_signup_links",
        "CREATE TABLE IF NOT EXISTS tenant_signup_links ("
        "id SERIAL PRIMARY KEY,"
        "code VARCHAR(64) UNIQUE NOT NULL,"
        "plan VARCHAR(50) DEFAULT 'Starter',"
        "created_by INTEGER NOT NULL REFERENCES users(id),"
        "invited_email VARCHAR(255) NULL,"
        "max_uses INTEGER DEFAULT 1,"
        "uses_count INTEGER DEFAULT 0,"
        "expires_at TIMESTAMP NOT NULL,"
        "used_at TIMESTAMP NULL,"
        "created_at TIMESTAMP DEFAULT NOW(),"
        "is_active BOOLEAN DEFAULT TRUE"
        ")")

    run(conn, "referral_codes",
        "CREATE TABLE IF NOT EXISTS referral_codes ("
        "id SERIAL PRIMARY KEY,"
        "code VARCHAR(32) UNIQUE NOT NULL,"
        "tenant_id INTEGER NOT NULL REFERENCES tenants(id),"
        "commission_rate INTEGER DEFAULT 5,"
        "uses_count INTEGER DEFAULT 0,"
        "max_uses INTEGER NULL,"
        "expires_at TIMESTAMP NULL,"
        "created_at TIMESTAMP DEFAULT NOW(),"
        "is_active BOOLEAN DEFAULT TRUE"
        ")")

    run(conn, "referral_conversions",
        "CREATE TABLE IF NOT EXISTS referral_conversions ("
        "id SERIAL PRIMARY KEY,"
        "referral_code_id INTEGER REFERENCES referral_codes(id),"
        "referred_tenant_id INTEGER REFERENCES tenants(id),"
        "conversion_value INTEGER DEFAULT 0,"
        "commission_earned INTEGER DEFAULT 0,"
        "paid_at TIMESTAMP NULL,"
        "created_at TIMESTAMP DEFAULT NOW()"
        ")")

    conn.commit()
    print("\nMigration complete")
