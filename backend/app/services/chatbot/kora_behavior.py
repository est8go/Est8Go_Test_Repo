"""
EST8GO KORA BEHAVIOR ENGINE (v2.0)
====================================
Persona Controller — maps pipeline flags to executive responses.

v2.0 Changes:
    - Removed "interested", "ok", "sure", "visit" from handshake triggers
      (these words appear in normal property queries)
    - Budget nudge fixed — no longer intercepts budget responses
    - Funnel-aware — respects state from conversation_service
    - Falls through cleanly when intent filter has already handled the message
"""

from app.conversations.responses import get_executive_response


def get_conversational_opener(first_name: str, biz_name: str, areas: str) -> str:
    import random
    variants = [
        (
            f"Welcome to *{biz_name}*, {first_name}! 🏡\n\n"
            f"You've just connected to one of {areas}'s most trusted verified property networks.\n\n"
            f"Before I open our vault — quick question:\n\n"
            f"Are you buying for *yourself to live in*, or is this an *investment*?"
        ),
        (
            f"Hello {first_name}! Great to have you here. 🤝\n\n"
            f"At *{biz_name}* every property is GPS-verified and document-checked before it reaches you. "
            f"No fake listings. No surprises.\n\n"
            f"To find your perfect match — are you searching for a *personal home* or an *investment property*?"
        ),
        (
            f"Hi {first_name}! Welcome to *{biz_name}*. 🏠\n\n"
            f"I'm Kora — your personal property guide. I only show you verified deals that have been "
            f"physically inspected and document-checked.\n\n"
            f"Quick question to get started:\n\n"
            f"Are you buying to *live in* or as an *investment*?"
        ),
    ]
    return random.choice(variants)


def get_investment_followup(first_name: str) -> str:
    return (
        f"Smart move, {first_name}. 📈\n\n"
        f"Verified properties consistently outperform unverified ones — buyers pay premium for certainty.\n\n"
        f"Are you buying to *rent out* for monthly income, or to *resell* for capital appreciation?"
    )


def get_personal_followup(first_name: str) -> str:
    return (
        f"Wonderful, {first_name}. 🏡\n\n"
        f"Finding a home you'll love is personal — I take that seriously.\n\n"
        f"What type of property are you looking for?\n\n"
        f"🌱 *Land* — build your dream home\n"
        f"🏠 *House* — move-in ready\n"
        f"🏢 *Apartment* — modern city living"
    )


def determine_bot_voice(
    raw_reply: str,
    text_body: str,
    first_name: str,
    tenant_profile: dict,
) -> str:
    """
    Maps pipeline flags to branded Kora responses.
    Only called AFTER intent filter and state machine have run.
    """
    text_lower = (text_body or "").lower().strip()
    biz_name = tenant_profile.get("business_name", "our firm")
    areas = tenant_profile.get("areas_covered", "Abuja")
    emoji = tenant_profile.get("emoji", "🏠")

    # ── 1. EXPLICIT HANDSHAKE TRIGGER ─────────────────────
    # Only very clear agreement signals — no ambiguous words
    if raw_reply == "handshake_flag":
        return "handshake_flag"

    # ── 1b. OPENER FLAGS ──────────────────────────────────
    if raw_reply == "opener_flag":
        return get_conversational_opener(first_name, biz_name, areas)

    if raw_reply == "investment_followup_flag":
        return get_investment_followup(first_name)

    if raw_reply == "personal_followup_flag":
        return get_personal_followup(first_name)

    # ── 2. FRESH START ────────────────────────────────────
    if raw_reply == "fresh_start_flag":
        intro = f"I've reset our vault connection, {first_name}. 🔄 I am monitoring verified deals across *{areas}*."
        question = get_executive_response("intent_location", first_name, biz_name)
        return f"{intro}\n\n{question}"

    # ── 3. RESUME PROMPT ──────────────────────────────────
    if raw_reply == "resume_flag":
        return get_executive_response("resume_prompt", first_name, biz_name)

    # ── 4. GLOBAL SEARCH TRIGGER ──────────────────────────
    if raw_reply == "trigger_global_search":
        return "trigger_global_search"

    # ── 5. COMPLETED FLAG (search should fire) ────────────
    # Let conversation_service handle this — don't intercept
    if raw_reply == "completed_flag":
        return "completed_flag"

    # ── 6. FILLER FLAG ────────────────────────────────────
    if raw_reply == "filler_flag":
        return get_executive_response("filler", first_name, biz_name)

    # ── 7. PASS THROUGH QUESTION FROM TEMPLATES ───────────
    # If raw_reply is already a proper question from get_next_question,
    # return it directly without modification
    if raw_reply and len(raw_reply) > 10 and "?" in raw_reply:
        return raw_reply

    if raw_reply and len(raw_reply) > 20:
        return raw_reply

    # ── 8. EXECUTIVE FALLBACK ─────────────────────────────
    # Only fires if nothing else matched
    return get_executive_response("filler", first_name, biz_name)
