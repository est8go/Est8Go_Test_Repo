"""
004 — drop listings.gps_photo_match

The column was added by the legacy backend/migrate_gps.py as part of a
graduated GPS score: 15 for coordinates captured, +10 for a location
match, +5 for photos geotagged on site. That last 5 was never reachable.

No capture flow ever set it. The only writer in the repo was
fix_listing.py, a one-off script that hardcoded listing #3 to a
fabricated Emerald 88 with every flag true; it has been deleted. Nine
rows carry TRUE from that script and from the demo seed.

003 collapsed the three divergent scorers into
trust_engine.calculate_confidence_score, where GPS is a flat 30. The
column therefore has no consumer and cannot acquire one, and dropping it
changes no trust_score — the value contributed nothing to the score even
where it was TRUE.

Idempotent — safe to run repeatedly:
  - DROP COLUMN IF EXISTS guards the destructive step
  - ON CONFLICT DO NOTHING on the self-record

DESTRUCTIVE: drops a column. Run only once the code that stops
referencing it is deployed.

NOTE: legacy backend/migrate_gps.py still lists gps_photo_match in its
ADD COLUMN block. It is left untouched as history per README.md, which
means running it against a fresh database would recreate this column;
run 004 after it if that ever happens.

Run from the backend folder:
    PYTHONPATH=. python migrations/004_drop_gps_photo_match.py
"""

from app.models_registry import register_all_models

register_all_models()

from app.database.db import get_db
from sqlalchemy import text

MIGRATION_NAME = "004_drop_gps_photo_match"

db = next(get_db())

_present = db.execute(
    text(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_name = 'listings' AND column_name = 'gps_photo_match'"
    )
).scalar()

if _present:
    _truthy = db.execute(
        text("SELECT COUNT(*) FROM listings WHERE gps_photo_match IS TRUE")
    ).scalar()
    print(f"  rows with gps_photo_match TRUE : {_truthy} (contributed 0 points)")
    db.execute(text("ALTER TABLE listings DROP COLUMN IF EXISTS gps_photo_match"))
    print("  column dropped")
else:
    print("  column already absent — nothing to drop")

db.execute(
    text(
        "INSERT INTO applied_migrations (name) VALUES (:name) "
        "ON CONFLICT (name) DO NOTHING"
    ),
    {"name": MIGRATION_NAME},
)
db.commit()

print(f"applied {MIGRATION_NAME}")
print("  (a re-run reports the column already absent — idempotent)")
