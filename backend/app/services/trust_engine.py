"""
EST8GO TRUST ENGINE (v2.0)
============================
Upgraded to integrate:
    - Document Trust Engine (5-tier Nigerian document scoring)
    - GPS proximity verification with 30+ Nigerian zones
    - AI Vision audit results
    - Witness signals
    - Full 100-point scoring system

Scoring Breakdown:
    GPS Verification    → 30 pts
    AI Vision Audit     → 20 pts
    Document Score      → 40 pts
    Witness Signals     → 10 pts
    Total               → 100 pts
"""

import logging
from datetime import datetime
from geopy.distance import geodesic
from app.listings.models import Listing

logger = logging.getLogger(__name__)


# ================================================================
# ZONE COORDINATES — 30+ Nigerian Areas
# ================================================================

ZONE_COORDS = {
    # ABUJA
    "maitama": (9.0770, 7.5023),
    "asokoro": (9.0358, 7.5186),
    "gwarinpa": (9.1098, 7.4042),
    "kabusa": (8.9700, 7.4200),
    "katampe": (9.0850, 7.4300),
    "jabi": (9.0650, 7.4380),
    "wuse": (9.0580, 7.4892),
    "wuse 2": (9.0580, 7.4892),
    "garki": (9.0411, 7.4769),
    "kubwa": (9.1367, 7.3517),
    "lugbe": (8.9856, 7.3928),
    "galadimawa": (9.0121, 7.4456),
    "apo": (8.9967, 7.5233),
    "lifecamp": (9.0912, 7.4167),
    "abuja": (9.0765, 7.3986),
    # LAGOS
    "lekki": (6.4350, 3.4510),
    "vi": (6.4281, 3.4219),
    "victoria island": (6.4281, 3.4219),
    "ikoyi": (6.4550, 3.4350),
    "ajah": (6.4674, 3.5759),
    "surulere": (6.4969, 3.3515),
    "ikeja": (6.6018, 3.3515),
    "magodo": (6.6167, 3.3833),
    "gbagada": (6.5500, 3.3833),
    "lagos": (6.5244, 3.3792),
    # PORT HARCOURT
    "ph": (4.8156, 7.0498),
    "port harcourt": (4.8156, 7.0498),
    # OTHER CITIES
    "ibadan": (7.3775, 3.9470),
    "kano": (12.0022, 8.5920),
    "enugu": (6.4584, 7.5464),
    "benin": (6.3350, 5.6270),
    "warri": (5.5167, 5.7500),
    "owerri": (5.4836, 7.0333),
}


# ================================================================
# GPS PROXIMITY
# ================================================================


def verify_gps_proximity(claimed_location: str, lat: float, lng: float) -> int:
    """Returns proximity score 0-100 based on GPS distance from claimed area."""
    loc_key = claimed_location.lower().strip()
    coords = ZONE_COORDS.get(loc_key)

    if not coords:
        for zone, zone_coords in ZONE_COORDS.items():
            if zone in loc_key or loc_key in zone:
                coords = zone_coords
                break

    if not coords:
        logger.warning(f"Zone '{claimed_location}' not mapped — defaulting 60")
        return 60

    distance = geodesic(coords, (lat, lng)).km
    if distance < 2.0:
        return 100
    if distance < 5.0:
        return 80
    if distance < 10.0:
        return 40
    return 10


def is_gps_expired(listing: Listing) -> bool:
    """GPS verification expires after 60 days."""
    if not getattr(listing, "gps_verified_at", None):
        return False
    return (datetime.utcnow() - listing.gps_verified_at).days > 60


# ================================================================
# MASTER CONFIDENCE SCORE
# ================================================================


def calculate_confidence_score(listing: Listing) -> int:
    """
    THE trust score. This is the only implementation — every other
    scorer in the codebase delegates here.

    GPS:30 | AI:20 | Docs:50 = 100

    There used to be three of these and they disagreed on every pillar.
    The same listing scored 90/emerald here and 73/Silver in
    document_trust_engine, so a listing's grade depended on which
    action the agency happened to perform last: a photo upload runs
    the AI audit, which wrote the score with the other formula and
    silently demoted whatever a GPS capture had promoted. Anything
    that needs a trust number calls this function.

    The witness pillar is gone. It was fed by an unauthenticated
    endpoint, its stored values are fabricated by the demo seed, and a
    site-visit count attested by the party whose score it raises is not
    a signal. Its 10 points moved to documents — the only pillar backed
    by an artefact the agency actually uploaded.

    document_score is stored on a 0-100 scale and truncated here, not
    rescaled: a listing below the cap keeps exactly the points it has.
    """
    gps_score = 30 if (
        getattr(listing, "latitude", None)
        and getattr(listing, "longitude", None)
        and getattr(listing, "gps_verified_at", None)
    ) else 0

    ai_score = 20 if getattr(listing, "ai_verified_real", False) else 0

    doc_score = min(getattr(listing, "document_score", 0) or 0, 50)

    return min(gps_score + ai_score + doc_score, 100)


def grade_for_score(score: int) -> str:
    """
    THE grade ladder. Lowercase, matching the trust_grade column.
    Kept in step with get_trust_label() below.
    """
    return (
        "emerald" if score >= 85 else
        "gold" if score >= 70 else
        "silver" if score >= 55 else
        "bronze" if score > 0 else
        "ungraded"
    )


# ================================================================
# TRUST LABEL (UI Display)
# ================================================================


def get_trust_label(score: int) -> dict:
    if score >= 85:
        return {
            "color": "emerald",
            "icon": "🟢",
            "text": "Emerald — Premium Verified",
            "grade": "emerald",
        }
    if score >= 70:
        return {
            "color": "gold",
            "icon": "🔵",
            "text": "Gold — Verified",
            "grade": "gold",
        }
    if score >= 55:
        return {
            "color": "amber",
            "icon": "🟡",
            "text": "Amber — In Progress",
            "grade": "silver",
        }
    if score > 0:
        return {
            "color": "rose",
            "icon": "🟠",
            "text": "Bronze — Incomplete",
            "grade": "bronze",
        }
    return {
        "color": "gray",
        "icon": "⚪",
        "text": "Ungraded — Not Started",
        "grade": "ungraded",
    }


# ================================================================
# BATCH UPDATER (Admin / Nightly Job)
# ================================================================


def recalculate_all_trust_scores(db) -> dict:
    """Recalculates trust scores for all listings. Run nightly."""
    listings = db.query(Listing).all()
    updated = errors = 0

    for listing in listings:
        try:
            new_score = calculate_confidence_score(listing)
            listing.trust_score = new_score
            listing.trust_grade = grade_for_score(new_score)
            updated += 1
        except Exception as e:
            logger.error(f"Failed listing {listing.id}: {e}")
            errors += 1

    db.commit()
    logger.info(f"Trust recalc: {updated} updated, {errors} errors")
    return {"updated": updated, "errors": errors, "total": len(listings)}
