"""
002 — clean junk values out of tenants.whatsapp_phone_number_id

whatsapp_phone_number_id is unique=True AND the webhook routing key:
resolve_tenant_from_webhook matches an incoming payload's
metadata.phone_number_id against it. Four tenants hold local Nigerian
phone numbers there instead of Meta ids, so those rows can never match a
webhook and each one occupies a unique slot that a real Meta id could
otherwise claim.

Format validation now rejects this at both the admin create/edit paths
and self-service onboarding (see app/core/validators.py), so this is a
one-off cleanup of what got in before the guard existed.

Four separate decisions, not one blanket rule:

  t3 Mshel Homes      NULL the id, move NOTHING.
                      Its value (08032207948) is Bravieshomz's own
                      WhatsApp number — a copy-paste during setup, not
                      Mshel's number. Moving it would write tenant 1's
                      number onto tenant 3's record and make the mistake
                      look deliberate.

  t4 Lasdslot         Move id -> whatsapp_phone_number, NULL the id.
  t6 Favour properties  Both have 0 listings and no slug, so they have no
                      public surface: nothing a visitor can see changes.

  t5 EstateTrust      NULL BOTH columns.
                      Inactive, no slug, treated as a dead test tenant.
                      It owns listing 31 (verified), so writing a number
                      into whatsapp_phone_number would put a NEW working
                      WhatsApp button on a public page. Leave that button
                      on the WHATSAPP_BUSINESS_NUMBER env fallback.
                      (The is_active gate shipped alongside this makes
                      that page 404 anyway — this migration does not
                      depend on that, and stands on its own.)

Idempotent: every statement matches on both the tenant id AND the exact
junk value, so a second run is a no-op, and none of them can overwrite a
value someone has since corrected by hand.
"""
from app.models_registry import register_all_models
register_all_models()

from app.database.db import get_db
from sqlalchemy import text

MIGRATION_NAME = "002_clean_whatsapp_phone_number_id"

db = next(get_db())

# --- t3: clear only. The value belongs to tenant 1. ---
_r3 = db.execute(
    text(
        "UPDATE tenants SET whatsapp_phone_number_id = NULL "
        "WHERE id = 3 AND whatsapp_phone_number_id = '08032207948'"
    )
)

# --- t4, t6: move the number to the column that wants a phone number. ---
# `whatsapp_phone_number IS NULL` keeps this from clobbering a real value
# if one is set later and the migration is re-run.
_r4 = db.execute(
    text(
        "UPDATE tenants "
        "SET whatsapp_phone_number = whatsapp_phone_number_id, "
        "    whatsapp_phone_number_id = NULL "
        "WHERE id = 4 AND whatsapp_phone_number_id = '08100022233' "
        "  AND whatsapp_phone_number IS NULL"
    )
)
_r6 = db.execute(
    text(
        "UPDATE tenants "
        "SET whatsapp_phone_number = whatsapp_phone_number_id, "
        "    whatsapp_phone_number_id = NULL "
        "WHERE id = 6 AND whatsapp_phone_number_id = '080236509874' "
        "  AND whatsapp_phone_number IS NULL"
    )
)

# --- t5: clear both. Dead test tenant — introduce no new public value. ---
_r5 = db.execute(
    text(
        "UPDATE tenants "
        "SET whatsapp_phone_number = NULL, whatsapp_phone_number_id = NULL "
        "WHERE id = 5 AND whatsapp_phone_number_id = '08065432167'"
    )
)

db.execute(
    text(
        "INSERT INTO applied_migrations (name) VALUES (:name) "
        "ON CONFLICT (name) DO NOTHING"
    ),
    {"name": MIGRATION_NAME},
)
db.commit()

print(f"applied {MIGRATION_NAME}")
print(f"  t3 cleared        : {_r3.rowcount} row(s)")
print(f"  t4 moved          : {_r4.rowcount} row(s)")
print(f"  t6 moved          : {_r6.rowcount} row(s)")
print(f"  t5 cleared both   : {_r5.rowcount} row(s)")
print("  (0 rows on a re-run is expected — this migration is idempotent)")

for _row in db.execute(
    text(
        "SELECT id, whatsapp_phone_number, whatsapp_phone_number_id "
        "FROM tenants WHERE id IN (3,4,5,6) ORDER BY id"
    )
):
    print(f"  t{_row[0]}: number={_row[1]!r} id={_row[2]!r}")
