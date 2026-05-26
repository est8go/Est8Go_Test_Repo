"""
FIX: Reset wrongly-defaulted ai_verified_real flag.

The Listing model had ai_verified_real = Column(Boolean, default=True),
meaning every listing was awarded 20 free AI points without any audit.

This migration resets:
  - Listings where AI was never actually run (no GPS captured = definitely not audited)
  - Trust score reduced by 20 to compensate

Safe to run multiple times (uses WHERE ai_verified_real = true so
already-corrected rows are skipped).
"""
import os
from dotenv import load_dotenv
load_dotenv()

from app.models_registry import register_all_models
register_all_models()

from app.database.db import engine
from sqlalchemy import text

with engine.connect() as conn:
    # Reset AI flag on listings that have no GPS — they were never on-site
    # so an AI audit would not have been triggered either.
    result = conn.execute(text("""
        UPDATE listings
        SET ai_verified_real = false,
            trust_score = GREATEST(trust_score - 20, 0)
        WHERE ai_verified_real = true
          AND trust_score > 0
          AND (latitude IS NULL OR longitude IS NULL)
    """))
    conn.commit()
    print(f"[OK] Reset ai_verified_real on {result.rowcount} listings (no GPS = no audit)")

    # Also recalculate grades for any listing whose score changed
    result2 = conn.execute(text("""
        UPDATE listings
        SET trust_grade = CASE
            WHEN trust_score >= 85 THEN 'emerald'
            WHEN trust_score >= 70 THEN 'gold'
            WHEN trust_score >= 55 THEN 'silver'
            WHEN trust_score  > 0  THEN 'bronze'
            ELSE 'ungraded'
        END
        WHERE trust_score IS NOT NULL
    """))
    conn.commit()
    print(f"[OK] Recalculated trust_grade for {result2.rowcount} listings")

print("[DONE] Migration complete.")
