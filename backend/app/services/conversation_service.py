from __future__ import annotations
import json
import logging
from typing import Optional, List
from sqlalchemy.orm import Session

# 1. Domain Models
from app.company_profiles.models import CompanyProfile
from app.conversations.models import Conversation, ConversationMessage
from app.listings.models import Listing

# 2. Logic Tools
from app.conversations.templates import is_filler, get_next_question
from app.conversations.brain import extract_preferences
from app.conversations.ai_fallback import is_company_faq, answer_company_faq

# 3. External Senders
from app.services.meta_sender_service import send_meta_carousel, send_meta_message
from app.services.notification_service import alert_realtor_of_lead
from app.services.trust_engine import calculate_confidence_score

logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# PROPERTY SEARCH ENGINE
# ---------------------------------------------------------
def _find_matching_listings(db: Session, tenant_id: int, data: dict) -> List[Listing]:
    """Premium Search: Finds verified matches with flexible criteria."""
    query = db.query(Listing).filter(
        Listing.tenant_id == tenant_id, Listing.status == "verified"
    )

    if data.get("location"):
        loc_search = data["location"].lower().replace("abuja", "").strip()
        query = query.filter(Listing.location.ilike(f"%{loc_search}%"))

    if data.get("property_type"):
        query = query.filter(Listing.property_type.ilike(f"%{data['property_type']}%"))

    if data.get("budget"):
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
# CONVERSATION START
# ---------------------------------------------------------
def start_conversation_service(
    channel: str,
    external_user_id: str,
    display_name: Optional[str],
    tenant_id: int,
    db: Session,
):
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

    name = profile.assistant_name if profile else "Assistant"
    firm = profile.company_name if profile else "our firm"
    reply = (
        f"Hi {display_name}! I am {name}, your property consultant for {firm}. 👋\n\n"
        f"I'm here to help you find a secure and profitable property investment. "
        f"You can type *'New search'* at any time to start fresh. 🔄\n\n"
        f"Are you looking to buy, rent, or invest?"
    )
    db.add(
        ConversationMessage(conversation_id=convo.id, role="assistant", content=reply)
    )
    db.commit()
    return {"conversation_id": convo.id, "reply": reply}


# ---------------------------------------------------------
# THE STATE MACHINE
# ---------------------------------------------------------
def add_message_service(conversation_id: int, text: str, tenant_id: int, db: Session):
    convo = db.query(Conversation).get(conversation_id)
    text_clean = (text or "").strip()

    # 1. ATOMIC RESET
    if any(k in text_clean.lower() for k in ["new search", "start again", "restart"]):
        convo.data_json = "{}"
        convo.state = "ACTIVE"
        db.commit()
        return {
            "reply": f"Understood, {convo.display_name}. I've cleared our search. What type of property are we looking for now?",
            "state": "ACTIVE",
            "prefs": {},
        }

    # 2. FILLER CHECK (ACCESSED: Cost Control)
    if is_filler(text_clean):
        return {
            "reply": "Got it. Please tell me more about what you're looking for.",
            "state": convo.state,
            "prefs": {},
        }

    # 3. FAQ CHECK
    if is_company_faq(text_clean):
        profile = (
            db.query(CompanyProfile)
            .filter(CompanyProfile.tenant_id == tenant_id)
            .first()
        )
        reply = answer_company_faq(db, tenant_id, text_clean, profile)
        return {
            "reply": f"{reply}\n\nShall we continue with our search?",
            "state": convo.state,
            "prefs": {},
        }

    # 4. AI EXTRACTION
    current_prefs = json.loads(convo.data_json or "{}")
    updated_prefs = extract_preferences(text_clean, current_prefs)
    convo.data_json = json.dumps(updated_prefs)

    # 5. SMART FLOW
    if updated_prefs.get("location") and (
        updated_prefs.get("budget") or updated_prefs.get("property_type")
    ):
        db.commit()
        return {
            "reply": "Excellent. I'm reviewing our verified inventory for you now...",
            "state": convo.state,
            "prefs": updated_prefs,
            "trigger_search": True,
        }

    next_q = get_next_question(updated_prefs)
    if not next_q:
        convo.state = "HANDOFF"
        next_q = "✅ Captured! I'm matching you with a verified specialist now."

    db.commit()
    return {"reply": next_q, "state": convo.state, "prefs": updated_prefs}


# ---------------------------------------------------------
# META WEBHOOK BRIDGE
# ---------------------------------------------------------
async def handle_incoming_message(data: dict, db: Session):
    try:
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
        tenant_id = 1

        # A. HANDLE BUTTONS (ACCESSED: Realtor Lead Alerts)
        btn_payload = msg.get("button", {}).get("payload", "") or msg.get(
            "postback", {}
        ).get("payload", "")
        if "INTERESTED_IN_" in btn_payload:
            list_id = int(btn_payload.split("_")[-1])
            await alert_realtor_of_lead(db, list_id, sender_id)
            await send_meta_message(
                sender_id,
                "🤝 Excellent decision. I've alerted the verified agent; they will reach out shortly.",
            )
            return

        # B. HANDLE TEXT
        text_body = msg.get("text", {}).get("body", "")
        convo = (
            db.query(Conversation)
            .filter(Conversation.external_user_id == sender_id)
            .first()
        )

        if not convo:
            res = start_conversation_service(
                "whatsapp", sender_id, whatsapp_name, tenant_id, db
            )
            convo_id = res["conversation_id"]
            convo = db.query(Conversation).get(convo_id)
        else:
            convo_id = convo.id
            if not convo.display_name or convo.display_name == "there":
                convo.display_name = whatsapp_name
                db.commit()

        # Resume Welcome
        from datetime import datetime, timedelta

        if convo.updated_at and convo.updated_at < (
            datetime.utcnow() - timedelta(hours=4)
        ):
            await send_meta_message(
                sender_id,
                f"Welcome back, {convo.display_name}! Should we continue, or start a *'New search'*?",
            )

        # Run State Machine
        pipe = add_message_service(convo_id, text_body, tenant_id, db)
        prefs = pipe.get("prefs", {})

        # C. DELIVERY
        if pipe.get("trigger_search") or (
            prefs.get("location") and prefs.get("property_type")
        ):
            matches = _find_matching_listings(db, tenant_id, prefs)
            if matches:
                carousel_cards = prepare_meta_carousel(matches)

            # This line now works because we imported 'calculate_confidence_score'
            trust_pct = calculate_confidence_score(matches[0])

            summary = (
                f"✨ *Premium Match Found!*\n\n"
                f"🏠 *{matches[0].title}*\n"
                f"💰 Price: ₦{matches[0].price:,}\n"
                f"📍 Location: {matches[0].location}\n\n"
                f"This property has an Est8Go Trust Score of **{trust_pct}%**. "
                f"Would you like to view the full gallery? 👇"
            )
            await send_meta_message(sender_id, summary)
            await send_meta_carousel(sender_id, carousel_cards)
            return

        await send_meta_message(sender_id, pipe["reply"])

    except Exception as e:
        logger.error(f"❌ BRIDGE ERROR: {e}", exc_info=True)
