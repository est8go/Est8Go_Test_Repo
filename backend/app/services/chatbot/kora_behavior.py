from app.conversations.responses import get_response


def determine_bot_voice(
    raw_reply: str, text_body: str, first_name: str, tenant_profile: dict
) -> str:
    """Maps logic flags to the branded persona of the Realtor."""
    biz_name = tenant_profile.get("business_name", "our team")
    areas = tenant_profile.get("areas_covered", "Abuja")
    text_lower = text_body.lower()

    # 1. GREETING (Proactive entry point)
    if any(w in text_lower for w in ["hi", "hello", "hey", "start"]):
        greeting = get_response("greeting", first_name, tenant_profile)
        return f"{greeting}\n\nI currently have verified listings in *{areas}*. Which area are you interested in?"

    # 2. DATA NUDGES (Keeping the flow alive)
    if "location" in raw_reply.lower() or "where" in raw_reply.lower():
        return get_response("nudge_location", first_name, tenant_profile)

    if "budget" in raw_reply.lower() or "price" in raw_reply.lower():
        return get_response("nudge_budget", first_name, tenant_profile)

    # 3. COMPLETION
    if raw_reply == "completed_flag":
        return f"✅ I've captured your preferences! A consultant from *{biz_name}* will contact you shortly."

    # 4. DEFAULT
    return get_response("filler", first_name, tenant_profile)
