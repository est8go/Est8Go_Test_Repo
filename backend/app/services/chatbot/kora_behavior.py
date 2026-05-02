from app.conversations.responses import get_executive_response


def determine_bot_voice(
    raw_reply: str, text_body: str, first_name: str, tenant_profile: dict
) -> str:
    """
    World-Class Persona Controller:
    Maps logic flags to executive, branded, and proactive responses.
    """

    # 1. INITIALIZE IDENTITY & CONTEXT
    text_lower = (text_body or "").lower().strip()
    biz_name = tenant_profile.get("business_name", "our firm")
    areas = tenant_profile.get("areas_covered", "Abuja")  # 🔹 Now used in Step 3 & 4
    emoji = tenant_profile.get("emoji", "🏠")

    # 2. THE AGGRESSIVE HANDSHAKE (Agent Connection)
    if any(
        w in text_lower
        for w in ["yes", "connect", "interested", "sure", "ok", "visit", "schedule"]
    ):
        return "handshake_flag"

    # 3. RESUME VS START FRESH LOGIC
    if raw_reply == "resume_flag":
        return get_executive_response("resume_prompt", first_name, biz_name)

    if raw_reply == "fresh_start_flag":
        # 🔹 AREAS USED HERE: Proves local expertise
        intro = f"I've reset our vault connection, {first_name}. 🔄 I am monitoring verified deals across **{areas}**."
        question = get_executive_response("intent_location", first_name, biz_name)
        return f"{intro}\n\n{question}"

    # 4. PROACTIVE GREETING (The Double-Tap identity)
    if any(w in text_lower for w in ["hi", "hello", "hey", "start"]):
        intro = get_executive_response("intro", first_name, biz_name)
        question = get_executive_response("intent_location", first_name, biz_name)
        # 🔹 AREAS & EMOJI USED HERE:
        return f"{intro} {emoji}\n\nI currently have verified listings in **{areas}**. {question}"

    # 5. THE REVENUE GATE: BUDGET NUDGE
    if (
        "budget" in raw_reply.lower()
        or "price" in raw_reply.lower()
        or raw_reply == "ask_budget_flag"
    ):
        return get_executive_response("budget_nudge", first_name, biz_name)

    # 6. GLOBAL SEARCH TRIGGER (Agreement to see more)
    if raw_reply == "trigger_global_search":
        return "trigger_global_search"

    # 7. EXECUTIVE FALLBACK (Smarter Filler)
    return get_executive_response("filler", first_name, biz_name)
