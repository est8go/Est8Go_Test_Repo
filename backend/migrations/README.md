# Migrations

`backend/migrations/` is the single home for all **new** schema changes.

## Convention

Every new migration is one file named `NNN_short_description.py`, where `NNN`
is the next unused three-digit number. Numbers are never reused and never
renumbered — the number is the migration's permanent identity.

Each script must be:

1. **Numbered** — `002_...`, `003_...`, applied in ascending order.
2. **Idempotent** — safe to run twice. Use `ADD COLUMN IF NOT EXISTS`,
   `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`,
   `ON CONFLICT DO NOTHING`. Never `DROP` without an explicit guard.
3. **Self-recording** — the last statement before `db.commit()` inserts the
   script's own name into `applied_migrations`.
4. **RLS-safe** — any script that creates a *new* table must follow it with
   `ALTER TABLE <t> ENABLE ROW LEVEL SECURITY`. With no policies attached
   this denies Supabase's `anon` / `authenticated` roles while leaving the
   backend's own connection (the table owner) unaffected. Add explicit
   policies only if a client key genuinely needs the table.

## Running

From the `backend/` folder:

    PYTHONPATH=. python migrations/001_applied_migrations.py

## Template

    """
    00N — what this changes
    """
    from app.models_registry import register_all_models
    register_all_models()

    from app.database.db import get_db
    from sqlalchemy import text

    MIGRATION_NAME = "00N_what_this_changes"

    db = next(get_db())

    db.execute(text("ALTER TABLE foo ADD COLUMN IF NOT EXISTS bar TEXT"))

    # If this migration CREATEs a table, lock it down:
    # db.execute(text("ALTER TABLE new_table ENABLE ROW LEVEL SECURITY"))

    db.execute(
        text(
            "INSERT INTO applied_migrations (name) VALUES (:name) "
            "ON CONFLICT (name) DO NOTHING"
        ),
        {"name": MIGRATION_NAME},
    )
    db.commit()
    print(f"applied {MIGRATION_NAME}")

## Checking state

    SELECT name, applied_at FROM applied_migrations ORDER BY name;

## Legacy scripts — do not touch

The `backend/migrate_*.py` scripts and the three unnumbered scripts already in
this folder (`add_listing_documents.py`, `add_tenant_branding.py`,
`add_tenant_channel_credentials.py`) predate this convention. They are all
applied to production and all idempotent. They are deliberately **not**
backfilled into `applied_migrations` and **not** renamed — the ledger starts
at `001` and covers new work only. Do not add anything new to `backend/`.
