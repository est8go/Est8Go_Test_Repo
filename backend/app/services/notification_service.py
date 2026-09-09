import os
import httpx
import logging
from sqlalchemy.orm import Session

# Import Models
from app.listings.models import Listing
from app.users.models import User
from app.messages.models import Message

# Configuration
logger = logging.getLogger(__name__)
META_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN") or os.getenv("META_ACCESS_TOKEN")
BUSINESS_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID")

# Stable log tags. Every realtor alert emits exactly one of these, so the
# delivery rate is countable straight off the Render logs without parsing
# free prose:
#   REALTOR_ALERT_FAILED reason=window_closed   → needs an approved template
#   REALTOR_ALERT_FAILED reason=no_alert_phone  → nobody has a number set
# Do not reword these strings; they are the query.
REALTOR_ALERT_FAILED = "REALTOR_ALERT_FAILED"
REALTOR_ALERT_SENT = "REALTOR_ALERT_SENT"

# ---------------------------------------------------------
# CORE SENDER (Meta API Engine)
# ---------------------------------------------------------


# Meta error codes meaning "the 24-hour customer-service window is shut".
# 131047 — Re-engagement message: >24h since the recipient last replied.
#    470 — legacy code for the same condition; still returned by some
#          phone-number / API-version combinations.
# Outside the window only an approved template gets through, so a failure
# with one of these codes is a template problem, not a delivery fault.
WINDOW_CLOSED_CODES = {131047, 470}


def _meta_error_code(response) -> int | None:
    """Meta's numeric error code from a non-200 body, or None if absent."""
    try:
        return int(response.json()["error"]["code"])
    except (ValueError, TypeError, KeyError, AttributeError):
        return None


async def _send_text(
    recipient_id: str,
    text: str,
    phone_number_id: str = None,
    access_token: str = None,
) -> tuple[bool, str]:
    """
    Pushes a free-form text message and reports WHY it failed.

    Returns (ok, reason). reason is one of:
        ok | no_credentials | no_recipient | window_closed
        | api_error:<code> | http_<status> | connection_error

    The reason exists so callers can distinguish "this realtor has no open
    24h window" from "the token is wrong" — the two need completely
    different fixes and previously produced the identical silent None.
    """
    pid = phone_number_id or BUSINESS_PHONE_ID
    _token = access_token or META_ACCESS_TOKEN
    if not _token or not pid:
        logger.error("❌ Meta Credentials missing in .env. Cannot send message.")
        return False, "no_credentials"
    if not recipient_id:
        logger.error("❌ Meta: cannot send, recipient_id is empty")
        return False, "no_recipient"

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
            response = await client.post(
                url, json=payload, headers=headers, timeout=30
            )
            if response.status_code == 200:
                return True, "ok"

            _code = _meta_error_code(response)
            if _code in WINDOW_CLOSED_CODES:
                # Logged distinctly: this is the 24h window, not a bug.
                logger.error(
                    f"❌ META_WINDOW_CLOSED code={_code} to={recipient_id} "
                    f"— no free-form message can reach this number until "
                    f"they message the business first. An approved template "
                    f"is the only route."
                )
                return False, "window_closed"

            logger.error(
                f"❌ Meta API Error ({response.status_code}) "
                f"code={_code} to={recipient_id}: {response.text}"
            )
            return False, (
                f"api_error:{_code}" if _code is not None
                else f"http_{response.status_code}"
            )
    except Exception as e:
        logger.error(f"❌ Connection error sending Meta message: {e}")
        return False, "connection_error"


async def send_meta_text_message(
    recipient_id: str, text: str, phone_number_id: str = None, access_token: str = None
) -> bool:
    """
    Low-level service to push text messages to WhatsApp/Instagram.

    Returns True ONLY on HTTP 200. Previously returned None on both success
    and failure, which made every caller's success check a no-op.
    """
    _ok, _ = await _send_text(
        recipient_id, text,
        phone_number_id=phone_number_id,
        access_token=access_token,
    )
    return _ok


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
    access_token: str = None,
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
            logger.error(
                f"❌ {REALTOR_ALERT_FAILED} reason=listing_not_found "
                f"listing={listing_id} tier=none to=none"
            )
            return False

        alert_phone = None
        alert_name = None
        # Which fallback tier supplied the number. Recorded on every failure
        # log: a "tenant_number" alert is the tenant's own WhatsApp line,
        # which by definition never has an open 24h window to itself.
        alert_tier = "none"

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
                alert_tier = "assigned_realtor"

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
                alert_tier = "tenant_admin"

        # Priority 3: Tenant WhatsApp number
        if not alert_phone:
            tenant = db.query(_Tenant).filter(_Tenant.id == listing.tenant_id).first()
            if tenant and tenant.whatsapp_phone_number:
                digits = _re.sub(r"\D", "", tenant.whatsapp_phone_number)
                if digits.startswith("0"):
                    digits = "234" + digits[1:]
                alert_phone = digits or None
                if alert_phone:
                    alert_tier = "tenant_number"

        if not alert_phone:
            logger.error(
                f"❌ {REALTOR_ALERT_FAILED} reason=no_alert_phone "
                f"listing={listing_id} tenant={listing.tenant_id} "
                f"tier=none to=none"
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

        _ok, _reason = await _send_text(
            alert_phone, alert_text,
            phone_number_id=phone_number_id,
            access_token=access_token,
        )

        if not _ok:
            # One greppable line per failed realtor alert, carrying the cause.
            # Callers escalate on the returned False (see the
            # SUPER_ADMIN_WHATSAPP path in conversation_service) — that
            # escalation could never fire while this returned True blindly.
            logger.error(
                f"❌ {REALTOR_ALERT_FAILED} reason={_reason} "
                f"listing={listing_id} tenant={listing.tenant_id} "
                f"tier={alert_tier} to={alert_phone}"
            )
            return False

        logger.info(
            f"✅ {REALTOR_ALERT_SENT} listing={listing_id} "
            f"tenant={listing.tenant_id} tier={alert_tier} to={alert_phone}"
        )
        return True

    except Exception as e:
        logger.error(
            f"❌ {REALTOR_ALERT_FAILED} reason=exception "
            f"listing={listing_id}: {e}",
            exc_info=True,
        )
        return False


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
