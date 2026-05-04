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
    Real-time trust score. Used by search engine to rank listings.
    Integrates GPS + AI Vision + Documents + Witnesses.
    """
    doc_keys = []
    if getattr(listing, "cof_uploaded", False):
        doc_keys.append("c_of_o")
    if getattr(listing, "deed_uploaded", False):
        doc_keys.append("deed_of_assignment")
    if getattr(listing, "survey_uploaded", False):
        doc_keys.append("survey_plan")

    lat = getattr(listing, "latitude", None)
    lng = getattr(listing, "longitude", None)
    gps_verified = bool(getattr(listing, "gps_verified_at", None)) or bool(lat and lng)
    gps_expired = is_gps_expired(listing) if gps_verified else False

    gps_location_match = False
    if lat and lng and listing.location:
        gps_location_match = verify_gps_proximity(listing.location, lat, lng) >= 80

    try:
        from app.services.document_trust_engine import calculate_full_trust_score

        result = calculate_full_trust_score(
            gps_verified=gps_verified,
            gps_expired=gps_expired,
            gps_location_match=gps_location_match,
            gps_photo_match=getattr(listing, "gps_photo_match", False),
            ai_verified=getattr(listing, "ai_verified_real", False),
            document_keys=doc_keys,
            witness_count=getattr(listing, "witness_count", 0) or 0,
        )
        return result["total_score"]

    except Exception as e:
        logger.error(f"Trust engine error listing {listing.id}: {e}")
        return _fallback(listing)


def _fallback(listing: Listing) -> int:
    """Simple fallback so search engine never crashes."""
    score = 0
    if listing.status == "verified":
        score += 40
    elif listing.status == "pending_review":
        score += 15
    lat = getattr(listing, "latitude", None)
    lng = getattr(listing, "longitude", None)
    if lat and lng:
        prox = (
            verify_gps_proximity(listing.location, lat, lng) if listing.location else 50
        )
        score += int((prox / 100) * 30)
    if getattr(listing, "ai_verified_real", False):
        score += 20
    imgs = len(listing.images) if hasattr(listing, "images") and listing.images else 0
    if imgs >= 3:
        score += 5
    if getattr(listing, "nearest_landmark", None):
        score += 5
    return score


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
    if score >= 60:
        return {
            "color": "gold",
            "icon": "🔵",
            "text": "Gold — Verified",
            "grade": "gold",
        }
    if score >= 40:
        return {
            "color": "amber",
            "icon": "🟡",
            "text": "Amber — Caution",
            "grade": "silver",
        }
    return {
        "color": "rose",
        "icon": "🔴",
        "text": "Flagged — Incomplete",
        "grade": "bronze",
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
            listing.trust_grade = get_trust_label(new_score)["grade"]
            updated += 1
        except Exception as e:
            logger.error(f"Failed listing {listing.id}: {e}")
            errors += 1

    db.commit()
    logger.info(f"Trust recalc: {updated} updated, {errors} errors")
    return {"updated": updated, "errors": errors, "total": len(listings)}
