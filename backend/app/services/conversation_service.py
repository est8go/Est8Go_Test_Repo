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

# (calculate_typing_ms and format_listings_text are removed)
from app.conversations.brain import extract_preferences
from app.conversations.ai_fallback import is_company_faq, answer_company_faq

# 3. External Senders
from app.services.meta_sender_service import send_meta_carousel, send_meta_message
from app.services.notification_service import alert_realtor_of_lead

logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# DATABASE SEARCH LOGIC (The Property Engine)
# ---------------------------------------------------------


def _find_matching_listings(db: Session, tenant_id: int, data: dict) -> List[Listing]:
    """Premium Search: Shows matches even if only one detail is provided."""
    query = db.query(Listing).filter(
        Listing.tenant_id == tenant_id, Listing.status == "verified"
    )

    # If they mentioned a location, filter strictly
    if data.get("location"):
        query = query.filter(Listing.location.ilike(f"%{data['location']}%"))

    # If they mentioned a property type, filter strictly
    if data.get("property_type"):
        query = query.filter(Listing.property_type.ilike(f"%{data['property_type']}%"))

    # Budget is flexible (+20% room)
    if data.get("budget"):
        max_val = int(data["budget"]) * 1.2
        query = query.filter(Listing.price <= max_val)

    return query.order_by(Listing.price.desc()).limit(5).all()


# ---------------------------------------------------------
# VISUAL FORMATTING
# ---------------------------------------------------------


def prepare_meta_carousel(listings: List[Listing]) -> List[dict]:
    """Prepares the horizontal scrolling carousel cards."""
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
                        "url": f"http://127.0.0.1:8000/public/property/{item.id}",
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
# CORE PIPELINE SERVICES
# ---------------------------------------------------------


def start_conversation_service(
    channel: str,
    external_user_id: str,
    display_name: Optional[str],
    tenant_id: int,
    db: Session,
):
    """Initializes a new customer interaction."""
    profile = (
        db.query(CompanyProfile).filter(CompanyProfile.tenant_id == tenant_id).first()
    )
    convo = (
        db.query(Conversation)
        .filter(
            Conversation.tenant_id == tenant_id,
            Conversation.external_user_id == external_user_id,
        )
        .first()
    )

    if not convo:
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

    welcome = f"Hi {display_name or ''}, welcome to {profile.company_name if profile else 'our firm'}! 👋\nAre you looking to buy or rent?"
    db.add(
        ConversationMessage(conversation_id=convo.id, role="assistant", content=welcome)
    )
    db.commit()
    return {"conversation_id": convo.id, "reply": welcome}


def add_message_service(conversation_id: int, text: str, tenant_id: int, db: Session):
    """
    The 'Premium State Machine'.
    Handles: Atomic Resets, FAQ Interruptions, and Omni-Intent Extraction.
    """
    convo = db.query(Conversation).get(conversation_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    text_clean = (text or "").strip()

    # 1. SAVE USER MESSAGE (Always track history)
    db.add(
        ConversationMessage(conversation_id=convo.id, role="user", content=text_clean)
    )
    db.commit()

    # 2. ATOMIC RESET: Handle 'Start Again' high-vocabulary request
    reset_keywords = ["start again", "new search", "restart", "something else", "clear"]
    if any(k in text_clean.lower() for k in reset_keywords):
        convo.data_json = "{}"
        convo.state = "ACTIVE"
        db.commit()
        return {
            "reply": "I've cleared our current search. 🔄 I'm ready to find you something new. What's your focus today?",
            "state": "ACTIVE",
            "prefs": {},
        }

    # 3. INTERRUPTION HANDLING: FAQ Check (Answer and keep in funnel)
    if is_company_faq(text_clean):
        profile = (
            db.query(CompanyProfile)
            .filter(CompanyProfile.tenant_id == tenant_id)
            .first()
        )
        faq_reply = answer_company_faq(db, tenant_id, text_clean, profile)
        # Note: We answer the question but DON'T change the state.
        # This allows them to answer the previous property question after the FAQ.
        return {
            "reply": f"{faq_reply}\n\nShall we continue with our property search? I'm still looking for your ideal match.",
            "state": convo.state,
        }

    # 4. SILENT FILLER CHECK (Cost Control)
    if is_filler(text_clean):
        return {
            "reply": "I understand. Please tell me more about the property you have in mind.",
            "state": convo.state,
        }

    # 5. OMNI-INTENT EXTRACTION (The Gemini Brain)
    current_prefs = json.loads(convo.data_json or "{}")
    updated_prefs = extract_preferences(text_clean, current_prefs)

    # Check if the AI detected a pivot/reset inside a natural sentence
    if updated_prefs.get("reset_requested"):
        convo.data_json = "{}"
        db.commit()
        return {
            "reply": "No problem, let's explore a different direction. What are you looking for now?",
            "state": "ACTIVE",
        }

    convo.data_json = json.dumps(updated_prefs)

    # 6. EVALUATE COMPLETION & RESPONSE
    next_question = get_next_question(updated_prefs)

    if not next_question:
        convo.state = "HANDOFF"
        # High-Authority vocabulary for the handoff
        next_question = "✅ Splendid. I have documented your requirements. I am now matching you with a verified specialist to provide a curated list of properties for your inspection."

    db.commit()
    return {"reply": next_question, "state": convo.state, "prefs": updated_prefs}


# ---------------------------------------------------------
# META WEBHOOK BRIDGE (The Entry Point)
# ---------------------------------------------------------


async def handle_incoming_message(data: dict, db: Session):
    """Bridges the Social Media Webhook to the Premium Logic above."""
    try:
        # A. Parse Payload
        entry = data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        if not messages:
            return

        msg = messages[0]
        sender_id = msg.get("from")

        # B. Handle Button Clicks (Leads)
        button_payload = msg.get("button", {}).get("payload", "")
        if "INTERESTED_IN_" in button_payload:
            list_id = int(button_payload.split("_")[-1])
            await alert_realtor_of_lead(db, list_id, sender_id)
            await send_meta_message(
                sender_id, "🤝 Agent notified! They will join this chat shortly."
            )
            return

        # C. Handle Chatting
        text = msg.get("text", {}).get("body", "")
        tenant_id = 1  # In prod, lookup by Meta Phone ID

        # 1. Get/Start Convo
        convo = (
            db.query(Conversation)
            .filter(Conversation.external_user_id == sender_id)
            .first()
        )
        if not convo:
            res = start_conversation_service("whatsapp", sender_id, None, tenant_id, db)
            convo_id = res["conversation_id"]
        else:
            convo_id = convo.id

        # 2. Run Pipeline
        pipeline_res = add_message_service(convo_id, text, tenant_id, db)

        # 3. Deliver Results (Carousel or Text)
        prefs = pipeline_res.get("prefs", {})
        matches = _find_matching_listings(db, tenant_id, prefs) if prefs else []

        if matches:
            carousel = prepare_meta_carousel(matches)
            await send_meta_carousel(sender_id, carousel)
            await send_meta_message(sender_id, pipeline_res["reply"])
        else:
            await send_meta_message(sender_id, pipeline_res["reply"])

    except Exception as e:
        logger.error(f"❌ BRIDGE ERROR: {e}", exc_info=True)
