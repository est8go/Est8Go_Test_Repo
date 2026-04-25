from __future__ import annotations
import json
import logging
from typing import Optional, List

from fastapi import HTTPException
from sqlalchemy.orm import Session

# 1. Domain Models
from app.company_profiles.models import CompanyProfile
from app.conversations.models import Conversation, ConversationMessage
from app.listings.models import Listing

# 2. Brain & Template Helpers
from app.conversations.templates import (
    is_filler,
    get_next_question,
)
from app.conversations.brain import extract_preferences
from app.conversations.ai_fallback import is_company_faq, answer_company_faq

# 3. External Senders
from app.services.meta_sender_service import send_meta_carousel, send_meta_message
from app.services.notification_service import alert_realtor_of_lead

logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# DATABASE SEARCH LOGIC
# ---------------------------------------------------------


def _find_matching_listings(db: Session, tenant_id: int, data: dict) -> List[Listing]:
    """Premium Search: Finds verified properties with flexible pricing."""
    query = db.query(Listing).filter(
        Listing.tenant_id == tenant_id, Listing.status == "verified"
    )

    if data.get("location"):
        # We strip common words like 'abuja' to match the specific district
        loc_search = data["location"].lower().replace("abuja", "").strip()
        query = query.filter(Listing.location.ilike(f"%{loc_search}%"))

    if data.get("property_type"):
        query = query.filter(Listing.property_type.ilike(f"%{data['property_type']}%"))

    if data.get("budget"):
        # 20% flexibility for Nigerian market negotiations
        max_val = int(data["budget"]) * 1.2
        query = query.filter(Listing.price <= max_val)

    return query.limit(5).all()


# ---------------------------------------------------------
# VISUAL CAROUSEL FORMATTER
# ---------------------------------------------------------


def prepare_meta_carousel(listings: List[Listing]) -> List[dict]:
    """Prepares visual cards for Meta horizontal scroll."""
    cards = []
    for item in listings:
        # Use first image or professional real estate placeholder
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
                        "title": "View Full Details 📸",
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
# CONVERSATION START
# ---------------------------------------------------------


def start_conversation_service(
    channel: str,
    external_user_id: str,
    display_name: Optional[str],
    tenant_id: int,
    db: Session,
):
    """Initializes interaction with professional Nigerian vocabulary."""
    profile = (
        db.query(CompanyProfile).filter(CompanyProfile.tenant_id == tenant_id).first()
    )

    convo = Conversation(
        tenant_id=tenant_id,
        channel=channel,
        external_user_id=external_user_id,
        display_name=display_name,
        state="ACTIVE",
        data_json="{}",
    )
    db.add(convo)
    db.commit()
    db.refresh(convo)

    firm_name = profile.company_name if profile else "our firm"
    reply = f"Hi {display_name or ''}, welcome to {firm_name}! 👋\nI am your digital consultant. Are you looking to buy, rent, or invest?"

    db.add(
        ConversationMessage(conversation_id=convo.id, role="assistant", content=reply)
    )
    db.commit()

    return {"conversation_id": convo.id, "reply": reply}


# ---------------------------------------------------------
# MAIN PIPELINE
# ---------------------------------------------------------


