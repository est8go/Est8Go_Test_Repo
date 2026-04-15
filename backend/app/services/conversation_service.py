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
    format_listings_text,
    calculate_typing_ms,
)
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
    """Securely fetches properties from the database with weighted scoring."""
    # Only show VERIFIED listings to the public
    query = db.query(Listing).filter(
        Listing.tenant_id == tenant_id, Listing.status == "verified"
    )

    if data.get("location"):
        query = query.filter(Listing.location.ilike(f"%{data['location']}%"))
    if data.get("property_type"):
        query = query.filter(Listing.property_type.ilike(f"%{data['property_type']}%"))
    if data.get("budget"):
        query = query.filter(Listing.price <= int(data["budget"]))

    listings = query.all()

    # Weighted scoring for relevance
    def score(listing):
        s = 0
        if (
            data.get("location")
            and data["location"].lower() in (listing.location or "").lower()
        ):
            s += 3
        if (
            data.get("property_type")
            and data["property_type"].lower() in (listing.property_type or "").lower()
        ):
            s += 2
        return s

    return sorted(listings, key=score, reverse=True)[:5]


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
    """The State Machine: Filters, FAQs, and Data Extraction."""
    convo = db.query(Conversation).get(conversation_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Convo not found")

    text_clean = (text or "").strip()
    db.add(
        ConversationMessage(conversation_id=convo.id, role="user", content=text_clean)
    )

    # 1. Cost Control: Filler Check
    if is_filler(text_clean):
        return {
            "reply": "Got it. Please tell me more about what you're looking for.",
            "state": convo.state,
        }

    # 2. Knowledge Base: FAQ Check
    if is_company_faq(text_clean):
        profile = (
            db.query(CompanyProfile)
            .filter(CompanyProfile.tenant_id == tenant_id)
            .first()
        )
        reply = answer_company_faq(db, tenant_id, text_clean, profile)
        return {"reply": reply, "state": convo.state}

    # 3. AI Extraction: Identify Location, Budget, Type
    current_data = json.loads(convo.data_json or "{}")
    updated_data = extract_preferences(text_clean, current_data)
    convo.data_json = json.dumps(updated_data)

    # 4. Logic: Get next question or handoff
    next_q = get_next_question(updated_data)
    if not next_q:
        convo.state = "HANDOFF"
        next_q = (
            "✅ I've captured your preferences! A consultant will contact you shortly."
        )

    db.commit()
    return {"reply": next_q, "state": convo.state, "prefs": updated_data}


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
