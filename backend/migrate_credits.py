from app.models_registry import register_all_models
register_all_models()
from app.database.db import engine
from sqlalchemy import text

print("Running credit economy migration...")

statements = [
    ("credit_wallets", """
        CREATE TABLE IF NOT EXISTS credit_wallets (
            id                 SERIAL PRIMARY KEY,
            tenant_id          INTEGER UNIQUE NOT NULL REFERENCES tenants(id),
            purchased_balance  INTEGER NOT NULL DEFAULT 0 CHECK (purchased_balance >= 0),
            bonus_balance      INTEGER NOT NULL DEFAULT 0 CHECK (bonus_balance >= 0),
            reserved           INTEGER NOT NULL DEFAULT 0 CHECK (reserved >= 0),
            total_purchased    INTEGER NOT NULL DEFAULT 0,
            total_spent        INTEGER NOT NULL DEFAULT 0,
            total_awarded      INTEGER NOT NULL DEFAULT 0,
            last_activity_at   TIMESTAMP DEFAULT NOW(),
            is_dormant         BOOLEAN DEFAULT FALSE,
            updated_at         TIMESTAMP DEFAULT NOW()
        )
    """),
    ("credit_ledger", """
        CREATE TABLE IF NOT EXISTS credit_ledger (
            id               SERIAL PRIMARY KEY,
            tenant_id        INTEGER NOT NULL REFERENCES tenants(id),
            event_type       TEXT NOT NULL,
            credits_debited  INTEGER NOT NULL DEFAULT 0,
            credits_credited INTEGER NOT NULL DEFAULT 0,
            balance_after    INTEGER NOT NULL,
            credit_type      TEXT DEFAULT 'purchased',
            reference        TEXT,
            action_type      TEXT,
            metadata         JSONB,
            created_by       INTEGER REFERENCES users(id),
            created_at       TIMESTAMP DEFAULT NOW()
        )
    """),
    ("credit_expiry", """
        CREATE TABLE IF NOT EXISTS credit_expiry (
            id              SERIAL PRIMARY KEY,
            tenant_id       INTEGER NOT NULL REFERENCES tenants(id),
            credits         INTEGER NOT NULL,
            credit_type     TEXT NOT NULL,
            expires_at      TIMESTAMP,
            expired         BOOLEAN DEFAULT FALSE,
            warning_sent_14 BOOLEAN DEFAULT FALSE,
            warning_sent_3  BOOLEAN DEFAULT FALSE,
            created_at      TIMESTAMP DEFAULT NOW()
        )
    """),
    ("credit_bundles", """
        CREATE TABLE IF NOT EXISTS credit_bundles (
            id            SERIAL PRIMARY KEY,
            name          TEXT NOT NULL,
            credits       INTEGER NOT NULL,
            bonus_credits INTEGER DEFAULT 0,
            price_ngn     INTEGER NOT NULL,
            is_active     BOOLEAN DEFAULT TRUE,
            display_order INTEGER DEFAULT 0,
            created_at    TIMESTAMP DEFAULT NOW()
        )
    """),
    ("credit_transactions", """
        CREATE TABLE IF NOT EXISTS credit_transactions (
            id            SERIAL PRIMARY KEY,
            tenant_id     INTEGER NOT NULL REFERENCES tenants(id),
            bundle_id     INTEGER REFERENCES credit_bundles(id),
            paystack_ref  TEXT UNIQUE,
            amount_ngn    INTEGER NOT NULL,
            credits       INTEGER NOT NULL,
            bonus_credits INTEGER DEFAULT 0,
            status        TEXT DEFAULT 'pending',
            month_year    TEXT,
            created_at    TIMESTAMP DEFAULT NOW(),
            completed_at  TIMESTAMP
        )
    """),
    ("mmef_tracking", """
        CREATE TABLE IF NOT EXISTS mmef_tracking (
            id            SERIAL PRIMARY KEY,
            tenant_id     INTEGER NOT NULL REFERENCES tenants(id),
            month_year    TEXT NOT NULL,
            tier          TEXT NOT NULL,
            required_ngn  INTEGER NOT NULL,
            purchased_ngn INTEGER DEFAULT 0,
            met           BOOLEAN DEFAULT FALSE,
            grace_until   TIMESTAMP,
            created_at    TIMESTAMP DEFAULT NOW(),
            UNIQUE(tenant_id, month_year)
        )
    """),
]

with engine.connect() as conn:
    for table_name, sql in statements:
        try:
            conn.execute(text(sql))
            print(f"[OK] {table_name}")
        except Exception as e:
            print(f"[SKIP] {table_name}: {str(e).split(chr(10))[0]}")
    conn.commit()

print("\n[OK] Credit migration complete")
