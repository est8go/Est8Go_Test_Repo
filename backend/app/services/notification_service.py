import os
import httpx
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

# Import Models
from app.listings.models import Listing
from app.users.models import User
from app.conversations.models import Conversation
from app.messages.models import Message

# Configuration
logger = logging.getLogger(__name__)
META_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN") or os.getenv("META_ACCESS_TOKEN")
BUSINESS_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID")

# ---------------------------------------------------------
# CORE SENDER (Meta API Engine)
# ---------------------------------------------------------


async def send_meta_text_message(recipient_id: str, text: str):
    """Low-level service to push text messages to WhatsApp/Instagram."""
    if not META_ACCESS_TOKEN or not BUSINESS_PHONE_ID:
        logger.error("❌ Meta Credentials missing in .env. Cannot send message.")
        return

    url = f"https://graph.facebook.com/v19.0/{BUSINESS_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_id,
        "type": "text",
        "text": {"body": text},
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                logger.error(f"❌ Meta API Error: {response.text}")
    except Exception as e:
        logger.error(f"❌ Connection error sending Meta message: {e}")


# ---------------------------------------------------------
# LEAD ALERTS (The Money-Maker)
# ---------------------------------------------------------


async def alert_realtor_of_lead(
    db: Session, listing_id: int, user_phone: str, biz_name: str
):
    """
    Finds the Realtor for a property and sends them a 'Hot Lead' alert.
    """
    try:
        # 1. Find the property
        listing = db.query(Listing).filter(Listing.id == listing_id).first()
        if not listing:
            logger.warning(f"⚠️ Alert failed: Listing {listing_id} not found.")
            return

        # 2. Find the Primary Agent for this Tenant
        agent = (
            db.query(User)
            .filter(
                User.tenant_id == listing.tenant_id,
                User.is_admin == True,
                User.is_active == True,
            )
            .first()
        )

        alert_phone = agent.phone_number if (agent and agent.phone_number) else None
        if not alert_phone:
            # Fallback: use tenant's registered WhatsApp number
            from app.tenants.models import Tenant as _Tenant
            import re as _re
            _tenant = db.query(_Tenant).filter(
                _Tenant.id == listing.tenant_id
            ).first()
            _raw = getattr(_tenant, "whatsapp_phone_number", None) if _tenant else None
            if _raw:
                _digits = _re.sub(r"\D", "", _raw)
                if _digits.startswith("0"):
                    _digits = "234" + _digits[1:]
                alert_phone = _digits or None
        if not alert_phone:
            logger.warning(
                f"⚠️ No phone for realtor alert: tenant={listing.tenant_id}"
            )
            return

        # 3. Format the High-Intent Alert
        alert_text = (
            f"🚨 *HOT LEAD ALERT: {biz_name}* 🚨\n\n"
            f"A client is interested in:\n"
            f"🏠 *{listing.title}*\n"
            f"💰 ₦{listing.price:,}\n\n"
            f"📱 *Client Phone*: +{user_phone}\n"
            f"Please reach out to them immediately! 🤝"
        )

        # 4. Push the alert to the Agent's WhatsApp
        await send_meta_text_message(alert_phone, alert_text)
        logger.info(
            f"🚀 Lead Alert for {biz_name} pushed to Agent {agent.phone_number}"
        )
        return True

    except Exception as e:
        logger.error(f"❌ Error in Realtor Alert service: {e}", exc_info=True)
        return False


# ---------------------------------------------------------
# ABANDONED CHAT REMINDERS (Retention Engine)
# ---------------------------------------------------------


async def check_for_abandoned_chats(db: Session):
    """Finds ghosted users and nudges them (2h and 24h intervals)."""
    try:
        # Using timezone-aware UTC
        reminder_threshold = datetime.now(timezone.utc) - timedelta(hours=2)

        idle_convos = (
            db.query(Conversation)
            .filter(
                Conversation.state == "ACTIVE",
                Conversation.updated_at < reminder_threshold,
                Conversation.reminder_count < 2,
            )
            .all()
        )

        for convo in idle_convos:
            nudge = "Hey! 👋 Just checking—are you still looking for a property? I don't want you to miss out on our verified deals!"
            await send_meta_text_message(convo.external_user_id, nudge)

            convo.reminder_count += 1
            convo.updated_at = datetime.now(timezone.utc)
            db.commit()

    except Exception as e:
        logger.error(f"❌ Error in Reminder service: {e}")
        db.rollback()


# ---------------------------------------------------------
# INSPECTION LOGIC
# ---------------------------------------------------------


async def send_meta_image_message(
    to: str,
    image_url: str,
    caption: str,
    phone_number_id: str = None,
) -> bool:
    """Sends a WhatsApp image message with optional caption."""
    token = META_ACCESS_TOKEN
    pid = phone_number_id or BUSINESS_PHONE_ID
    if not token or not pid:
        logger.warning("Meta credentials missing — image message not sent")
        return False
    url = f"https://graph.facebook.com/v19.0/{pid}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "image",
        "image": {"link": image_url, "caption": caption},
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=headers, timeout=30)
            if resp.status_code != 200:
                logger.warning(f"Image send non-200: {resp.text}")
            return resp.status_code == 200
    except Exception as e:
        logger.warning(f"Image send failed: {e}")
        return False


async def schedule_inspection_logic(
    db: Session, tenant_id: int, user_phone: str, property_id: int, date_text: str
):
    """Saves the inspection intent to the Message table."""
    try:
        new_request = Message(
            tenant_id=tenant_id,
            sender_id=user_phone,
            content=f"INSPECTION REQUEST for Property #{property_id} on {date_text}",
            is_bot=False,
        )
        db.add(new_request)
        db.commit()
        return f"Excellent. I've noted your interest for {date_text}. The Realtor will call you shortly to confirm."
    except Exception as e:
        logger.error(f"Failed to save inspection: {e}")
        return "I've noted your interest, but I had a small glitch saving the date."
