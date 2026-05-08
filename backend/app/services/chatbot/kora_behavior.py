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
