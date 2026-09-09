"""
WITNESS REMOVAL + TRUST SCORE RECOMPUTATION
============================================

Rewrites trust_score and trust_grade for EVERY listing using the single
scorer in trust_engine.calculate_confidence_score:

    GPS 30 | AI 20 | Docs 50 = 100

Why this is needed
------------------
1. The witness pillar is gone. It was fed by an unauthenticated endpoint
   (POST /listings/{id}/confirm-visit, deleted), and its stored values
   are fabricated: seed_demo_listings.py hardcodes witness_count 3 and 5
   on listings nobody ever visited.

2. There were three trust formulas and they disagreed on every pillar.
   The same listing scored 90/emerald in trust_engine and 73/Silver in
   document_trust_engine, so a listing's grade depended on which action
   the agency last performed. All three now delegate to one function.

3. ai_verified_real is True on listings no audit ever ran against.
   migrate_fix_ai_default.py only reset rows WHERE latitude IS NULL, and
   every seeded row has coordinates, so all 25 were skipped. This uses a
   precise discriminator instead: the real audit writes ai_audit_report
   alongside the flag, and the seed never does. ai_verified_real = TRUE
   AND ai_audit_report IS NULL means "flag set, audit never ran".

4. The cof/deed/survey booleans are set on 23 listings, but only ONE of
   them has an actual uploaded file behind it. The demo seed sets all
   three flags on rows with no documents at all. Scoring from those
   flags would award up to 72 points for paperwork nobody uploaded —
   the same fabrication the witness counter was doing.

   So Stage 2 scores documents from the listing_documents rows (the
   model's stated source of truth) and resets the flags to match. This
   makes scores FALL on every listing whose documents were fictional.
   Listing #4 currently holds document_score 72 off a single C of O
   worth 35, because _get_uploaded_doc_keys used to read the flags.

Usage
-----
    python migrate_witness_removal.py                 # dry run (default)
    python migrate_witness_removal.py --apply         # write changes
    python migrate_witness_removal.py --drop-column   # drop witness_count

DRY RUN IS THE DEFAULT. This rewrites every row in `listings`, so it
refuses to act without --apply, regardless of what the other migrate_*
scripts in this directory do.

Run --drop-column ONLY after the code above is deployed. Dropping
witness_count while the old code is live would 500 every listing query.
Order: deploy code -> --apply -> --drop-column.
"""
import os
import sys
from collections import Counter

from dotenv import load_dotenv

load_dotenv()

from app.models_registry import register_all_models  # noqa: E402

register_all_models()

from sqlalchemy import text  # noqa: E402
from app.database.db import engine  # noqa: E402
from app.services.document_trust_engine import (  # noqa: E402
    calculate_document_score,
    DOCUMENT_SCORES,
)
from app.services.trust_engine import grade_for_score  # noqa: E402

APPLY = "--apply" in sys.argv
DROP_COLUMN = "--drop-column" in sys.argv

GRADE_ORDER = ["emerald", "gold", "silver", "bronze", "ungraded"]


FLAG_FOR_KEY = {
    "c_of_o": "cof_uploaded",
    "deed_of_assignment": "deed_uploaded",
    "survey_plan": "survey_uploaded",
}


def real_doc_keys(conn, listing_id):
    """
    Document keys backed by an actual uploaded file.

    From listing_documents, never from the cof/deed/survey booleans —
    those are set on 22 listings that have no documents at all.
    """
    rows = conn.execute(
        text("SELECT DISTINCT doc_type FROM listing_documents WHERE listing_id = :i"),
        {"i": listing_id},
    ).all()
    return [r[0] for r in rows if r[0]]


def doc_score_from_real(keys):
    """The document score real uploaded files earn, on the 0-100 scale."""
    scorable = [k for k in keys if k in DOCUMENT_SCORES]
    if not scorable:
        return 0
    return calculate_document_score(scorable).final_score


def score_from(gps_ok, ai_ok, doc_score):
    """Mirror of trust_engine.calculate_confidence_score."""
    return min((30 if gps_ok else 0) + (20 if ai_ok else 0) + min(doc_score, 50), 100)


