"""
Migration: add slug column to tenants table and auto-generate slugs.
Run once: python backend/migrate_tenant_slug.py
"""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.models_registry import register_all_models
register_all_models()

from app.database.db import engine, get_db
from sqlalchemy import text

with engine.connect() as conn:
    try:
        conn.execute(text(
            "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS slug VARCHAR(100) NULL"
        ))
        conn.commit()
        print("[OK] Added slug column to tenants")
    except Exception as e:
        print(f"[SKIP] Column may already exist: {e}")

try:
    conn2 = engine.connect()
    conn2.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_tenants_slug ON tenants (slug) WHERE slug IS NOT NULL"
    ))
    conn2.commit()
    conn2.close()
    print("[OK] Created unique index on tenants.slug")
except Exception as e:
    print(f"[SKIP] Index: {e}")

db = next(get_db())
from app.tenants.models import Tenant

tenants = db.query(Tenant).all()
updated = 0
for t in tenants:
    if not t.slug and t.business_name:
        candidate = re.sub(r'[^a-z0-9]+', '-', t.business_name.lower()).strip('-')
        existing = db.query(Tenant).filter(
            Tenant.slug == candidate, Tenant.id != t.id
        ).first()
        if existing:
            candidate = f"{candidate}-{t.id}"
        t.slug = candidate
        print(f"  [OK] {t.business_name!r} → {candidate!r}")
        updated += 1

db.commit()
print(f"\nDone — {updated} tenant(s) updated, {len(tenants) - updated} skipped (already had slug or no business_name).")
