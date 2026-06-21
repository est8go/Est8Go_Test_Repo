# EST8GO PREMIUM MESSAGE BUILDER
# Responsible for high-converting property summaries and referral handshakes.

import os

NEARBY_AREAS = {
    "maitama": ["asokoro", "wuse 2", "katampe"],
    "asokoro": ["maitama", "garki", "wuse"],
    "gwarinpa": ["kubwa", "lugbe", "lokogoma"],
    "kubwa": ["gwarinpa", "lugbe", "gwagwalada"],
    "lugbe": ["kubwa", "gwarinpa", "lokogoma"],
    "garki": ["maitama", "wuse", "asokoro"],
    "wuse": ["garki", "maitama", "jabi"],
    "wuse 2": ["wuse", "maitama", "jabi"],
    "jabi": ["wuse", "maitama", "lifecamp"],
    "lifecamp": ["gwarinpa", "jabi", "kubwa", "dawaki"],
    "katampe": ["maitama", "wuse", "gwarinpa", "jabi"],
    "apo": ["garki", "asokoro", "guzape"],
    "guzape": ["asokoro", "apo", "maitama", "wuse", "garki"],
    "lokogoma": ["gwarinpa", "lugbe", "kubwa"],
    "galadimawa": ["apo", "lokogoma", "gwarinpa"],
    "dawaki": ["gwarinpa", "lifecamp", "kubwa", "dutse"],
    "dutse": ["kubwa", "gwagwalada", "lugbe"],
    "nbora": ["lokogoma", "gwarinpa", "lugbe"],
    "gwagwalada": ["kubwa", "lugbe", "dutse"],
    "lekki": ["ajah", "victoria island", "ikoyi"],
    "ajah": ["lekki", "sangotedo", "badore"],
    "ikeja": ["maryland", "ojodu", "magodo"],
    "victoria island": ["ikoyi", "lekki", "oniru"],
    "ikoyi": ["victoria island", "lekki", "obalende"],
    "surulere": ["yaba", "gbagada", "magodo"],
    "yaba": ["surulere", "gbagada", "maryland"],
    "gbagada": ["yaba", "surulere", "maryland"],
    "magodo": ["ojodu", "ikeja", "gbagada"],
    "ojodu": ["magodo", "ikeja", "berger"],
    "sangotedo": ["ajah", "lekki", "badore"],
    "badore": ["ajah", "sangotedo", "lekki"],
    "maryland": ["ikeja", "gbagada", "yaba"],
    "port harcourt": ["rumuola", "gra ph", "trans amadi"],
    "gra ph": ["port harcourt", "rumuola", "old gra"],
    "rumuola": ["port harcourt", "gra ph", "rumuigbo"],
}

AREA_TO_CITY = {
    "maitama": "Abuja", "asokoro": "Abuja", "gwarinpa": "Abuja",
    "kubwa": "Abuja", "lugbe": "Abuja", "garki": "Abuja",
    "wuse": "Abuja", "wuse 2": "Abuja", "jabi": "Abuja",
    "lifecamp": "Abuja", "katampe": "Abuja", "apo": "Abuja",
    "guzape": "Abuja", "lokogoma": "Abuja", "galadimawa": "Abuja",
    "dawaki": "Abuja", "dutse": "Abuja", "nbora": "Abuja",
    "gwagwalada": "Abuja",
    "lekki": "Lagos", "ajah": "Lagos", "ikeja": "Lagos",
    "victoria island": "Lagos", "ikoyi": "Lagos", "surulere": "Lagos",
    "yaba": "Lagos", "gbagada": "Lagos", "magodo": "Lagos",
    "ojodu": "Lagos", "sangotedo": "Lagos", "badore": "Lagos",
    "maryland": "Lagos",
    "port harcourt": "Port Harcourt", "gra ph": "Port Harcourt",
    "rumuola": "Port Harcourt",
}


def _trust_grade(score) -> str:
    s = score or 0
    if s >= 85:
        return "Emerald"
    if s >= 70:
        return "Gold"
    if s >= 55:
        return "Silver"
    if s >= 30:
        return "Bronze"
    return "Unrated"


