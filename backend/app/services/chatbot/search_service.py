from typing import List  # 🔹 SOCKET: Now used in type hints
from sqlalchemy.orm import Session, joinedload
from app.listings.models import Listing
from app.services.trust_engine import (
    calculate_confidence_score,
)  # 🔹 SOCKET: Now used in logic


def execute_premium_search(db: Session, tenant_id: int, prefs: dict) -> dict:
    """
    World-Class Network Search:
    Prioritizes current Realtor, but pulls from the Partner Network if empty.
    """
    # 1. SETUP BASE FILTERS
    location = prefs.get("location", "").strip()
    p_type = prefs.get("property_type", "").strip()

    # 2. PRIMARY SEARCH (Current Realtor)
    query = (
        db.query(Listing)
        .options(joinedload(Listing.images))
        .filter(Listing.tenant_id == tenant_id, Listing.status == "verified")
    )

    if location:
        query = query.filter(Listing.location.ilike(f"%{location}%"))
    if p_type:
        query = query.filter(Listing.property_type.ilike(f"%{p_type}%"))

    # Explicitly type the list to satisfy Ruff F401
    matches: List[Listing] = query.limit(3).all()

    if matches:
        # 🔹 SOCKET: Use the trust engine to verify scores before returning
        for prop in matches:
            prop.calculated_trust = calculate_confidence_score(prop)
        return {"source": "direct", "data": matches}

    # 3. SHADOW SEARCH (Partner Referral)
    # If original realtor has nothing, we find high-trust partners
    net_query = (
        db.query(Listing)
        .options(joinedload(Listing.images))
        .filter(Listing.tenant_id != tenant_id, Listing.status == "verified")
    )

    if location:
        net_query = net_query.filter(Listing.location.ilike(f"%{location}%"))
    if p_type:
        net_query = net_query.filter(Listing.property_type.ilike(f"%{p_type}%"))

    referrals: List[Listing] = net_query.limit(2).all()

    if referrals:
        for prop in referrals:
            prop.calculated_trust = calculate_confidence_score(prop)
        return {"source": "referral", "data": referrals}

    return {"source": "none", "data": []}
