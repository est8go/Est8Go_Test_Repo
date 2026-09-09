"""
005 — create listing_reports

Buyer fraud reports filed through the platform-care WhatsApp flow
(platform_care.py, option 5) previously went nowhere reachable. The
handler set convo.data_json["report_detail"] and returned; nothing in the
codebase read that key, GET /admin/conversations/{id} does not return
data_json, and no ConversationMessage rows are ever written, so the only
route to a report was direct SQL against Supabase.

The reference shown to the reporter ("EST-482913") was generated with
random.randint, displayed, and discarded. The confirmation asked them to
quote it. There was nothing to quote it against.

This table is deliberately NOT platform_issues. That table belongs to the
health monitor: severity-filtered, dominated by automated check output,
and listed newest-first with no affected_area filter, so a 'low' row
sinks under health noise. Fraud reports need their own surface.

reference is random rather than derived from id — a sequential reference
would tell every reporter the platform's total report volume. UNIQUE
enforces it; the writer retries on collision.

Idempotent — safe to run repeatedly:
  - CREATE TABLE IF NOT EXISTS
  - CREATE INDEX IF NOT EXISTS
  - ENABLE ROW LEVEL SECURITY is a no-op when already enabled
  - ON CONFLICT DO NOTHING on the self-record

Run from the backend folder:
    PYTHONPATH=. python migrations/005_listing_reports.py
"""

from app.models_registry import register_all_models

register_all_models()

from app.database.db import get_db
from sqlalchemy import text

MIGRATION_NAME = "005_listing_reports"

db = next(get_db())

db.execute(text("""
    CREATE TABLE IF NOT EXISTS listing_reports (
        id                SERIAL PRIMARY KEY,
        reference         VARCHAR(16) NOT NULL UNIQUE,
        reporter_phone    VARCHAR(32),
        reporter_name     VARCHAR(255),
        detail            TEXT NOT NULL,
        listing_reference TEXT,
        tenant_id         INTEGER,
        status            VARCHAR(20) NOT NULL DEFAULT 'new',
        created_at        TIMESTAMP NOT NULL DEFAULT now(),
        updated_at        TIMESTAMP NOT NULL DEFAULT now()
    )
"""))

db.execute(text(
    "CREATE INDEX IF NOT EXISTS ix_listing_reports_status "
    "ON listing_reports (status)"
))
db.execute(text(
    "CREATE INDEX IF NOT EXISTS ix_listing_reports_created_at "
    "ON listing_reports (created_at)"
))
db.execute(text(
    "CREATE INDEX IF NOT EXISTS ix_listing_reports_reference "
    "ON listing_reports (reference)"
))

# New table → lock it down per migrations/README.md. With no policies
# attached this denies Supabase's anon / authenticated roles while leaving
# the backend's own connection (the table owner) unaffected. Reports carry
# a reporter's phone number and their unredacted account of a dispute;
# neither belongs to any client key.
db.execute(text("ALTER TABLE listing_reports ENABLE ROW LEVEL SECURITY"))

_count = db.execute(text("SELECT COUNT(*) FROM listing_reports")).scalar()
print(f"  listing_reports rows: {_count}")

db.execute(
    text(
        "INSERT INTO applied_migrations (name) VALUES (:name) "
        "ON CONFLICT (name) DO NOTHING"
    ),
    {"name": MIGRATION_NAME},
)
db.commit()

print(f"applied {MIGRATION_NAME}")
print("  (a re-run reports the existing row count — idempotent)")