def _factual_badges(prop) -> list:
    """Buyer-facing verification badges built ONLY from real fields.
    No score, no grade, no AI. Each badge is a fact we can stand behind."""
    badges = []
    if getattr(prop, "latitude", None) or getattr(prop, "gps_location_match", False):
        badges.append("GPS recorded")
    doc_count = sum(
        1
        for f in (
            getattr(prop, "cof_uploaded", False),
            getattr(prop, "deed_uploaded", False),
            getattr(prop, "survey_uploaded", False),
        )
        if f
    )
    if doc_count:
        badges.append(f"{doc_count} document{'s' if doc_count != 1 else ''} on file")
    visits = getattr(prop, "witness_count", 0) or 0
    if visits:
        badges.append(f"{visits} site visit{'s' if visits != 1 else ''}")
    return badges


# 🔹 SOCKET: Update build_property_summary in message_builder.py


def build_property_summary(
    prop, matches: list, total_count: int, first_name: str
) -> str:
    """The Complete Elite Showcase: Includes Location, Links, and Closing CTA."""
    _base = os.getenv("BASE_URL", "https://est8go-api.onrender.com")
    showroom_link = f"{_base}/public/property/{prop.id}"
    all_ids = ",".join([str(m.id) for m in matches[:50]])
    boutique_link = f"{_base}/public/matches?ids={all_ids}"

    price = f"₦{int(prop.price):,}" if prop.price else "Price on request"
    location = (prop.location or "Abuja").title()
    _badges = _factual_badges(prop)
    badge_line = " · ".join(_badges) if _badges else "Verification details on the listing"

    count = len(matches) - 1
    options_text = "other option" if count == 1 else f"{count} other options"
    boutique_section = (
        f"🛍️ Browse {options_text} in our property vault:\n{boutique_link}\n\n"
        if len(matches) > 1
        else ""
    )

    return (
        f"✨ *Match Found for {first_name}!* \n\n"
        f"🏠 *{prop.title}*\n"
        f"📍 Location: {location}\n"
        f"💰 Price: *{price}*\n"
        f"🛡️ {badge_line}\n\n"
        f"🔗 *View Property Details & Photos:* \n{showroom_link}\n\n"
        f"{boutique_section}"
        f"Would you like to schedule a physical site inspection for this property? Just say the word and we will arrange it. 📅"
    )


def build_no_results_message(
    location: str,
    property_type: str,
    budget: int = None,
    nearby_areas: list = None,
    nearby_min_price: int = None,
) -> str:
    loc = location.title() if location else "that area"
    ptype = property_type.title() if property_type else "Property"
    location_lower = (location or "").lower().strip()

    budget_note = ""
    if nearby_min_price:
        try:
            budget_note = (
                f"\n\n💡 {ptype}s in nearby areas start from "
                f"₦{nearby_min_price / 1_000_000:.0f}M."
            )
        except (ValueError, TypeError):
            pass

    nearby = NEARBY_AREAS.get(location_lower, [])
    city = AREA_TO_CITY.get(location_lower, "")

    nearby_text = ""
    if nearby:
        nearby_formatted = " · ".join(a.title() for a in nearby[:3])
        nearby_text = (
            f"\n\n📍 *Nearby areas with active listings:*\n"
            f"{nearby_formatted}\n\n"
            f"Reply with any of these areas and I'll search immediately."
        )
    elif city:
        nearby_text = (
            f"\n\n📍 I can search other parts of *{city}* for you. "
            f"Which area would you like to try?"
        )

    next_steps = (
        f"\n\n*What would you like to do?*\n"
        f"1️⃣ Search a nearby area\n"
        f"2️⃣ Adjust my budget\n"
        f"3️⃣ Change property type\n"
        f"4️⃣ Start a new search"
    )

    return (
        f"I could not find any {ptype} listings in *{loc}* right now. 🔍"
        f"{nearby_text}"
        f"{budget_note}"
        f"{next_steps}"
    )


