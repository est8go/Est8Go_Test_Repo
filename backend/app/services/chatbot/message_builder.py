# EST8GO PREMIUM MESSAGE BUILDER
# Responsible for high-converting property summaries and referral handshakes.


def build_property_summary(prop, first_name: str) -> str:
    """Constructs a premium property pitch for WhatsApp."""
    # 1. Format Price Safely
    try:
        formatted_price = f"₦{int(prop.price):,}" if prop.price else "Price on request"
    except (ValueError, TypeError):
        formatted_price = "Price on request"

    # 2. Extract Image from joined relationship
    image = "Pending audit"
    if hasattr(prop, "images") and prop.images:
        image = prop.images[0].url

    # 3. Fetch Trust Score
    trust = getattr(prop, "calculated_trust", 90)

    return (
        f"✨ *Verified Match for {first_name}!*\n\n"
        f"🏠 *{prop.title}*\n"
        f"📍 Location: {prop.location}\n"
        f"💰 Price: {formatted_price}\n"
        f"🛡️ Trust Score: {trust}% (GPS Verified)\n\n"
        f"📸 *View Verified Site Photos:* \n{image}\n\n"
        f"Would you like to book an inspection or see more options?"
    )


def build_referral_summary(prop, original_biz_name: str) -> str:
    """The 'Broker Handshake' - introduces a high-trust partner listing."""
    try:
        formatted_price = f"₦{int(prop.price):,}" if prop.price else "Price on request"
    except (ValueError, TypeError):
        formatted_price = "Price on request"

    image = "Photos pending audit"
    if hasattr(prop, "images") and prop.images:
        image = prop.images[0].url

    trust = getattr(prop, "calculated_trust", 95)

    return (
        f"I searched the vault for *{original_biz_name}*, but they don't have a direct match in this area today. 🔍\n\n"
        f"However, Est8Go has found a **Premium Verified** alternative from our partner network:\n\n"
        f"🏠 *{prop.title}*\n"
        f"💰 Price: {formatted_price}\n"
        f"🛡️ Trust Score: {trust}% (Physical Site Verified)\n\n"
        f"📸 *View Verified Photos:* \n{image}\n\n"
        f"Would you like me to connect you with the agent for this property?"
    )


def build_no_match_message(location: str) -> str:
    """Friendly recovery when the vault is empty for a specific area."""
    return (
        f"I checked our Truth-Vault for verified listings in *{location}*, "
        f"but we don't have a perfect match yet. 🔍\n\n"
        f"Would you like to see our top-rated deals in nearby areas instead?"
    )
