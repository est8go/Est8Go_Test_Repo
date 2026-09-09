"""
003 — remove the witness pillar and recompute every trust score

Trust becomes GPS 30 | AI 20 | Docs 50 = 100, computed by the single
scorer in trust_engine.calculate_confidence_score.

What this fixes
---------------
1. The witness pillar. It was fed by POST /listings/{id}/confirm-visit,
   which was unauthenticated, never tenant-scoped and called by nothing
   in the codebase. Anyone with a listing id could increment it, and the
   raw counter was printed on the public property page as social proof.
   The endpoint is deleted; this drops the column.

2. Three divergent trust formulas. GPS was a flat 30 in trust_engine and
   listings/router, a graduated 15/+10/+5 in document_trust_engine, and a
   fourth variant in the agency dashboard. Documents were truncated in
   two places and rescaled to 40 in the others. Witnesses scored 5 in one
   and 2 in another. The same listing came out 90/emerald and 73/Silver
   depending on which ran, and since the AI audit path writes trust_score
   on photo upload, a listing's grade depended on the agency's last
   action. Everything now delegates to one function.

3. ai_verified_real set with no audit behind it. The real audit writes
   ai_audit_report alongside the flag; the demo seed never did. So
   ai_verified_real = TRUE AND ai_audit_report IS NULL means "flag set,
   audit never ran". (migrate_fix_ai_default.py used a latitude
   heuristic and missed every seeded row.)

4. Document flags with no document behind them. cof_uploaded /
   deed_uploaded / survey_uploaded were set on 23 listings, of which
   exactly ONE had a file in listing_documents. Scoring from those
   booleans awarded up to 72 points for paperwork nobody uploaded, which
   is how listing #4 came to hold document_score 72 off a single C of O
   worth 35. Documents are now scored from listing_documents — the
   model's stated source of truth — and the booleans are reset to match.
   _get_uploaded_doc_keys() was changed to read the same rows.

Idempotent — safe to run repeatedly:
  - every value is recomputed from source columns, so a second run
    writes the same numbers
  - DROP COLUMN IF EXISTS guards the destructive step
  - ON CONFLICT DO NOTHING on the self-record

DESTRUCTIVE: drops listings.witness_count. Run only once the code that
stops reading it is deployed, or every listing query 500s.

NOTE: document scoring imports calculate_document_score, so this
captures the scorer as it stands at 003. A later re-run re-syncs scores
to the then-current scorer, which is the intent for a recompute.

Run from the backend folder:
    PYTHONPATH=. python migrations/003_remove_witness_pillar.py
"""

from app.models_registry import register_all_models

register_all_models()

from app.database.db import get_db
from app.services.document_trust_engine import (
    DOCUMENT_SCORES,
    calculate_document_score,
)
from app.services.trust_engine import grade_for_score
from sqlalchemy import text

MIGRATION_NAME = "003_remove_witness_pillar"

db = next(get_db())


def _doc_score(keys):
    """Document score earned by files that actually exist, 0-100 scale."""
    scorable = [k for k in keys if k in DOCUMENT_SCORES]
    return calculate_document_score(scorable).final_score if scorable else 0


rows = db.execute(
    text(
        """
        SELECT id, latitude, longitude, gps_verified_at,
               ai_verified_real, ai_audit_report,
               cof_uploaded, deed_uploaded, survey_uploaded,
               document_score, trust_score, trust_grade
        FROM listings
        ORDER BY id
        """
    )
).mappings().all()

_ai_cleared = 0
_docs_fixed = 0
_flags_fixed = 0
_scores_changed = 0

for r in rows:
    # 1. A flag with no audit report behind it is not an audit result.
    ai_ok = bool(r["ai_verified_real"]) and bool(r["ai_audit_report"])
    if bool(r["ai_verified_real"]) and not ai_ok:
        _ai_cleared += 1

    # 2. Documents come from the rows, never from the booleans.
    keys = [
        x[0]
        for x in db.execute(
            text(
                "SELECT DISTINCT doc_type FROM listing_documents "
                "WHERE listing_id = :i"
            ),
            {"i": r["id"]},
        ).all()
        if x[0]
    ]
    doc_score = _doc_score(keys)
    if doc_score != (r["document_score"] or 0):
        _docs_fixed += 1

    flags = {
        "cof": "c_of_o" in keys,
        "deed": "deed_of_assignment" in keys,
        "survey": "survey_plan" in keys,
    }
    if (
        bool(r["cof_uploaded"]) != flags["cof"]
        or bool(r["deed_uploaded"]) != flags["deed"]
        or bool(r["survey_uploaded"]) != flags["survey"]
    ):
        _flags_fixed += 1

    # 3. GPS 30 | AI 20 | Docs 50, truncated not rescaled.
    gps_ok = bool(r["latitude"] and r["longitude"] and r["gps_verified_at"])
    score = min(
        (30 if gps_ok else 0) + (20 if ai_ok else 0) + min(doc_score, 50),
        100,
    )
    grade = grade_for_score(score)
    if score != (r["trust_score"] or 0):
        _scores_changed += 1

    db.execute(
        text(
            """
            UPDATE listings
            SET ai_verified_real = :ai,
                document_score   = :doc,
                cof_uploaded     = :cof,
                deed_uploaded    = :deed,
                survey_uploaded  = :survey,
                trust_score      = :score,
                trust_grade      = :grade
            WHERE id = :id
            """
        ),
        {
            "id": r["id"],
            "ai": ai_ok,
            "doc": doc_score,
            "cof": flags["cof"],
            "deed": flags["deed"],
            "survey": flags["survey"],
            "score": score,
            "grade": grade,
        },
    )

# 4. The pillar itself. Guarded, per the README rule on DROP.
db.execute(text("ALTER TABLE listings DROP COLUMN IF EXISTS witness_count"))

db.execute(
    text(
        "INSERT INTO applied_migrations (name) VALUES (:name) "
        "ON CONFLICT (name) DO NOTHING"
    ),
    {"name": MIGRATION_NAME},
)
db.commit()

print(f"applied {MIGRATION_NAME}")
print(f"  listings recomputed    : {len(rows)}")
print(f"  ai_verified_real cleared: {_ai_cleared}")
print(f"  document_score corrected: {_docs_fixed}")
print(f"  document flags reset    : {_flags_fixed}")
print(f"  trust_score changed     : {_scores_changed}")
print("  witness_count dropped (or already absent)")
print("  (zeros on a re-run are expected — this migration is idempotent)")

for _row in db.execute(
    text(
        "SELECT trust_grade, COUNT(*) FROM listings "
        "GROUP BY 1 ORDER BY 2 DESC"
    )
):
    print(f"  {_row[0]:<10} {_row[1]}")
