# backend/app/services/chatbot/kora_behavior.py

from app.conversations.responses import get_response


def determine_bot_voice(
    raw_reply: str, text_body: str, first_name: str, tenant_profile: dict
) -> str:
    """
    World-Class Persona Controller:
    Maps logic flags to branded, proactive responses.
    """

    # 1. INITIALIZE IDENTITY (Prevents 'areas' undefined error)
    text_lower = (text_body or "").lower().strip()
    biz_name = tenant_profile.get("business_name", "our team")
    areas = tenant_profile.get("areas_covered", "Abuja")

    # 2. Smart Handshake Logic
    if text_lower in [
        "yes",
        "yes please",
        "inspect",
        "let's go",
        "i want to visit",
        "sure",
        "Alright",
        "show me",
        "connect me",
    ]:
        last_id = tenant_profile.get("last_viewed_id")  # We'll pass this in

        if last_id:
            return "handshake_flag"  # Tell the controller to send agent details

        return "trigger_global_search"

    # 3. PROACTIVE GREETING
    # This uses 'get_response', satisfying the linter
    if any(w in text_lower for w in ["hi", "hello", "hey", "start"]):
        greeting = get_response("greeting", first_name, tenant_profile)
        return f"{greeting}\n\nI currently have verified listings in *{areas}*. Which area are you interested in?"

    if raw_reply == "fresh_start_flag":
        return f"I've cleared our previous search, {first_name}. 🔄 What area or property type should we look for now?"

    # 4. COMPLETION FLAG
    if raw_reply == "completed_flag":
        return f"✅ I've captured your preferences! A consultant from *{biz_name}* will contact you shortly."

    # 5. CONTEXT-AWARE NUDGES
    # 🔹 SOCKET 2: PROACTIVE GUIDANCE
    if "location" in raw_reply.lower() or "where" in raw_reply.lower():
        return f"Nice! 👍 I'm currently monitoring high trust deals in *{areas}*. Which of these areas should we look into first?"

    if "budget" in raw_reply.lower() or "price" in raw_reply.lower():
        return f"Got the location! {first_name}, to filter the best verified options, what's our budget range? (e.g., '10m to 50m' or 'Under 100m')"

    if "property_type" in raw_reply.lower() or "what kind" in raw_reply.lower():
        # 🔹 FIX: Removed unnecessary f-prefix
        return "Understood. Are we looking for a Plot of Land for development, or a Completed House/Apartment?"
    # 6. FINAL FALLBACK (Smarter Logic to prevent dead-ends)
    # If the logic flag is 'filler' but the user mentioned a known area, nudge for the type
    if raw_reply in ["filler_flag", ""] or not raw_reply:
        if any(
            loc in text_lower for loc in ["maitama", "kabusa", "asokoro", "gwarinpa"]
        ):
            return f"I've noted the location, {first_name}! 👍 Are you looking for a Plot of Land or a Completed House there?"

    return get_response("filler", first_name, tenant_profile)
