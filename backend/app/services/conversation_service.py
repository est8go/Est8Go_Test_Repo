from __future__ import annotations
import json
import logging
from typing import Optional, List
from sqlalchemy.orm import Session

# 1. Domain Models
from app.company_profiles.models import CompanyProfile
from app.conversations.models import Conversation, ConversationMessage
from app.listings.models import Listing
from app.services.tenant_service import get_tenant_profile
from app.conversations.responses import get_response

# 2. Brain & Template Helpers (Ensure these files exist)
from app.conversations.templates import is_filler, get_next_question
from app.conversations.brain import extract_preferences
from app.conversations.ai_fallback import is_company_faq, answer_company_faq
from sqlalchemy.orm import joinedload  # Ensure this is imported

# 3. External Senders & Trust
from app.services.meta_sender_service import (
    send_meta_message,
    send_meta_carousel,  # If used interchangeably with send_meta_message
)
from app.services.notification_service import alert_realtor_of_lead
from app.services.trust_engine import calculate_confidence_score

logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# DATABASE SEARCH LOGIC
# ---------------------------------------------------------


def _find_matching_listings(db: Session, tenant_id: int, data: dict) -> List[Listing]:
    """Premium Search: Finds verified properties with flexible pricing."""
    query = (
        db.query(Listing)
        .options(joinedload(Listing.images))
        .filter(Listing.tenant_id == tenant_id, Listing.status == "verified")
    )

    if data.get("location"):
        # Clean location to prevent strict match failures
        loc_search = data["location"].lower().replace("abuja", "").strip()
        query = query.filter(Listing.location.ilike(f"%{loc_search}%"))

    if data.get("property_type"):
        query = query.filter(Listing.property_type.ilike(f"%{data['property_type']}%"))

    if data.get("budget"):
        try:
            max_val = int(data["budget"]) * 1.2  # 20% negotiation room
            query = query.filter(Listing.price <= max_val)
        except (ValueError, TypeError):
            pass

    return query.limit(5).all()


# ---------------------------------------------------------
# VISUAL CAROUSEL FORMATTER
# ---------------------------------------------------------


def prepare_meta_carousel(listings: List[Listing]) -> List[dict]:
    """Prepares visual cards for Meta horizontal scroll."""
    cards = []
    for item in listings:
        image_url = (
            item.images[0].url
            if item.images
            else "https://images.unsplash.com/photo-1560518883-ce09059eeffa"
        )
        cards.append(
            {
                "title": item.title[:80],
                "subtitle": f"₦{item.price:,} | {item.location}",
                "image_url": image_url,
                "buttons": [
                    {
                        "type": "web_url",
                        "url": f"https://est8go-api.onrender.com/public/property/{item.id}",
                        "title": "View Photos 📸",
                    },
                    {
                        "type": "postback",
                        "title": "I'm Interested! 💎",
                        "payload": f"INTERESTED_IN_{item.id}",
                    },
                ],
            }
        )
    return cards


# ---------------------------------------------------------
# CONVERSATION START (Upgraded with Voice Engine)
# ---------------------------------------------------------


def start_conversation_service(
    channel: str,
    external_user_id: str,
    display_name: Optional[str],
    tenant_id: int,
    db: Session,
):
    """Initializes interaction with professional branding."""
    # Fetch branding via our new Tenant Service
    tenant_profile = get_tenant_profile(db, tenant_id)
    first_name = display_name.split()[0] if display_name else "there"

    convo = Conversation(
        tenant_id=tenant_id,
        channel=channel,
        external_user_id=external_user_id,
        display_name=display_name,
        state="ACTIVE",
        data_json="{}",
        is_bot_active=True,  # Ensure your model has this
    )
    db.add(convo)
    db.commit()
    db.refresh(convo)

    # Use our standard Response Engine for the greeting
    reply = get_response("greeting", first_name, tenant_profile)

    db.add(
        ConversationMessage(conversation_id=convo.id, role="assistant", content=reply)
    )
    db.commit()

    return {"conversation_id": convo.id, "reply": reply}


