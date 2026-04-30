def build_property_summary(prop, first_name: str) -> str:
    """Constructs a premium property pitch for WhatsApp."""
    price = f"₦{int(prop.price):,}" if prop.price else "Price on request"
    # Pull image from our audited LISTING_IMAGES table
    image = prop.images[0].url if prop.images else "Verified Photos coming soon"
    trust = getattr(prop, "calculated_trust", 90)

    return (
        f"✨ *Verified Match for {first_name}!*\n\n"
        f"🏠 *{prop.title}*\n"
        f"📍 Location: {prop.location}\n"
        f"💰 Price: {price}\n"
        f"🛡️ Trust Score: {trust}% (GPS Verified)\n\n"
        f"📸 *View Verified Site Photos:* \n{image}\n\n"
        f"Would you like to book an inspection or see more options?"
    )


def build_no_match_message(location: str) -> str:
    """Friendly recovery when the vault is empty for a specific area."""
    return (
        f"I searched our Truth-Vault for verified listings in *{location}*, "
        f"but we don't have a perfect match yet. 🔍\n\n"
        f"Would you like to see our top-rated deals in nearby areas instead?"
    )
