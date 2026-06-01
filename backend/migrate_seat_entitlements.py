"""
Migration: Create seat_entitlements table
Run once: python migrate_seat_entitlements.py
"""
import os
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

SQL = """
CREATE TABLE IF NOT EXISTS seat_entitlements (
    id                 SERIAL PRIMARY KEY,
    tenant_id          INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id            INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status             VARCHAR(20) NOT NULL DEFAULT 'active',
    credits_per_month  INTEGER NOT NULL DEFAULT 800,
    grace_until        TIMESTAMP,
    last_renewed_at    TIMESTAMP,
    last_month_year    VARCHAR(7),
    created_at         TIMESTAMP DEFAULT NOW(),
    updated_at         TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_seat_tenant_user UNIQUE (tenant_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_seat_tenant ON seat_entitlements(tenant_id);
CREATE INDEX IF NOT EXISTS idx_seat_status ON seat_entitlements(status);
"""

with engine.connect() as conn:
    conn.execute(text(SQL))
    conn.commit()
    print("OK: seat_entitlements table created successfully.")