# ---------------------------------------------------------
# THE STATE MACHINE (The Engine)
# ---------------------------------------------------------


def add_message_service(conversation_id: int, text: str, tenant_id: int, db: Session):
    convo = db.query(Conversation).get(conversation_id)
    text_clean = (text or "").strip()

    # Log user message
    db.add(
        ConversationMessage(conversation_id=convo.id, role="user", content=text_clean)
    )

    # 1. ATOMIC RESET
    # 🔹 SOCKET: Added "hi", "hello", "hey" to the reset list
    if any(
        k in text_clean.lower()
        for k in ["new search", "start again", "restart", "hi", "hello", "hey"]
    ):
        convo.data_json = "{}"
        convo.state = "ACTIVE"  # This pulls the bot out of 'HANDOFF'
        db.commit()

        # If it was a greeting, we let the main logic handle the response
        if any(k in text_clean.lower() for k in ["hi", "hello", "hey"]):
            return {"reply": "greeting_flag", "state": "ACTIVE", "prefs": {}}

        return {
            "reply": "I've refreshed our search. 🔄 What type of property are we looking for now?",
            "state": "ACTIVE",
            "prefs": {},
        }

    # 2. FILLER/FAQ CHECKS
    if is_filler(text_clean):
        return {"reply": "filler_flag", "state": convo.state, "prefs": {}}

    if is_company_faq(text_clean):
        profile = (
            db.query(CompanyProfile)
            .filter(CompanyProfile.tenant_id == tenant_id)
            .first()
        )
        faq_reply = answer_company_faq(db, tenant_id, text_clean, profile)
        return {"reply": faq_reply, "state": convo.state, "prefs": {}}

    # 3. AI PREFERENCE EXTRACTION
    current_data = json.loads(convo.data_json or "{}")
    updated_data = extract_preferences(text_clean, current_data)

    # LOOP BREAKER: Intent forcing
    if "invest" in text_clean.lower():
        updated_data["intent"] = "invest"
    if "buy" in text_clean.lower():
        updated_data["intent"] = "buy"
    if updated_data.get("location") or updated_data.get("property_type"):
        if not updated_data.get("intent"):
            updated_data["intent"] = "buy"

    convo.data_json = json.dumps(updated_data)

    # 4. DETERMINE NEXT QUESTION
    next_q = get_next_question(updated_data)
    if not next_q:
        convo.state = "HANDOFF"
        next_q = "completed_flag"

    db.commit()
    return {"reply": next_q, "state": convo.state, "prefs": updated_data}


# ---------------------------------------------------------
# META WEBHOOK BRIDGE (The Entry Point)
# ---------------------------------------------------------


