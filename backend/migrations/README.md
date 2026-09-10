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

    PYTHONPATH=. python migrations/00N_name.py --dry-run   # validate, rolls back
    PYTHONPATH=. python migrations/00N_name.py             # apply

## ⚠️ `register_all_models()` autocommits — import it only when needed

`register_all_models()` calls `Base.metadata.create_all()`. That runs on its
**own connection and autocommits**, before any transaction your script opens.

For a plain `ALTER` that is harmless. For a migration that **creates a table**
it is a trap, in two ways:

1. **`create_all` wins the race.** It creates the table first, from the
   SQLAlchemy model. Your `CREATE TABLE IF NOT EXISTS` then becomes a no-op,
   so the table you get is the *model's* definition, not your SQL's. Anything
   that exists only in your SQL — most importantly
   `ENABLE ROW LEVEL SECURITY`, which has no SQLAlchemy equivalent — is
   silently skipped.

2. **A `--dry-run` cannot undo it.** Wrapping everything in a transaction and
   rolling back at the end does *not* roll back `create_all`, because that
   already committed on a different connection. The rollback leaves the new
   table behind **without RLS**, while correctly reverting every statement
   that was actually inside your transaction — so the run reports success and
   the schema is left half-hardened.

This is not hypothetical: the first `--dry-run` of `006_followup_tasks` did
exactly this, leaving `followup_tasks` and `followup_digest_log` in production
with `RLS = False`. `005_listing_reports` has the same shape and escaped only
because it was never dry-run.

**So: import the registry inside a `if not DRY_RUN:` guard** (see
`006_followup_tasks.py`), and keep `ENABLE ROW LEVEL SECURITY` in the
migration where it belongs. A migration that only `ALTER`s existing tables can
skip the registry entirely.

Related ordering rule: **apply a table-creating migration BEFORE the deploy
that ships its model.** Render boots `register_all_models()`, so a deploy that
lands first will create the table un-hardened.

## Template

    """
    00N — what this changes
    """
    import sys

    MIGRATION_NAME = "00N_what_this_changes"

    DRY_RUN = "--dry-run" in sys.argv

    # See the warning above. create_all() autocommits on its own connection,
    # so under --dry-run it would create tables the closing rollback cannot
    # undo — leaving them without the RLS this script applies. It is only
    # needed so create_all can resolve models on a real apply; a migration
    # that just ALTERs existing tables does not need it at all.
    if not DRY_RUN:
        from app.models_registry import register_all_models

        register_all_models()

    from app.database.db import get_db
    from sqlalchemy import text

    db = next(get_db())

    db.execute(text("ALTER TABLE foo ADD COLUMN IF NOT EXISTS bar TEXT"))

    # If this migration CREATEs a table, lock it down:
    # db.execute(text("ALTER TABLE new_table ENABLE ROW LEVEL SECURITY"))

    if DRY_RUN:
        db.rollback()
        print(f"ROLLED BACK — {MIGRATION_NAME} NOT recorded")
        sys.exit(0)

    db.execute(
        text(
            "INSERT INTO applied_migrations (name) VALUES (:name) "
            "ON CONFLICT (name) DO NOTHING"
        ),
        {"name": MIGRATION_NAME},
    )
    db.commit()
    print(f"applied {MIGRATION_NAME}")

A `--dry-run` executes every statement against the real database inside a
transaction and then rolls back. Postgres DDL is transactional, so this
genuinely validates the SQL — FK targets resolve, syntax is accepted,
constraints hold — without persisting anything, *provided* the registry guard
above is in place.

## Checking state

    SELECT name, applied_at FROM applied_migrations ORDER BY name;

## Legacy scripts — do not touch

The `backend/migrate_*.py` scripts and the three unnumbered scripts already in
this folder (`add_listing_documents.py`, `add_tenant_branding.py`,
`add_tenant_channel_credentials.py`) predate this convention. They are all
applied to production and all idempotent. They are deliberately **not**
backfilled into `applied_migrations` and **not** renamed — the ledger starts
at `001` and covers new work only. Do not add anything new to `backend/`.