def main():
    mode = "APPLY" if APPLY else "DRY RUN"
    print("=" * 72)
    print(f"  WITNESS REMOVAL + TRUST RECOMPUTATION   [{mode}]")
    print("=" * 72)

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, tenant_id, title,
                   latitude, longitude, gps_verified_at,
                   ai_verified_real, ai_audit_report,
                   cof_uploaded, deed_uploaded, survey_uploaded,
                   document_score, witness_count,
                   trust_score, trust_grade
            FROM listings
            ORDER BY id
        """)).mappings().all()

        if not rows:
            print("\nNo listings found. Nothing to do.")
            return

        print(f"\nListings found: {len(rows)}\n")

        transitions = Counter()
        ai_cleared = 0
        doc_fixed = 0
        flags_fixed = 0
        witness_wiped = 0
        score_changes = []
        updates = []

        for r in rows:
            # --- Stage 1: flag set but no audit ever ran ---
            ai_ok = bool(r["ai_verified_real"])
            if ai_ok and not r["ai_audit_report"]:
                ai_ok = False
                ai_cleared += 1

            # --- Stage 2: score documents from real files, reset flags ---
            old_doc = r["document_score"] or 0
            keys = real_doc_keys(conn, r["id"])
            new_doc = doc_score_from_real(keys)
            if new_doc != old_doc:
                doc_fixed += 1

            new_flags = {
                "cof_uploaded": "c_of_o" in keys,
                "deed_uploaded": "deed_of_assignment" in keys,
                "survey_uploaded": "survey_plan" in keys,
            }
            if any(
                bool(r[f]) != v for f, v in new_flags.items()
            ):
                flags_fixed += 1

            # --- Stage 3: recompute ---
            gps_ok = bool(r["latitude"] and r["longitude"] and r["gps_verified_at"])
            new_score = score_from(gps_ok, ai_ok, new_doc)
            new_grade = grade_for_score(new_score)

            old_score = r["trust_score"] or 0
            old_grade = (r["trust_grade"] or "ungraded").lower()

            # --- Stage 4: witness counter ---
            if (r["witness_count"] or 0) != 0:
                witness_wiped += 1

            transitions[(old_grade, new_grade)] += 1
            if new_score != old_score:
                score_changes.append(
                    (r["id"], r["title"], old_score, new_score, old_grade, new_grade)
                )

            updates.append({
                "id": r["id"],
                "ai": ai_ok,
                "doc": new_doc,
                "score": new_score,
                "grade": new_grade,
                **new_flags,
            })

        # ── GRADE TRANSITION MATRIX ──────────────────────────────
        print("GRADE TRANSITIONS")
        print("-" * 72)
        moved = 0
        for old in GRADE_ORDER:
            for new in GRADE_ORDER:
                n = transitions.get((old, new), 0)
                if not n:
                    continue
                if old == new:
                    print(f"  {old:9s} -> {new:9s}  {n:4d}   (unchanged)")
                else:
                    direction = (
                        "DOWN" if GRADE_ORDER.index(new) > GRADE_ORDER.index(old)
                        else "UP"
                    )
                    print(f"  {old:9s} -> {new:9s}  {n:4d}   {direction}")
                    moved += n
        print("-" * 72)
        print(f"  {moved} of {len(rows)} listings change grade")

        # ── BEFORE / AFTER ───────────────────────────────────────
        before = Counter((r["trust_grade"] or "ungraded").lower() for r in rows)
        after = Counter(u["grade"] for u in updates)
        print("\nGRADE DISTRIBUTION")
        print("-" * 72)
        print(f"  {'grade':10s} {'before':>8s} {'after':>8s} {'delta':>8s}")
        for g in GRADE_ORDER:
            d = after[g] - before[g]
            print(f"  {g:10s} {before[g]:8d} {after[g]:8d} {d:+8d}")

        # ── FIXES ────────────────────────────────────────────────
        print("\nDATA FIXES")
        print("-" * 72)
        print(f"  ai_verified_real cleared (flag set, no audit report) : {ai_cleared}")
        print(f"  document_score recomputed from real uploaded files   : {doc_fixed}")
        print(f"  cof/deed/survey flags reset to match real files      : {flags_fixed}")
        print(f"  witness_count zeroed                                 : {witness_wiped}")

        # ── BIGGEST MOVERS ───────────────────────────────────────
        if score_changes:
            score_changes.sort(key=lambda x: x[3] - x[2])
            print(f"\nLARGEST SCORE CHANGES ({len(score_changes)} listings change score)")
            print("-" * 72)
            for lid, title, o, n, og, ng in score_changes[:10]:
                t = (title or "")[:38]
                print(f"  #{lid:<4d} {t:38s} {o:3d} -> {n:3d}   {og} -> {ng}")
            if len(score_changes) > 10:
                print(f"  ... and {len(score_changes) - 10} more")

        # ── WRITE ────────────────────────────────────────────────
        if not APPLY:
            print("\n" + "=" * 72)
            print("  DRY RUN — nothing written.")
            print("  Re-run with --apply to commit these changes.")
            print("=" * 72)
            return

        for u in updates:
            conn.execute(
                text("""
                    UPDATE listings
                    SET ai_verified_real = :ai,
                        document_score   = :doc,
                        cof_uploaded     = :cof_uploaded,
                        deed_uploaded    = :deed_uploaded,
                        survey_uploaded  = :survey_uploaded,
                        trust_score      = :score,
                        trust_grade      = :grade,
                        witness_count    = 0
                    WHERE id = :id
                """),
                u,
            )
        conn.commit()
        print("\n" + "=" * 72)
        print(f"  APPLIED — {len(updates)} listings recomputed.")
        print("  Next: deploy the code, then run --drop-column.")
        print("=" * 72)


def drop_column():
    print("=" * 72)
    print("  DROP witness_count COLUMN")
    print("=" * 72)
    print("\nThis is safe ONLY once the code that reads witness_count is")
    print("deployed. If old code is still live, every listing query 500s.\n")
    reply = os.getenv("CONFIRM_DROP", "")
    if reply != "yes":
        print("Refusing to drop. Re-run with CONFIRM_DROP=yes to proceed.")
        return
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE listings DROP COLUMN IF EXISTS witness_count"))
        conn.commit()
    print("[OK] witness_count dropped.")


if __name__ == "__main__":
    if DROP_COLUMN:
        drop_column()
    else:
        main()
