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


async def send_meta_text_message(
    recipient_id: str, text: str, phone_number_id: str = None, access_token: str = None
):
    """Low-level service to push text messages to WhatsApp/Instagram."""
    pid = phone_number_id or BUSINESS_PHONE_ID
    _token = access_token or META_ACCESS_TOKEN
    if not _token or not pid:
        logger.error("❌ Meta Credentials missing in .env. Cannot send message.")
        return

    url = f"https://graph.facebook.com/v19.0/{pid}/messages"
    headers = {
        "Authorization": f"Bearer {_token}",
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
    db: Session,
    listing_id: int,
    user_phone: str,
    biz_name: str,
    phone_number_id: str = None,
    custom_message: str = None,
):
    """
    Alert priority:
    1. Assigned realtor's phone_number
    2. Tenant admin's phone_number
    3. Tenant's whatsapp_phone_number (fallback)
    """
    try:
        from app.tenants.models import Tenant as _Tenant
        import re as _re

        listing = db.query(Listing).filter(Listing.id == listing_id).first()
        if not listing:
            logger.warning(f"⚠️ Alert failed: Listing {listing_id} not found.")
            return False

        alert_phone = None
        alert_name = None

        # Priority 1: Assigned realtor
        if listing.assigned_realtor_id:
            realtor = (
                db.query(User)
                .filter(
                    User.id == listing.assigned_realtor_id,
                    User.is_active == True,
                )
                .first()
            )
            if realtor and realtor.phone_number:
                alert_phone = realtor.phone_number
                alert_name = realtor.first_name or realtor.email.split("@")[0]

        # Priority 2: Tenant admin
        if not alert_phone:
            admin = (
                db.query(User)
                .filter(
                    User.tenant_id == listing.tenant_id,
                    User.role == "admin",
                    User.is_active == True,
                    User.phone_number.isnot(None),
                )
                .first()
            )
            if admin and admin.phone_number:
                alert_phone = admin.phone_number
                alert_name = admin.first_name or admin.email.split("@")[0]

        # Priority 3: Tenant WhatsApp number
        if not alert_phone:
            tenant = db.query(_Tenant).filter(_Tenant.id == listing.tenant_id).first()
            if tenant and tenant.whatsapp_phone_number:
                digits = _re.sub(r"\D", "", tenant.whatsapp_phone_number)
                if digits.startswith("0"):
                    digits = "234" + digits[1:]
                alert_phone = digits or None

        if not alert_phone:
            logger.warning(
                f"⚠️ No alert phone found: listing={listing_id} tenant={listing.tenant_id}"
            )
            return False

        # Normalize phone — strip leading 0, ensure 234 prefix
        digits = _re.sub(r"\D", "", alert_phone)
        if digits.startswith("0"):
            digits = "234" + digits[1:]
        alert_phone = digits

        if custom_message:
            alert_text = custom_message
        else:
            # Build Google Maps nav link for agent
            nav_link = ""
            if listing.latitude and listing.longitude:
                nav_link = (
                    f"https://www.google.com/maps/dir/?api=1"
                    f"&destination={listing.latitude},{listing.longitude}"
                    f"&travelmode=driving"
                )

            directions_block = ""
            if getattr(listing, "directions", None):
                directions_block = (
                    f"🗺️ *Directions to Gate:*\n{listing.directions}\n\n"
                )

            alert_text = (
                f"🔔 *INSPECTION ALERT — ACTION REQUIRED*\n\n"
                f"Hi {alert_name}, a buyer has confirmed interest "
                f"in a property you manage:\n\n"
                f"🏠 *{listing.title}*\n"
                f"📍 {(listing.location or '').title()}\n"
                f"💰 ₦{listing.price:,}\n"
                f"🛡️ Trust Score: {listing.trust_score or 0}/100\n\n"
                f"👤 *Buyer Details:*\n"
                f"📱 Contact: +{user_phone}\n\n"
                f"⚡ *Your Action:*\n"
                f"Please reach out to the buyer immediately to "
                f"confirm the inspection date and time.\n\n"
                + (
                    f"📍 *Navigate to Property:*\n{nav_link}\n\n"
                    if nav_link
                    else f"📍 *Location:* {(listing.location or '').title()} "
                    f"— GPS coordinates pending verification.\n\n"
                )
                + directions_block
                + f"You are required to be *physically present* "
                f"at the property gate to receive the buyer. 🤝\n\n"
                f"Please confirm your attendance by calling "
                f"the buyer directly."
            )

        await send_meta_text_message(
            alert_phone, alert_text, phone_number_id=phone_number_id
        )
        logger.info(f"✅ Lead alert sent to {alert_phone} for listing {listing_id}")
        return True

    except Exception as e:
        logger.error(f"❌ alert_realtor_of_lead error: {e}", exc_info=True)
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
    access_token: str = None,
) -> bool:
    """Sends a WhatsApp image message with optional caption."""
    token = access_token or META_ACCESS_TOKEN
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
