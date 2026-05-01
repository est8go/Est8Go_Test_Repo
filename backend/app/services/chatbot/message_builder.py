# EST8GO PREMIUM MESSAGE BUILDER
# Responsible for high-converting property summaries and referral handshakes.


# 🔹 SOCKET: Update build_property_summary in message_builder.py


def build_property_summary(prop, matches: list, first_name: str) -> str:
    """Invites the user to the Web-Gallery."""
    # 1. Create the link containing all matched IDs
    all_ids = ",".join([str(m.id) for m in matches])
    # IMPORTANT: Change this URL to your actual Render URL!
    gallery_link = f"https://est8go-api.onrender.com/public/matches?ids={all_ids}"

    price = f"₦{int(prop.price):,}" if prop.price else "Price on request"

    return (
        f"✨ *Verified Matches Found for {first_name}!* \n\n"
        f"🏠 *Top Pick:* {prop.title}\n"
        f"📍 Location: {prop.location}\n"
        f"💰 Price: {price}\n\n"
        f"🔗 *Tap below to view all {len(matches)} verified options in our Full-Screen Gallery:* \n"
        f"{gallery_link}\n\n"
        f"Which one would you like to visit?"
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
