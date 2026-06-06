from typing import List  # 🔹 SOCKET: Now used in type hints
from sqlalchemy.orm import Session, joinedload
from app.listings.models import Listing
from app.services.trust_engine import (
    calculate_confidence_score,
)  # 🔹 SOCKET: Now used in logic


def execute_premium_search(db: Session, tenant_id: int, prefs: dict) -> dict:
    """
    ULTIMATE SEARCH ENGINE:
    1. Sorts by Trust (Emerald First)
    2. Searches Current Realtor, then the Partner Network
    3. Calculates Total Count for the Boutique
    4. Saves 'last_viewed_id' for the Handshake
    """
    location = prefs.get("location", "").strip()
    p_type = prefs.get("property_type", "").strip()
    budget_max = prefs.get("budget_max") or prefs.get("budget")
    budget_min = prefs.get("budget_min")

    # --- STEP 1: PRIMARY SEARCH (Current Realtor) ---
    query = (
        db.query(Listing)
        .options(joinedload(Listing.images))
        .filter(Listing.tenant_id == tenant_id, Listing.status == "verified")
    )

    if location:
        query = query.filter(Listing.location.ilike(f"%{location}%"))
    if p_type:
        query = query.filter(Listing.property_type.ilike(f"%{p_type}%"))
    if budget_max:
        query = query.filter(Listing.price <= budget_max)
    if budget_min:
        query = query.filter(Listing.price >= budget_min)

    # 🔹 MULTI-TIER SORTING: High Trust Score first, then Lowest Price
    query = query.order_by(Listing.trust_score.desc(), Listing.price.asc())

    primary_matches: List[Listing] = query.all()

    if primary_matches:
        prefs["last_viewed_id"] = primary_matches[0].id

        # We still calculate the 'Live' trust for the builder
        for prop in primary_matches:
            prop.calculated_trust = calculate_confidence_score(prop)

        return {
            "source": "direct",
            "data": primary_matches[:5],
            "total_count": len(primary_matches),
            "prefs": prefs,
        }

    # --- STEP 2: SHADOW SEARCH (Partner Referral Network) ---
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
    if budget_max:
        net_query = net_query.filter(Listing.price <= budget_max)
    if budget_min:
        net_query = net_query.filter(Listing.price >= budget_min)

    # Sort the network results as well
    net_query = net_query.order_by(Listing.trust_score.desc(), Listing.price.asc())

    referrals: List[Listing] = net_query.all()  # 🔹 SOCKET: Adds type hint

    if referrals:
        # Save the ID of the top referral match
        prefs["last_viewed_id"] = referrals[0].id

        for prop in referrals:
            prop.calculated_trust = calculate_confidence_score(prop)

        return {
            "source": "referral",
            "data": referrals[:5],
            "total_count": len(referrals),
            "prefs": prefs,
        }

    # --- STEP 3: NO MATCHES ---
    return {"source": "none", "data": [], "total_count": 0, "prefs": prefs}


def get_tenant_areas_by_budget(
    db,
    tenant_id: int,
    budget: int,
    property_type: str = None,
    city: str = None,
) -> list:
    """
    Returns areas from tenant listings that have at least one property
    within the given budget. Sorted by min_price ascending.
    """
    from app.listings.models import Listing
    from sqlalchemy import func

    query = db.query(
        Listing.location,
        func.min(Listing.price).label("min_price"),
        func.count(Listing.id).label("count"),
    ).filter(
        Listing.tenant_id == tenant_id,
        Listing.price <= budget,
        Listing.status == "verified",
    )

    if property_type:
        query = query.filter(
            Listing.property_type.ilike(f"%{property_type}%")
        )

    if city:
        query = query.filter(
            Listing.location.ilike(f"%{city}%")
        )

    results = query.group_by(Listing.location).order_by("min_price").limit(6).all()

    return [
        {
            "area": r.location or "",
            "min_price": int(r.min_price or 0),
            "count": int(r.count or 0),
        }
        for r in results
        if r.location
    ]


def get_tenant_cheapest_listing(
    db,
    tenant_id: int,
    property_type: str = None,
) -> dict:
    """
    Returns the cheapest verified listing for this tenant.
    Used when buyer budget is too low.
    """
    from app.listings.models import Listing

    query = db.query(Listing).filter(
        Listing.tenant_id == tenant_id,
        Listing.status == "verified",
    )

    if property_type:
        query = query.filter(
            Listing.property_type.ilike(f"%{property_type}%")
        )

    listing = query.order_by(Listing.price.asc()).first()

    if not listing:
        return {}

    price = listing.price or 0
    if price >= 1_000_000_000:
        price_fmt = f"₦{price/1_000_000_000:.1f}B"
    elif price >= 1_000_000:
        price_fmt = f"₦{price/1_000_000:.0f}M"
    else:
        price_fmt = f"₦{price:,}"

    return {
        "id": listing.id,
        "title": listing.title,
        "location": listing.location,
        "price": price,
        "price_fmt": price_fmt,
        "trust_score": listing.trust_score,
        "trust_grade": listing.trust_grade,
        "property_type": listing.property_type,
    }
