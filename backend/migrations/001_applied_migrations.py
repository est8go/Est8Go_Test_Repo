"""
001 — applied_migrations ledger

Run from the backend folder:
    PYTHONPATH=. python migrations/001_applied_migrations.py

Creates the table that records which numbered migrations have run, then
records itself. Every later script in this folder ends by inserting its own
filename here, so `SELECT name FROM applied_migrations ORDER BY name` is the
answer to "what has been applied to this database?".

Also enables Row Level Security on the new table, matching the posture of
platform_issues. There are deliberately NO policies: RLS with zero policies
denies every non-owner role (Supabase anon / authenticated / PostgREST),
while the table owner — which is the role this backend connects as via
DATABASE_URL — still reads and writes normally. This ledger is backend-only
infrastructure and must never be reachable from a client key.

Idempotent — safe to run repeatedly:
  - CREATE TABLE IF NOT EXISTS
  - ENABLE ROW LEVEL SECURITY is a no-op once already enabled
  - ON CONFLICT DO NOTHING on the self-record

Non-destructive: creates one new table. Nothing existing is read or modified.

NOTE: the legacy backend/migrate_*.py scripts and the three unnumbered
scripts in this folder are NOT backfilled here. They are already applied and
idempotent; see README.md.
"""

from app.models_registry import register_all_models

register_all_models()

from app.database.db import get_db
from sqlalchemy import text

MIGRATION_NAME = "001_applied_migrations"

db = next(get_db())

db.execute(
    text(
        """
        CREATE TABLE IF NOT EXISTS applied_migrations (
            name       TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
)

# Deny-by-default for every non-owner role. No policies, by design.
db.execute(text("ALTER TABLE applied_migrations ENABLE ROW LEVEL SECURITY"))

db.execute(
    text(
        """
        INSERT INTO applied_migrations (name)
        VALUES (:name)
        ON CONFLICT (name) DO NOTHING
        """
    ),
    {"name": MIGRATION_NAME},
)

db.commit()
print(f"applied_migrations table ready (RLS enabled); recorded {MIGRATION_NAME}")