def add_message_service(conversation_id: int, text: str, tenant_id: int, db: Session):
    """Handles Fillers, FAQs, PIVOTS, and Preference Extraction."""
    convo = db.query(Conversation).get(conversation_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    text_clean = (text or "").strip()
    db.add(
        ConversationMessage(conversation_id=convo.id, role="user", content=text_clean)
    )

    # 1. ATOMIC RESET
    reset_keywords = ["start again", "new search", "restart", "something else"]
    if any(k in text_clean.lower() for k in reset_keywords):
        convo.data_json = "{}"
        convo.state = "ACTIVE"
        db.commit()
        return {
            "reply": "I've refreshed our search context. 🔄 What type of property are we looking for now?",
            "state": "ACTIVE",
            "prefs": {},
        }

    # 2. FILLER CHECK
    if is_filler(text_clean):
        return {
            "reply": "Understood. Please provide more details about your ideal property.",
            "state": convo.state,
            "prefs": {},
        }

    # 3. FAQ INTERRUPTION
    if is_company_faq(text_clean):
        profile = (
            db.query(CompanyProfile)
            .filter(CompanyProfile.tenant_id == tenant_id)
            .first()
        )
        faq_reply = answer_company_faq(db, tenant_id, text_clean, profile)
        return {
            "reply": f"{faq_reply}\n\nShall we continue with our search? What budget range are you considering?",
            "state": convo.state,
            "prefs": {},
        }

    # 4. PREMIUM AI EXTRACTION
    current_prefs = json.loads(convo.data_json or "{}")
    updated_prefs = extract_preferences(text_clean, current_prefs)
    convo.data_json = json.dumps(updated_prefs)

    # 5. SMART FLOW LOGIC
    if updated_prefs.get("location") and (
        updated_prefs.get("budget") or updated_prefs.get("property_type")
    ):
        db.commit()
        return {
            "reply": "Excellent choice. I am currently reviewing our verified inventory for you...",
            "state": convo.state,
            "prefs": updated_prefs,
            "trigger_search": True,
        }

    next_question = get_next_question(updated_prefs)
    if not next_question:
        convo.state = "HANDOFF"
        next_question = "✅ Splendid. I have documented your requirements. I am now matching you with a verified specialist."

    db.commit()
    return {"reply": next_question, "state": convo.state, "prefs": updated_prefs}


# ---------------------------------------------------------
# META WEBHOOK BRIDGE
# ---------------------------------------------------------


async def handle_incoming_message(data: dict, db: Session):
    """Bridges raw Meta JSON to the High-Performance Pipeline."""
    try:
        # A. Parse Data
        entry = data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return

        msg = messages[0]
        sender_id = msg.get("from")

        # B. Handle Button Interactions
        btn_data = msg.get("button", {}) or msg.get("postback", {})
        payload = btn_data.get("payload", "")

        if "INTERESTED_IN_" in payload:
            listing_id = int(payload.split("_")[-1])
            await alert_realtor_of_lead(db, listing_id, sender_id)
            await send_meta_message(
                sender_id,
                "🤝 Excellent. I've alerted the verified agent for this property.",
            )
            return

        # C. Handle Natural Language Text
        text_body = msg.get("text", {}).get("body", "")
        if not text_body:
            return

        tenant_id = 2

        # 1. Fetch or Initialize Conversation
        convo = (
            db.query(Conversation)
            .filter(
                Conversation.external_user_id == sender_id,
                Conversation.tenant_id == tenant_id,
            )
            .first()
        )

        if not convo:
            res = start_conversation_service("whatsapp", sender_id, None, tenant_id, db)
            convo_id = res["conversation_id"]
        else:
            convo_id = convo.id

        # 2. Run the State Machine
        pipeline_res = add_message_service(convo_id, text_body, tenant_id, db)

        # 3. Decision Logic: Search Result Delivery
        prefs = pipeline_res.get("prefs", {})
        if pipeline_res.get("trigger_search") or (
            prefs.get("location") and prefs.get("property_type")
        ):
            matches = _find_matching_listings(db, tenant_id, prefs)
            if matches:
                carousel_cards = prepare_meta_carousel(matches)
            # 1. Send text summary first (The Backup)
            summary = f"🏠 I found a match: *{matches[0].title}*\n💰 Price: ₦{matches[0].price:,}\n📍 Location: {matches[0].location}\n🔗 View Photos: https://est8go-api.onrender.com/public/property/{matches[0].id}"
            await send_meta_message(sender_id, summary)

            # 2. Try to send the visual cards
            await send_meta_carousel(sender_id, carousel_cards)
            return

        # 4. Standard Response
        await send_meta_message(sender_id, pipeline_res["reply"])

    except Exception as e:
        logger.error(f"❌ PREMIUM BRIDGE ERROR: {e}", exc_info=True)
