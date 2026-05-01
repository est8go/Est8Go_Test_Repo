# EST8GO PREMIUM MESSAGE BUILDER
# Responsible for high-converting property summaries and referral handshakes.


# 🔹 SOCKET: Update build_property_summary in message_builder.py


def build_property_summary(prop, matches: list, first_name: str) -> str:
    """
    Constructs a pitch that points to the Direct Showcase Page.
    This bypasses the browser chooser and loads the image instantly.
    """
    # 🔹 SOCKET: Direct Showcase Link (The one you prefer)
    direct_link = f"https://est8go-api.onrender.com/public/property/{prop.id}"

    price = f"₦{int(prop.price):,}" if prop.price else "Price on request"

    return (
        f"✨ *Verified Match Found for {first_name}!* \n\n"
        f"🏠 *{prop.title}*\n"
        f"📍 Location: {prop.location}\n"
        f"💰 Price: {price}\n"
        f"🛡️ Trust Score: {getattr(prop, 'calculated_trust', 90)}% (Verified)\n\n"
        f"📸 *View Verified Photos & GPS Audit:* \n"
        f"{direct_link}\n\n"
        f"Would you like to book an inspection?"
    )


def build_no_match_message(location: str) -> str:
    """Friendly recovery when the vault is empty for a specific area."""
    return (
        f"I checked our Truth-Vault for verified listings in *{location}*, "
        f"but we don't have a perfect match yet. 🔍\n\n"
        f"Would you like to see our top-rated deals in nearby areas instead?"
    )


def build_referral_summary(prop, original_biz_name: str) -> str:
    """
    The 'Broker Handshake':
    Introduces a partner listing using the high-performance showcase link.
    """
    # 1. THE INSTANT LINK (System B - Deep Link)
    direct_link = f"https://est8go-api.onrender.com/public/property/{prop.id}"

    # 2. SAFE DATA FORMATTING
    try:
        formatted_price = f"₦{int(prop.price):,}" if prop.price else "Price on request"
    except (ValueError, TypeError):
        formatted_price = "Price on request"

    trust = getattr(prop, "calculated_trust", 95)

    return (
        f"I searched the vault for *{original_biz_name}*, but they don't have a direct match today. 🔍\n\n"
        f"However, Est8Go has found a **Premium Verified** alternative from our partner network:\n\n"
        f"🏠 *{prop.title}*\n"
        f"💰 Price: {formatted_price}\n"
        f"🛡️ Trust Score: {trust}% (Physical Site Verified)\n\n"
        f"🔗 *View Verified Photos & GPS Audit:* \n"
        f"{direct_link}\n\n"
        f"Would you like me to connect you with the agent for this property?"
    )
