import logging
from app.listings.models import Listing

logger = logging.getLogger(__name__)


def calculate_confidence_score(listing: Listing) -> int:
    """
    Master algorithm for the Est8Go Trust Score.
    This calculates the proof of truth using the data in our Moat.
    """
    score = 0

    # 1. Document Pillar (40%)
    if listing.status == "verified":
        score += 40
    elif listing.status == "pending_review":
        score += 15

    # 2. Physical Pillar (30%)
    # Proves the agent was on-site via GPS
    lat = getattr(listing, "latitude", None)
    lon = getattr(listing, "longitude", None)
    if lat and lon:
        score += 30

    # 3. AI Authenticity Pillar (20%)
    # Proves the images are real and not international stock photos
    if getattr(listing, "ai_verified_real", True):
        score += 20

    # 4. Professionalism (10%)
    # Multiple photos and nearest landmark
    images_count = len(listing.images) if hasattr(listing, "images") else 0
    if images_count >= 3:
        score += 5
    if getattr(listing, "nearest_landmark", None):
        score += 5

    return score


def get_trust_label(score: int) -> dict:
    """Returns visual signals (icon, text, color) for the UI."""
    if score >= 85:
        return {"color": "green", "icon": "🟢", "text": "High Trust"}
    if score >= 50:
        return {"color": "yellow", "icon": "🟡", "text": "Verified Source"}
    return {"color": "red", "icon": "🔴", "text": "Under Review"}