def build_comparison_message(listings: list, first_name: str) -> str:
    """
    Structured side-by-side comparison for WhatsApp.
    Picks best option by trust score, then price.
    """
    if not listings:
        return f"No properties to compare yet, {first_name}. Run a search first."

    lines = [f"🔍 *Side-by-Side Comparison for {first_name}:*\n"]

    for i, l in enumerate(listings, 1):
        price = f"₦{int(l.price) / 1_000_000:.0f}M" if l.price else "POA"
        location = (l.location or "").title()
        ptype = (l.property_type or "Property").title()

        # Verification badges: real fields only, no score, no AI
        _badges = _factual_badges(l)
        badge_str = " · ".join(_badges) if _badges else "Verification details on the listing"

        lines.append(
            f"*Option {i}: {l.title}*\n"
            f"📍 {location}  |  💰 {price}\n"
            f"🏠 {ptype}  ·  {badge_str}"
        )

    # Best pick: most complete verification record, then lowest price.
    # Ranking still uses the internal trust_score; it is never shown to the buyer.
    best = max(listings, key=lambda x: (x.trust_score or 0, -(x.price or 999_999_999)))
    best_idx = listings.index(best) + 1
    all_same_trust = len(set(l.trust_score or 0 for l in listings)) == 1
    reason = (
        "lowest price among similar listings"
        if all_same_trust
        else "most complete verification record"
    )

    sep = "─" * 28
    lines.append(
        f"\n{sep}\n"
        f"💡 *Best pick:* Option {best_idx}, {reason}.\n\n"
        f"Reply *{best_idx}* to view full details and book a site visit. 📅"
    )

    return "\n".join(lines)


def build_referral_summary(prop, original_biz_name: str) -> str:
    """The Complete Broker Handshake: Includes Location and Direct Link."""
    _base = os.getenv("BASE_URL", "https://est8go-api.onrender.com")
    direct_link = f"{_base}/public/property/{prop.id}"
    price = f"₦{int(prop.price):,}" if prop.price else "Price on request"
    location = (prop.location or "Abuja").title()
    _badges = _factual_badges(prop)
    badge_line = " · ".join(_badges) if _badges else "Verification details on the listing"

    return (
        f"I searched the vault for *{original_biz_name}*, but they don't have a direct match today. 🔍\n\n"
        f"However, Est8Go has found an alternative from our network:\n\n"
        f"🏠 *{prop.title}*\n"
        f"📍 Location: {location}\n"
        f"💰 Price: {price}\n"
        f"🛡️ {badge_line}\n\n"
        f"🔗 *Tap to view photos and location details:* \n{direct_link}\n\n"
        f"Would you like me to connect you with the lead agent for an inspection?"
    )


# 🔹 SOCKET: Add to the bottom of message_builder.py


def build_navigation_link(latitude: float, longitude: float, title: str) -> str:
    """Generates a Google Maps Deep Link for instant navigation."""
    # This URL format triggers the 'Start Navigation' mode on mobile phones
    return f"https://www.google.com/maps/dir/?api=1&destination={latitude},{longitude}"


def build_inspection_confirmation(
    first_name: str, prop_title: str, lat: float, lng: float,
    directions: str = None,
) -> str:
    """The final handshake message with a Safety Guard for missing GPS."""

    directions_block = (
        f"\n\n🗺️ *How to find us:*\n{directions}" if directions else ""
    )

    # 🔹 SOCKET: Safety Guard
    if lat is None or lng is None:
        return (
            f"Excellent, {first_name}! 🤝\n\n"
            f"I've shared your interest with the lead agent for *{prop_title}*. \n\n"
            "📍 *Site Location:* \n"
            "We are still confirming this property's GPS location. "
            "The agent will send you a direct WhatsApp location pin once you connect."
            + directions_block
            + "\n\nWhat time works best for your arrival? 🚗"
        )

    # Standard logic if GPS exists
    nav_link = build_navigation_link(lat, lng, prop_title)
    return (
        f"Excellent, {first_name}! 🤝\n\n"
        f"I've shared your interest with the lead agent for *{prop_title}*. \n\n"
        f"📍 *Site Navigation:* \n"
        f"Tap below to open Google Maps and get live directions to the property gate:\n"
        f"{nav_link}"
        + directions_block
        + "\n\nWhat time works best for your arrival? 🚗"
    )
