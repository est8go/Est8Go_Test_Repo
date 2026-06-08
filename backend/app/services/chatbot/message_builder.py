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
    trust = prop.trust_score or 0

    count = len(matches) - 1
    options_text = "other option" if count == 1 else f"{count} other options"
    boutique_section = (
        f"🛍️ Browse {options_text} in our verified vault:\n{boutique_link}\n\n"
        if len(matches) > 1
        else ""
    )

    return (
        f"✨ *Verified Match Found for {first_name}!* \n\n"
        f"🏠 *{prop.title}*\n"
        f"📍 Location: {location}\n"
        f"💰 Price: *{price}*\n"
        f"🛡️ Trust Score: *{trust}/100 ({_trust_grade(trust)})*\n\n"
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
                f"\n\n💡 Verified {ptype}s in nearby areas start from "
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
        f"No verified {ptype} listings found in *{loc}* right now. 🔍"
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
        score = l.trust_score or 0
        grade = _trust_grade(score)
        ptype = (l.property_type or "Property").title()

        # Verification badges
        badges = []
        if l.latitude or l.gps_location_match:
            badges.append("GPS ✅")
        if l.cof_uploaded or l.deed_uploaded or l.survey_uploaded:
            badges.append("Docs ✅")
        if l.ai_verified_real:
            badges.append("Smart Verified ✅")
        badge_str = " · ".join(badges) if badges else "Pending Verification"

        lines.append(
            f"*Option {i} — {l.title}*\n"
            f"📍 {location}  |  💰 {price}  |  🛡️ {score}/100 ({grade})\n"
            f"🏠 {ptype}  ·  {badge_str}"
        )

    # Best pick: highest trust, then lowest price
    best = max(listings, key=lambda x: (x.trust_score or 0, -(x.price or 999_999_999)))
    best_idx = listings.index(best) + 1
    best_price = best.price or 0
    all_same_trust = len(set(l.trust_score or 0 for l in listings)) == 1
    reason = (
        "lowest price among equal-trust options"
        if all_same_trust
        else "highest trust score — most verified by Est8Go"
    )

    sep = "─" * 28
    lines.append(
        f"\n{sep}\n"
        f"💡 *Best pick:* Option {best_idx} — {reason}.\n\n"
        f"Reply *{best_idx}* to view full details and book a site visit. 📅"
    )

    return "\n".join(lines)


def build_referral_summary(prop, original_biz_name: str) -> str:
    """The Complete Broker Handshake: Includes Location and Direct Link."""
    _base = os.getenv("BASE_URL", "https://est8go-api.onrender.com")
    direct_link = f"{_base}/public/property/{prop.id}"
    price = f"₦{int(prop.price):,}" if prop.price else "Price on request"
    location = (prop.location or "Abuja").title()
    trust = prop.trust_score or 0

    return (
        f"I searched the vault for *{original_biz_name}*, but they don't have a direct match today. 🔍\n\n"
        f"However, Est8Go has found a verified alternative from our network:\n\n"
        f"🏠 *{prop.title}*\n"
        f"📍 Location: {location}\n"
        f"💰 Price: {price}\n"
        f"🛡️ Trust Score: {trust}/100 ({_trust_grade(trust)})\n\n"
        f"🔗 *Tap to view photos and GPS Audit:* \n{direct_link}\n\n"
        f"Would you like me to connect you with the lead agent for an inspection?"
    )


# 🔹 SOCKET: Add to the bottom of message_builder.py


def build_navigation_link(latitude: float, longitude: float, title: str) -> str:
    """Generates a Google Maps Deep Link for instant navigation."""
    # This URL format triggers the 'Start Navigation' mode on mobile phones
    return f"https://www.google.com/maps/dir/?api=1&destination={latitude},{longitude}"


def build_inspection_confirmation(
    first_name: str, prop_title: str, lat: float, lng: float
) -> str:
    """The final handshake message with a Safety Guard for missing GPS."""

    # 🔹 SOCKET: Safety Guard
    if lat is None or lng is None:
        return (
            f"Excellent, {first_name}! 🤝\n\n"
            f"I've shared your interest with the lead agent for *{prop_title}*. \n\n"
            "📍 *Site Location:* \n"
            "This property is currently undergoing its final GPS audit. "
            "The agent will send you a direct WhatsApp location pin once you connect.\n\n"
            "What time works best for your arrival? 🚗"
        )

    # Standard logic if GPS exists
    nav_link = build_navigation_link(lat, lng, prop_title)
    return (
        f"Excellent, {first_name}! 🤝\n\n"
        f"I've shared your interest with the lead agent for *{prop_title}*. \n\n"
        f"📍 *Site Navigation:* \n"
        f"Tap below to open Google Maps and get live directions to the property gate:\n"
        f"{nav_link}\n\n"
        f"What time works best for your arrival? 🚗"
    )
