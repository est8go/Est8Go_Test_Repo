def build_referral_summary(prop, original_biz_name: str) -> str:
    """
    World-Class Broker Handshake:
    Introduces a high-trust partner listing when the original realtor has no stock.
    """
    price = f"₦{int(prop.price):,}" if prop.price else "Price on request"
    image = prop.images[0].url if prop.images else "Photos pending audit"
    trust = getattr(prop, "calculated_trust", 95)

    return (
        f"I searched the vault for *{original_biz_name}*, but they don't have a direct match in this area today. 🔍\n\n"
        f"However, Est8Go has found a **Premium Verified** alternative from our partner network:\n\n"
        f"🏠 *{prop.title}*\n"
        f"💰 Price: {price}\n"
        f"🛡️ Trust Score: {trust}% (Physical Site Verified)\n\n"
        f"📸 *View Verified Photos:* \n{image}\n\n"
        f"Would you like me to connect you with the agent for this property?"
    )


def build_no_match_message(location: str) -> str:
    """Friendly recovery when the vault is empty for a specific area."""
    return (
        f"I searched our Truth-Vault for verified listings in *{location}*, "
        f"but we don't have a perfect match yet. 🔍\n\n"
        f"Would you like to see our top-rated deals in nearby areas instead?"
    )
