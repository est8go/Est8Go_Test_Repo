import logging
import json
from sqlalchemy.orm import Session

# 1. DOMAIN & INFRASTRUCTURE
# Removed 'ConversationMessage'
from app.conversations.models import Conversation
from app.services.tenant_service import get_tenant_profile
from app.services.meta_sender_service import (
    send_meta_message,
    send_meta_carousel,
    prepare_meta_carousel,
)

# 2. LOGIC ENGINES (Existing Brain & Templates)
from app.conversations.templates import is_filler, get_next_question
from app.conversations.brain import extract_preferences

# 🔹 SOCKET: Added back is_company_faq and CompanyProfile
from app.conversations.ai_fallback import is_company_faq, answer_company_faq
from app.company_profiles.models import CompanyProfile

# 3. 🔹 THE NEW PREMIUM SOCKETS
from app.services.chatbot.search_service import execute_premium_search
from app.services.chatbot.message_builder import (
    build_property_summary,
    build_no_match_message,
    build_referral_summary,
)
from app.services.chatbot.kora_behavior import determine_bot_voice
from app.services.chatbot.fallback_engine import handle_logic_error

logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# CONVERSATION START
# ---------------------------------------------------------


def start_conversation_service(
    channel: str, uid: str, name: str, t_id: int, db: Session
):
    """Initializes interaction using the branded voice engine."""
    tenant_profile = get_tenant_profile(db, t_id)
    first_name = name.split()[0] if name else "there"

    convo = Conversation(
        tenant_id=t_id,
        channel=channel,
        external_user_id=uid,
        display_name=name,
        state="ACTIVE",
        data_json="{}",
    )
    db.add(convo)
    db.commit()
    db.refresh(convo)

    # Use Kora to generate the initial greeting
    greeting = determine_bot_voice("start", "hi", first_name, tenant_profile)
    return {"conversation_id": convo.id, "reply": greeting}


# ---------------------------------------------------------
# THE STATE MACHINE
# ---------------------------------------------------------


def add_message_service(conversation_id: int, text: str, tenant_id: int, db: Session):
    convo = db.query(Conversation).get(conversation_id)
    text_clean = (text or "").strip()

    # Reset Logic: Breaks the 'Handoff' loop and clears memory
    if any(k in text_clean.lower() for k in ["new search", "restart", "hi", "hello"]):
        convo.data_json = "{}"
        convo.state = "ACTIVE"
        db.commit()
        if "new search" in text_clean.lower():
            return {
                "reply": "I've refreshed our search. 🔄 What area are we looking in now?",
                "prefs": {},
            }
        return {"reply": "greeting_flag", "prefs": {}}

    if is_filler(text_clean):
        return {"reply": "filler_flag", "prefs": {}}

    # 3. FAQ CHECK (Rules-First: Answer company questions without AI)
    if is_company_faq(text_clean):
        profile = (
            db.query(CompanyProfile)
            .filter(CompanyProfile.tenant_id == tenant_id)
            .first()
        )
        # This line uses 'answer_company_faq', clearing the linter error
        faq_reply = answer_company_faq(db, tenant_id, text_clean, profile)
        return {"reply": faq_reply, "prefs": {}}

    # Extract Data via AI Brain
    current_data = json.loads(convo.data_json or "{}")
    updated_data = extract_preferences(text_clean, current_data)

    convo.data_json = json.dumps(updated_data)
    next_q = get_next_question(updated_data)

    if not next_q:
        convo.state = "HANDOFF"
        next_q = "completed_flag"

    db.commit()
    return {"reply": next_q, "prefs": updated_data}


# ---------------------------------------------------------
# META WEBHOOK BRIDGE (The Orchestrator)
# ---------------------------------------------------------


async def handle_incoming_message(data: dict, db: Session):
    try:
        # --- A. PARSE INCOMING ---
        entry = data.get("entry", [{}])[0]
        value = entry.get("changes", [{}])[0].get("value", {})
        contacts = value.get("contacts", [])
        whatsapp_name = (
            contacts[0].get("profile", {}).get("name", "there") if contacts else "there"
        )
        messages = value.get("messages", [])
        if not messages:
            return

        msg = messages[0]
        sender_id = msg.get("from")
        text_body = msg.get("text", {}).get("body", "")
        tenant_id = 1  # Update to be dynamic in production

        tenant_profile = get_tenant_profile(db, tenant_id)
        first_name = whatsapp_name.split()[0] if whatsapp_name else "there"

        # --- B. HITL & GREETING GUARD (Top Priority) ---
        convo = (
            db.query(Conversation)
            .filter_by(external_user_id=sender_id, tenant_id=tenant_id)
            .first()
        )
        if convo and hasattr(convo, "is_bot_active") and not convo.is_bot_active:
            return

        # 🔹 SOCKET: Reset and Greet immediately if it's a 'Hi'
        if any(w in text_body.lower() for w in ["hi", "hello", "hey", "start"]):
            res = start_conversation_service(
                "whatsapp", sender_id, whatsapp_name, tenant_id, db
            )
            await send_meta_message(sender_id, res["reply"])
            return

        # --- C. RUN LOGIC ENGINE ---
        pipe = add_message_service(convo.id, text_body, tenant_id, db)
        prefs = pipe.get("prefs", {})

        # --- D. THE HUNTER: Execute Search ---

        # --- D. THE HUNTER: Execute Network-Aware Search ---
        if prefs.get("location") and (
            prefs.get("budget") or prefs.get("property_type")
        ):
            try:
                # Execute the Premium Search (returns source and data)
                search_result = execute_premium_search(db, tenant_id, prefs)
                matches = search_result.get("data", [])
                source = search_result.get("source", "none")

                if matches:
                    # THE ARCHITECT: Build Visuals based on the Source
                    if source == "referral":
                        # 🔹 Handshake Logic: Kora refers a partner's property
                        summary = build_referral_summary(
                            matches[0],
                            tenant_profile.get("business_name", "this agency"),
                        )
                    else:
                        # Standard direct match
                        summary = build_property_summary(matches[0], first_name)

                    # 1. Send the text summary (The Truth Data)
                    await send_meta_message(sender_id, summary)

                    # 2. Send the Visual Carousel (The Emotional Hook)
                    carousel_payload = prepare_meta_carousel(matches)
                    if carousel_payload:
                        await send_meta_carousel(sender_id, carousel_payload)
                    return

                else:
                    # 🔄 NO MATCHES — Suggest nearby or network deals
                    await send_meta_message(
                        sender_id, build_no_match_message(prefs.get("location"))
                    )
                    return

            except Exception as e:
                logger.error(f"❌ SEARCH BLOCK FAILURE: {e}", exc_info=True)
                await send_meta_message(sender_id, handle_logic_error("search_failure"))
                return

        # --- E. THE PERSONALITY: Branded Response ---
        final_reply = determine_bot_voice(
            pipe.get("reply", ""), text_body, first_name, tenant_profile
        )
        await send_meta_message(sender_id, final_reply)

    except Exception as e:
        logger.error(f"❌ ORCHESTRATOR ERROR: {e}", exc_info=True)
