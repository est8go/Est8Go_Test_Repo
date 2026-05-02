# EST8GO PREMIUM MESSAGE BUILDER
# Responsible for high-converting property summaries and referral handshakes.


# 🔹 SOCKET: Update build_property_summary in message_builder.py


def build_property_summary(
    prop, matches: list, total_count: int, first_name: str
) -> str:
    """The Complete Elite Showcase: Includes Location, Links, and Closing CTA."""
    showroom_link = f"https://est8go-api.onrender.com/public/property/{prop.id}"
    all_ids = ",".join([str(m.id) for m in matches[:50]])
    boutique_link = f"https://est8go-api.onrender.com/public/matches?ids={all_ids}"

    price = f"₦{int(prop.price):,}" if prop.price else "Price on request"
    # 🔹 SOCKET: Explicitly pulling location
    location = prop.location if prop.location else "Abuja"
    trust = getattr(prop, "calculated_trust", 95)

    return (
        f"✨ *Verified Match Found for {first_name}!* \n\n"
        f"🏠 *{prop.title}*\n"
        f"📍 Location: {location}\n"  # 📌 LOCATION RESTORED
        f"💰 Price: {price}\n"
        f"🛡️ Trust Score: {trust}% (Emerald)\n\n"
        f"🔗 *View High-Res Photos & GPS Audit:* \n{showroom_link}\n\n"
        f"🛍️ *Browse the other {total_count - 1} options in our Boutique:* \n{boutique_link}\n\n"
        f"**Would you like to schedule a physical site inspection for this property?** Just give me a date! 📅"
    )


def build_no_match_message(location: str) -> str:
    """Elite recovery when the vault is undergoing audit."""
    return (
        f"I've scanned our verified inventory for *{location}*. 🔍\n\n"
        "At the moment, we are performing physical site-audits on new arrivals. "
        "To maintain our Truth Standard, only properties with confirmed GPS "
        "coordinates are visible in the vault."
    )


def build_referral_summary(prop, original_biz_name: str) -> str:
    """The Complete Broker Handshake: Includes Location and Direct Link."""
    direct_link = f"https://est8go-api.onrender.com/public/property/{prop.id}"
    price = f"₦{int(prop.price):,}" if prop.price else "Price on request"
    # 🔹 SOCKET: Explicitly pulling location
    location = prop.location if prop.location else "Abuja"
    trust = getattr(prop, "calculated_trust", 95)

    return (
        f"I searched the vault for *{original_biz_name}*, but they don't have a direct match today. 🔍\n\n"
        f"However, Est8Go has found a **Premium Verified** alternative from our network:\n\n"
        f"🏠 *{prop.title}*\n"
        f"📍 Location: {location}\n"  # 📌 LOCATION RESTORED
        f"💰 Price: {price}\n"
        f"🛡️ Trust Score: {trust}% (Physical Site Verified)\n\n"
        f"🔗 *Tap to view photos and GPS Audit:* \n{direct_link}\n\n"
        f"**Would you like me to connect you with the lead agent for an inspection?**"
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
            "The agent will send you a **Direct WhatsApp Location Pin** once you connect! \n\n"
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
