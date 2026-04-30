from typing import List
from sqlalchemy.orm import Session, joinedload
from app.listings.models import Listing
from app.services.trust_engine import calculate_confidence_score


def execute_premium_search(db: Session, tenant_id: int, prefs: dict) -> List[Listing]:
    query = (
        db.query(Listing)
        .options(joinedload(Listing.images))
        .filter(Listing.tenant_id == tenant_id, Listing.status == "verified")
    )

    if prefs.get("location"):
        # 🔹 SOCKET: Split by comma and take the first one, or search for ANY of them
        loc_input = (
            prefs["location"].replace(",", " ").split()[0]
        )  # Takes first area mentioned
        query = query.filter(Listing.location.ilike(f"%{loc_input}%"))

    # 2. Property Type Filtering
    if prefs.get("property_type"):
        p_type = prefs["property_type"].strip()
        query = query.filter(Listing.property_type.ilike(f"%{p_type}%"))

    # 3. Budget Intelligence (20% Negotiation Buffer)
    if prefs.get("budget"):
        try:
            budget_val = int(prefs["budget"])
            query = query.filter(Listing.price <= (budget_val * 1.2))
        except (ValueError, TypeError):
            pass

    results = query.limit(5).all()

    # Inject Trust Scores before returning
    for item in results:
        item.calculated_trust = calculate_confidence_score(item)

    return results