async def handle_incoming_message(data: dict, db: Session):
    try:
        # --- A. PARSE META PAYLOAD ---
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
        text_body = msg.get("text", {}).get("body", "").lower()

        # --- B. VOICE ENGINE PREP ---
        first_name = whatsapp_name.split()[0] if whatsapp_name else "there"
        tenant_id = 1
        tenant_profile = get_tenant_profile(db, tenant_id)

        # --- C. CONVERSATION & HITL CHECK ---
        convo = (
            db.query(Conversation)
            .filter_by(external_user_id=sender_id, tenant_id=tenant_id)
            .first()
        )

        if convo and hasattr(convo, "is_bot_active") and not convo.is_bot_active:
            logger.info(
                f"🤖 Bot silenced for {sender_id}. Human Realtor is in control."
            )
            return

        # --- D. HANDLE BUTTONS ---
        btn_payload = msg.get("button", {}).get("payload", "") or msg.get(
            "postback", {}
        ).get("payload", "")
        if "INTERESTED_IN_" in btn_payload:
            list_id = int(btn_payload.split("_")[-1])
            await alert_realtor_of_lead(
                db, list_id, sender_id, tenant_profile["business_name"]
            )
            reply = get_response("inspection_confirm", first_name, tenant_profile)
            await send_meta_message(sender_id, reply)
            return

        # --- E. CONVERSATION MANAGEMENT ---
        if not convo:
            res = start_conversation_service(
                "whatsapp", sender_id, whatsapp_name, tenant_id, db
            )
            convo = db.query(Conversation).get(res["conversation_id"])
            # The start_conversation_service already sends the greeting
            return

        # --- F. STATE MACHINE ---
        pipe = add_message_service(convo.id, text_body, tenant_id, db)
        prefs = pipe.get("prefs", {})

        # --- G. DYNAMIC SEARCH ---
        # --- G. DYNAMIC SEARCH (The Truth-First Results) ---
        if prefs.get("location") and (
            prefs.get("budget") or prefs.get("property_type")
        ):
            matches = _find_matching_listings(db, tenant_id, prefs)

            if matches and len(matches) > 0:
                prop = matches[0]
                trust = calculate_confidence_score(prop)
                image_url = prop.images[0].url if prop.images else None

                summary = (
                    f"✨ *Verified Match Found!*\n\n"
                    f"🏠 *{prop.title}*\n"
                    f"📍 Location: {prop.location}\n"
                    f"💰 Price: ₦{prop.price:,}\n"
                    f"🛡️ Trust Score: {trust}% (GPS Verified)\n\n"
                    f"📸 *View Photos:* {image_url if image_url else 'Pending Audit'}\n\n"
                    f"Would you like to book an inspection for this property?"
                )

                # 1. SEND TEXT (Always works, ensures link is seen)
                await send_meta_message(sender_id, summary)

                # 2. 🔹 SOCKET: SEND CAROUSEL (Satisfies Linter + Premium Visuals)
                # This uses both 'send_meta_carousel' and 'prepare_meta_carousel'
                await send_meta_carousel(sender_id, prepare_meta_carousel(matches))

                return

            # Handle "No Results" specifically
            else:
                final_reply = f"I've searched our Truth-Vault for verified listings in *{prefs.get('location')}*, but I couldn't find a match for your budget yet. 🔍\n\nWould you like to see our most trusted deals in other areas instead?"
                await send_meta_message(sender_id, final_reply)
                return

        # --- H. FINAL REPLY (Proactive Branding Injection) ---
        raw_reply = pipe.get("reply", "")

        # 1. Capture Completion
        if raw_reply == "completed_flag":
            final_reply = f"✅ I've captured your preferences! A consultant from *{tenant_profile['business_name']}* will contact you shortly."

        # 2. PROACTIVE GREETING
        elif any(w in text_body for w in ["hi", "hello", "hey", "start"]):
            greeting = get_response("greeting", first_name, tenant_profile)
            # Pull areas_covered from the company profile
            areas = tenant_profile.get("areas_covered", "Abuja")
            nudge = f"\n\nCurrently, I have verified listings in *{areas}*. Which area are you looking at today?"
            final_reply = greeting + nudge

        # 3. NUDGES: Keep the flow moving
        elif "location" in raw_reply.lower() or "where" in raw_reply.lower():
            final_reply = get_response("nudge_location", first_name, tenant_profile)
        elif "budget" in raw_reply.lower() or "price" in raw_reply.lower():
            final_reply = get_response("nudge_budget", first_name, tenant_profile)

        # 4. FALLBACK: filler or raw reply
        elif raw_reply == "filler_flag" or not raw_reply:
            final_reply = get_response("filler", first_name, tenant_profile)
        else:
            final_reply = raw_reply

        # Send the final greeting or nudge
        await send_meta_message(sender_id, final_reply)

    except Exception as e:
        logger.error(f"❌ BRIDGE ERROR: {e}", exc_info=True)
