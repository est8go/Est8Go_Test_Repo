"""
Migration: add tenants.logo_url + tenants.brand_color (Workstream C1)

Run from the backend folder:
    PYTHONPATH=. python migrations/add_tenant_branding.py

Idempotent — safe to run multiple times:
  - ADD COLUMN IF NOT EXISTS
Non-destructive: only adds two NULLABLE columns. No existing row is read
or modified; tenants without a logo/colour keep falling back to the
default Est8Go-neutral styling.
"""

from app.models_registry import register_all_models
register_all_models()
from app.database.db import get_db
from sqlalchemy import text

db = next(get_db())

# Agency co-branding fields on tenants.
#   logo_url    — public URL of the agency logo (non-sensitive, public bucket)
#   brand_color — validated hex like #4F46E5 (7 chars incl. the leading '#')
db.execute(text('''
    ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS logo_url VARCHAR(500)
'''))
db.execute(text('''
    ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS brand_color VARCHAR(7)
'''))

db.commit()
print("tenants.logo_url + tenants.brand_color added")
