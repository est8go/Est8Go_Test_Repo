import logging
from geopy.distance import geodesic
from app.listings.models import Listing

logger = logging.getLogger(__name__)

# Coordinate centers for validation (expand as needed)
ZONE_COORDS = {
    "maitama": (9.0770, 7.5023),
    "asokoro": (9.0358, 7.5186),
    "gwarinpa": (9.1098, 7.4042),
    "kabusa": (8.9700, 7.4200),
}


def verify_gps_proximity(claimed_location: str, lat: float, lng: float) -> int:
    """Returns a Trust Score (0-100) based on GPS proximity to claimed area."""
    loc_key = claimed_location.lower().strip()
    if loc_key not in ZONE_COORDS:
        return 60  # Default if area center isn't mapped

    distance = geodesic(ZONE_COORDS[loc_key], (lat, lng)).km
    if distance < 2.0:
        return 100
    if distance < 5.0:
        return 80
    if distance < 10.0:
        return 40
    return 10


def calculate_confidence_score(listing: Listing) -> int:
    """
    Master algorithm for the Est8Go Trust Score.
    """
    score = 0

    # 1. Document Pillar (40%)
    if listing.status == "verified":
        score += 40
    elif listing.status == "pending_review":
        score += 15

    # 2. Physical Pillar (30%) - Proximity Check
    # We check for both 'latitude/longitude' and 'lat/lng' to prevent errors
    lat = getattr(listing, "latitude", getattr(listing, "lat", None))
    lng = getattr(listing, "longitude", getattr(listing, "lng", None))

    if lat and lng:
        # If we have a location name, we verify proximity
        if listing.location:
            proximity_score = verify_gps_proximity(listing.location, lat, lng)
            # We scale the proximity score to our 30% pillar
            score += int((proximity_score / 100) * 30)
        else:
            score += 15  # Gave GPS but didn't specify location name

    # 3. AI Authenticity Pillar (20%)
    # Proves the images are real and not international stock photos
    # Note: Use getattr to safely check for the field
    if getattr(listing, "ai_verified_real", True):
        score += 20

    # 4. Professionalism (10%)
    images_count = (
        len(listing.images) if hasattr(listing, "images") and listing.images else 0
    )
    if images_count >= 3:
        score += 5
    if getattr(listing, "nearest_landmark", None):
        score += 5

    return score


def get_trust_label(score: int) -> dict:
    """
    PREMIUM GRADING SYSTEM:
    85 - 100: EMERALD (Green)
    60 - 84:  BLUE (Verified)
    40 - 59:  AMBER (Caution)
    0  - 39:  ROSE (Red)
    """
    if score >= 85:
        return {"color": "emerald", "icon": "🟢", "text": "Premium"}
    if score >= 60:
        return {"color": "blue", "icon": "🔵", "text": "Verified"}
    if score >= 40:
        return {"color": "amber", "icon": "🟡", "text": "Caution"}
    return {"color": "rose", "icon": "🔴", "text": "Flagged"}
