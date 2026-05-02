import logging
import json
from sqlalchemy.orm import Session
from app.listings.models import Listing
from app.services.notification_service import alert_realtor_of_lead

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
        # 🔹 1. LOG THE PAYLOAD (Surgical Diagnostic)
        # This lets you see exactly what Meta sends in your Render logs
        logger.info(f"Incoming Meta Payload: {data}")

        entry = data.get("entry", [{}])[0]

        # 🔹 2. BULLETPROOF SENDER EXTRACTION
        sender_id = None
        text_body = ""
        whatsapp_name = "Prospect"
        channel = "whatsapp"  # Default

        # Path A: Messenger / Instagram (messaging list)
        if "messaging" in entry:
            messaging_event = entry["messaging"][0]
            sender_id = messaging_event.get("sender", {}).get("id")
            text_body = messaging_event.get("message", {}).get("text", "")
            channel = "instagram" if "instagram" in str(data).lower() else "facebook"

        # Path B: WhatsApp (changes list)
        elif "changes" in entry:
            value = entry["changes"][0].get("value", {})

            # Extract Name
            contacts = value.get("contacts", [])
            if contacts:
                whatsapp_name = contacts[0].get("profile", {}).get("name", "there")

            # Extract Phone and Message
            messages = value.get("messages", [])
            if messages:
                msg = messages[0]
                sender_id = msg.get("from")  # This is the phone number
                text_body = msg.get("text", {}).get("body", "")

        # 🔹 3. THE CRITICAL GUARD
        if not sender_id:
            logger.error("❌ PARSER ERROR: Could not find sender_id in Meta payload.")
            return

        # --- REST OF YOUR LOGIC (Identity, HITL, Search) ---
        tenant_id = 1
        tenant_profile = get_tenant_profile(db, tenant_id)
        first_name = whatsapp_name.split()[0] if whatsapp_name else "there"

        # --- B. HITL & GREETING GUARD ---
        convo = (
            db.query(Conversation)
            .filter_by(external_user_id=sender_id, tenant_id=tenant_id)
            .first()
        )

        if convo and hasattr(convo, "is_bot_active") and not convo.is_bot_active:
            return

        # Trigger Reset and Greeting if 'Hi' or new user
        if not convo or any(
            w in text_body.lower() for w in ["hi", "hello", "hey", "start"]
        ):
            # 🔹 We pass 'channel' here, satisfying the 'not accessed' warning
            res = start_conversation_service(
                channel, sender_id, whatsapp_name, tenant_id, db
            )
            await send_meta_message(sender_id, res["reply"])
            return

        # --- C. RUN LOGIC ENGINE (State Machine) ---
        pipe = add_message_service(convo.id, text_body, tenant_id, db)
        prefs = pipe.get("prefs", {})

        # --- D. THE HUNTER: Execute Network-Aware Search ---
        if prefs.get("location") and (
            prefs.get("budget") or prefs.get("property_type")
        ):
            try:
                # 1. Execute Search (Returns source, data, and total_count)
                search_result = execute_premium_search(db, tenant_id, prefs)
                matches = search_result.get("data", [])
                total = search_result.get("total_count", 0)
                source = search_result.get("source", "none")

                if matches:
                    # 2. THE ARCHITECT: Build Visuals based on the Source
                    if source == "referral":
                        # Handshake logic for partner listings
                        summary = build_referral_summary(
                            matches[0],
                            tenant_profile.get("business_name", "this agency"),
                        )
                    else:
                        # Standard direct match with Boutique count
                        summary = build_property_summary(
                            matches[0], matches, total, first_name
                        )

                    # 3. DISPATCH: Send results to WhatsApp
                    await send_meta_message(sender_id, summary)
                    await send_meta_carousel(sender_id, prepare_meta_carousel(matches))
                    return

                else:
                    # 4. RECOVERY: No matches found
                    await send_meta_message(
                        sender_id, build_no_match_message(prefs.get("location"))
                    )
                    return

            except Exception as e:
                logger.error(f"❌ SEARCH BLOCK FAILURE: {e}", exc_info=True)
                await send_meta_message(sender_id, handle_logic_error("search_failure"))
                return

        # --- E. THE PERSONALITY (Branded Response & Handshake) ---
        try:
            raw_reply = pipe.get("reply", "")
            # We use determine_bot_voice to get the branded content or 'handshake_flag'
            final_reply = determine_bot_voice(
                raw_reply, text_body, first_name, tenant_profile
            )

            # 🔹 HANDSHAKE LOGIC: Handles the connection to the Agent
            if final_reply == "handshake_flag":
                last_id = prefs.get("last_viewed_id")
                # Legacy check: Use db.get(Listing, id) for SQLAlchemy 2.0
                listing = db.get(Listing, last_id) if last_id else None

                if listing and listing.tenant:
                    realtor_name = listing.tenant.name
                    connection_msg = (
                        f"Excellent choice, {first_name}! 🤝\n\n"
                        f"I've notified the team at *{realtor_name}*. You can reach them directly here:\n\n"
                        f"📱 *Realtor:* {realtor_name}\n\n"
                        f"Shall I schedule a physical site inspection for you?"
                    )
                    await send_meta_message(sender_id, connection_msg)

                    # 💰 THE REVENUE TRIGGER: Alert the Realtor of the lead
                    await alert_realtor_of_lead(db, last_id, sender_id, realtor_name)
                    return  # Stop here; handshake complete

            # 📢 FINAL FALLBACK: Send the standard branded reply
            await send_meta_message(sender_id, final_reply)

        except Exception as e:
            # 🔹 THIS IS THE 'EXCEPT' CLAUSE THAT FIXES YOUR ERROR
            logger.error(f"❌ PERSONALITY BLOCK FAILURE: {e}", exc_info=True)
            await send_meta_message(
                sender_id,
                "I'm still here! I had a small glitch, could you please say that again? 🙏",
            )

    except Exception as e:
        # This catches errors in the outer bridge (parsing, etc.)
        logger.error(f"❌ BRIDGE ERROR: {e}", exc_info=True)
