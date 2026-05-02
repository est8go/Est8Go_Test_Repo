import logging
import json
from sqlalchemy.orm import Session
from app.listings.models import Listing
from app.services.notification_service import alert_realtor_of_lead
from app.conversations.responses import get_executive_response

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
    build_inspection_confirmation,
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
    text_clean = (text or "").strip().lower()

    # 🔹 SOCKET: Atomic Memory Wipe
    if any(k in text_clean for k in ["new search", "restart", "start again"]):
        convo.data_json = "{}"  # 👈 Clears Katampe, Kabusa, everything.
        convo.state = "ACTIVE"
        db.commit()
        # Returns a specific "Fresh Start" voice
        return {"reply": "fresh_start_flag", "prefs": {}}

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
    """
    EST8GO MASTER ORCHESTRATOR (v2.1.0)
    Surgical Logic: Unified Parser, Double-Tap Greetings, Truth-First Search, and Handshakes.
    """
    try:
        # --- 1. UNIFIED PARSER (WhatsApp, IG, FB) ---
        entry = data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})

        # Security Guard: Ignore Meta status receipts (Read/Delivered)
        if "messages" not in value and "messaging" not in entry:
            return

        sender_id = None
        text_body = ""
        btn_payload = ""
        whatsapp_name = "there"
        channel = "whatsapp"

        # Path A: WhatsApp (Standard)
        if "messages" in value:
            msg_obj = value["messages"][0]
            sender_id = msg_obj.get("from")
            text_body = msg_obj.get("text", {}).get("body", "")
            btn_payload = msg_obj.get("button", {}).get("payload", "") or msg_obj.get(
                "interactive", {}
            ).get("button_reply", {}).get("id", "")
            contacts = value.get("contacts", [])
            if contacts:
                whatsapp_name = contacts[0].get("profile", {}).get("name", "there")

        # Path B: Instagram / Messenger
        elif "messaging" in entry:
            msg_event = entry["messaging"][0]
            sender_id = msg_event.get("sender", {}).get("id")
            text_body = msg_event.get("message", {}).get("text", "")
            channel = "instagram" if "instagram" in str(data).lower() else "facebook"

        if not sender_id:
            return

        # --- 2. IDENTITY & CONTEXT (Defined ONCE) ---
        tenant_id = 1
        tenant_profile = get_tenant_profile(db, tenant_id)
        first_name = whatsapp_name.split()[0] if whatsapp_name else "there"

        convo = (
            db.query(Conversation)
            .filter_by(external_user_id=sender_id, tenant_id=tenant_id)
            .first()
        )

        # --- 3. HUMAN-IN-THE-LOOP (HITL) CHECK ---
        if convo and hasattr(convo, "is_bot_active") and not convo.is_bot_active:
            return

        # --- 4. BUTTON HANDLER (Immediate Priority) ---
        if btn_payload and "INTERESTED_IN_" in btn_payload:
            list_id = int(btn_payload.split("_")[-1])
            listing = db.get(Listing, list_id)
            if listing:
                # Premium Flash Confirmation
                await send_meta_message(
                    sender_id,
                    f"✅ *Interest Verified, {first_name}* \n\nI am establishing a direct satellite link to the site for you... 🛰️",
                )
                # Deliver Google Maps Navigation
                nav_msg = build_inspection_confirmation(
                    first_name, listing.title, listing.latitude, listing.longitude
                )
                await send_meta_message(sender_id, nav_msg)
                # Revenue Alert to Realtor
                await alert_realtor_of_lead(
                    db, list_id, sender_id, tenant_profile["business_name"]
                )
                return

        # --- 5. THE EXECUTIVE SALES FUNNEL (Double-Tap & Persistence) ---
        is_greeting = any(
            w in text_body.lower() for w in ["hi", "hello", "hey", "start", "greetings"]
        )
        if is_greeting:
            # A. Check for Existing Session
            if convo and convo.data_json and convo.data_json != "{}":
                resume_prompt = get_executive_response(
                    "resume_prompt", first_name, tenant_profile["business_name"]
                )
                await send_meta_message(sender_id, resume_prompt)
                return

            # B. New User Setup
            if not convo:
                res = start_conversation_service(
                    channel, sender_id, whatsapp_name, tenant_id, db
                )
                convo_id = res["conversation_id"]
                convo = db.get(Conversation, convo_id)

            # C. The Double-Tap Greeting
            intro = get_executive_response(
                "intro", first_name, tenant_profile["business_name"]
            )
            await send_meta_message(sender_id, intro)

            areas = tenant_profile.get("areas_covered", "Abuja")
            emoji = tenant_profile.get("emoji", "🏠")
            question = get_executive_response(
                "intent_location", first_name, tenant_profile["business_name"]
            )
            await send_meta_message(
                sender_id,
                f"I am currently monitoring verified deals in **{areas}** {emoji}. {question}",
            )

            # Reset memory for fresh start
            convo.state = "ACTIVE"
            convo.data_json = "{}"
            db.commit()
            return

            # --- 6. DATA EXTRACTION & SEARCH (The Hunter) ---
        pipe = add_message_service(convo.id, text_body, tenant_id, db)
        prefs = pipe.get("prefs", {})

        if prefs.get("location") and prefs.get("budget"):
            try:
                search_result = execute_premium_search(db, tenant_id, prefs)
                matches = search_result.get("data", [])
                total = search_result.get("total_count", 0)
                source = search_result.get("source", "none")  # Check if it's a partner

                if matches:
                    # 🔹 SOCKET: Use build_referral_summary for partner listings
                    if source == "referral":
                        summary = build_referral_summary(
                            matches[0], tenant_profile.get("business_name", "our firm")
                        )
                    else:
                        summary = build_property_summary(
                            matches[0], matches, total, first_name
                        )

                    # 1. Send text summary
                    await send_meta_message(sender_id, summary)

                    # 2. 🔹 SOCKET: Send visual carousel (Satisfies linter)
                    carousel_data = prepare_meta_carousel(matches)
                    await send_meta_carousel(sender_id, carousel_data)
                    return
                else:
                    await send_meta_message(
                        sender_id, build_no_match_message(prefs.get("location"))
                    )
                    return
            except Exception as e:
                logger.error(f"Search Block Failure: {e}")
                await send_meta_message(sender_id, handle_logic_error("search_failure"))
                return

        # --- 7. FINAL RESPONSE (Kora Personality & Handshakes) ---
        try:
            raw_reply = pipe.get("reply", "")
            final_reply = determine_bot_voice(
                raw_reply, text_body, first_name, tenant_profile
            )

            # Handle the 'Yes' Handover or Global Search Trigger
            if final_reply == "trigger_global_search":
                search_result = execute_premium_search(
                    db, tenant_id, {"location": "Abuja"}
                )
                matches = search_result.get("data", [])
                if matches:
                    summary = f"I've pulled our Top {len(matches)} most trusted deals in Abuja for you, {first_name}. 🔄\n\n"
                    summary += build_property_summary(
                        matches[0],
                        matches,
                        search_result.get("total_count"),
                        first_name,
                    )

                    await send_meta_message(sender_id, summary)

                    # 🔹 SOCKET: Trigger carousel for global deals
                    await send_meta_carousel(sender_id, prepare_meta_carousel(matches))
                    return

            if final_reply == "handshake_flag":
                last_id = prefs.get("last_viewed_id")
                listing = db.get(Listing, last_id) if last_id else None
                if listing:
                    connection_msg = build_inspection_confirmation(
                        first_name, listing.title, listing.latitude, listing.longitude
                    )
                    await send_meta_message(sender_id, connection_msg)
                    await alert_realtor_of_lead(
                        db, last_id, sender_id, listing.tenant.name
                    )
                    return

            # Default Voice Delivery
            await send_meta_message(sender_id, final_reply)

        except Exception as e:
            logger.error(f"❌ PERSONALITY ERROR: {e}")
            await send_meta_message(
                sender_id,
                "I'm still here! I had a small glitch, could you please say that again? 🙏",
            )

    except Exception as e:
        logger.error(f"❌ CRITICAL MASTER ERROR: {e}", exc_info=True)
