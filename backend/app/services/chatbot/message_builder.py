# EST8GO PREMIUM MESSAGE BUILDER
# Responsible for high-converting property summaries and referral handshakes.

NEARBY_AREAS = {
    "maitama":         ["asokoro", "wuse", "garki"],
    "asokoro":         ["maitama", "garki", "wuse"],
    "gwarinpa":        ["kubwa", "lugbe", "lokogoma"],
    "kubwa":           ["gwarinpa", "lugbe", "gwagwalada"],
    "lugbe":           ["kubwa", "gwarinpa", "lokogoma"],
    "lekki":           ["ajah", "victoria island", "ikoyi"],
    "ajah":            ["lekki", "sangotedo", "abraham adesanya"],
    "ikeja":           ["maryland", "ojodu", "magodo"],
    "victoria island": ["ikoyi", "lekki", "oniru"],
    "ikoyi":           ["victoria island", "lekki", "obalende"],
    "surulere":        ["yaba", "gbagada", "magodo"],
    "yaba":            ["surulere", "gbagada", "maryland"],
    "garki":           ["maitama", "wuse", "asokoro"],
    "wuse":            ["garki", "maitama", "jabi"],
    "jabi":            ["wuse", "maitama", "lifecamp"],
    "gbagada":         ["yaba", "surulere", "maryland"],
    "magodo":          ["ojodu", "ikeja", "gbagada"],
    "ojodu":           ["magodo", "ikeja", "berger"],
    "lokogoma":        ["gwarinpa", "lugbe", "kubwa"],
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
    showroom_link = f"https://est8go-api.onrender.com/public/property/{prop.id}"
    all_ids = ",".join([str(m.id) for m in matches[:50]])
    boutique_link = f"https://est8go-api.onrender.com/public/matches?ids={all_ids}"

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
        f"🔗 *View High-Res Photos & GPS Audit:* \n{showroom_link}\n\n"
        f"{boutique_section}"
        f"Would you like to schedule a physical site inspection for this property? Just say the word and we will arrange it. 📅"
    )


def build_no_results_message(
    location: str, property_type: str, budget=None
) -> str:
    loc = location.title() if location else "that area"
    ptype = property_type.title() if property_type else "property"

    budget_note = ""
    if budget:
        try:
            budget_int = int(budget)
            if budget_int < 10_000_000:
                budget_note = (
                    f"\n\nNote: Your budget of "
                    f"₦{budget_int / 1_000_000:.0f}M may be below "
                    f"market rate for verified properties in "
                    f"{loc}. Would you like to explore a "
                    f"higher budget or a different area?"
                )
        except (ValueError, TypeError):
            pass

    location_lower = (location or "").lower().strip()
    nearby = NEARBY_AREAS.get(location_lower, [])
    nearby_text = ""
    if nearby:
        nearby_formatted = ", ".join(a.title() for a in nearby[:3])
        nearby_text = (
            f"\n\nNearby areas with active listings:\n"
            f"{nearby_formatted}\n\n"
            f"Would you like me to search any of these?"
        )

    return (
        f"We don't have verified {ptype} listings "
        f"in *{loc}* right now. 🔍\n\n"
        f"This could mean:\n"
        f"Our agents are currently auditing new "
        f"arrivals in that area, or\n"
        f"Inventory in {loc} is currently limited."
        f"{nearby_text}"
        f"{budget_note}"
    )


def build_referral_summary(prop, original_biz_name: str) -> str:
    """The Complete Broker Handshake: Includes Location and Direct Link."""
    direct_link = f"https://est8go-api.onrender.com/public/property/{prop.id}"
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
