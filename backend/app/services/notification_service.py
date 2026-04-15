import os
import httpx
import logging
import asyncio
from datetime import datetime, timedelta
from typing import List
from sqlalchemy.orm import Session

# Import Models
from app.listings.models import Listing
from app.users.models import User
from app.conversations.models import Conversation

# Configuration
logger = logging.getLogger(__name__)
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
# This is the Phone Number ID from your Meta Developer Dashboard
BUSINESS_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID")

# ---------------------------------------------------------
# CORE SENDER (The actual Meta API Engine)
# ---------------------------------------------------------


async def send_meta_text_message(recipient_id: str, text: str):
    """
    Low-level service to push text messages to WhatsApp/Instagram.
    """
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
            else:
                logger.info(f"✅ Message sent successfully to {recipient_id}")
    except Exception as e:
        logger.error(f"❌ Connection error sending Meta message: {e}")


# ---------------------------------------------------------
# LEAD ALERTS (The Money-Maker)
# ---------------------------------------------------------


async def alert_realtor_of_lead(db: Session, listing_id: int, client_phone: str):
    """
    Finds the Realtor for a property and sends them a 'Hot Lead' alert.
    This triggers when a user clicks 'I'm Interested' on the carousel.
    """
    try:
        # 1. Find the property
        listing = db.query(Listing).filter(Listing.id == listing_id).first()
        if not listing:
            logger.warning(f"⚠️ Alert failed: Listing {listing_id} not found.")
            return

        # 2. Find the Primary Admin/Agent for this Tenant
        # We look for an active admin user tied to the same tenant as the house
        agent = (
            db.query(User)
            .filter(
                User.tenant_id == listing.tenant_id,
                User.is_admin == True,
                User.is_active == True,
            )
            .first()
        )

        if not agent or not agent.phone_number:
            logger.warning(
                f"⚠️ Alert failed: No active admin with phone found for Tenant {listing.tenant_id}"
            )
            return

        # 3. Format the High-Intent Alert
        alert_text = (
            f"🚨 *HOT LEAD ALERT!* 🚨\n\n"
            f"A client is interested in your property:\n"
            f"🏠 *{listing.title}*\n"
            f"📍 {listing.location}\n"
            f"💰 ₦{listing.price:,}\n\n"
            f"📱 *Client Phone*: +{client_phone}\n\n"
            f"Please reach out to them immediately to close the deal! 🤝"
        )

        # 4. Push the alert to the Agent's WhatsApp
        await send_meta_text_message(agent.phone_number, alert_text)
        logger.info(f"🚀 Lead Alert pushed to Agent {agent.email}")

    except Exception as e:
        logger.error(f"❌ Error in Realtor Alert service: {e}", exc_info=True)


# ---------------------------------------------------------
# ABANDONED CHAT REMINDERS (The Retention Engine)
# ---------------------------------------------------------


async def check_for_abandoned_chats(db: Session):
    """
    Finds users who 'ghosted' the conversation and nudges them.
    Intervals: 2 hours, then 24 hours.
    """
    try:
        # Define 'Ghosting' time (e.g., 2 hours since last message)
        reminder_threshold = datetime.utcnow() - timedelta(hours=2)

        # Find ACTIVE conversations that are older than the threshold
        # but haven't been nudged more than twice.
        idle_convos = (
            db.query(Conversation)
            .filter(
                Conversation.state == "ACTIVE",
                Conversation.updated_at < reminder_threshold,
                Conversation.reminder_count < 2,
            )
            .all()
        )

        if not idle_convos:
            return

        for convo in idle_convos:
            # 1. Determine the Nudge Content
            if convo.reminder_count == 0:
                nudge = "Hey! 👋 Just checking back—are you still looking for a property? I've found some new matches you might like!"
            else:
                nudge = "Still there? 🏠 I don't want you to miss out on the best verified properties. Should we continue your search?"

            # 2. Send the Nudge
            await send_meta_text_message(convo.external_user_id, nudge)

            # 3. Update Conversation to prevent spamming
            convo.reminder_count += 1
            convo.updated_at = datetime.utcnow()  # Reset timer for the next 24h check
            db.commit()

            logger.info(
                f"🔔 Nudge #{convo.reminder_count} sent to {convo.external_user_id}"
            )

    except Exception as e:
        logger.error(f"❌ Error in Reminder service: {e}", exc_info=True)
        db.rollback()
