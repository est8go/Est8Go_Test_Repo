import os
import httpx
import logging

logger = logging.getLogger(__name__)

# --- Environment Controls ---
ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_ID")


async def send_meta_message(
    recipient_id: str,
    text: str,
    phone_number_id: str = None,
    access_token: str = None,
):
    """
    Sends a standard text message.
    The recipient_id must be a string (e.g. '2348030000000')
    """
    pid = phone_number_id or PHONE_NUMBER_ID
    _token = access_token or ACCESS_TOKEN
    if not _token or not pid:
        logger.error("❌ META ERROR: Credentials missing")
        return

    # 🔹 SOCKET: Ensure recipient_id is not empty
    if not recipient_id:
        logger.error(
            "❌ META ERROR: Cannot send message, phone number (recipient_id) is empty!"
        )
        return

    url = f"https://graph.facebook.com/v19.0/{pid}/messages"
    headers = {
        "Authorization": f"Bearer {_token}",
        "Content-Type": "application/json",
    }

    # 🔹 SOCKET: Meta's payload structure
    payload = {
        "messaging_product": "whatsapp",
        "to": str(recipient_id),  # Ensure it is a string
        "type": "text",
        "text": {"body": text},
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                # This log will help us see exactly what 'recipient_id' was sent
                logger.error(
                    f"❌ Meta Error: {response.text} | Sent to: {recipient_id}"
                )
            else:
                logger.info(f"✅ Message sent to {recipient_id}")
        except Exception as e:
            logger.error(f"❌ Connection Error: {e}")


async def send_meta_carousel(
    recipient_id: str,
    cards: list,
    phone_number_id: str = None,
    access_token: str = None,
):
    """
    Sends a high-intent property carousel.
    Requires 'property_carousel' template to be approved in Meta Dashboard.
    """
    pid = phone_number_id or PHONE_NUMBER_ID
    _token = access_token or ACCESS_TOKEN
    if not _token or not pid:
        logger.error("❌ CRITICAL: Meta credentials missing.")
        return

    url = f"https://graph.facebook.com/v19.0/{pid}/messages"
    headers = {"Authorization": f"Bearer {_token}"}

    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_id,
        "type": "template",
        "template": {
            "name": "property_carousel",
            "language": {"code": "en_US"},
            "components": [
                {
                    "type": "carousel",
                    "cards": [
                        {
                            "card_index": i,
                            "components": [
                                {
                                    "type": "header",
                                    "parameters": [
                                        {
                                            "type": "image",
                                            "image": {"link": card["image_url"]},
                                        }
                                    ],
                                },
                                {
                                    "type": "body",
                                    "parameters": [
                                        {"type": "text", "text": card["title"]},
                                        {"type": "text", "text": card["subtitle"]},
                                    ],
                                },
                            ],
                        }
                        for i, card in enumerate(cards[:10])
                    ],
                }
            ],
        },
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers)

            # --- PREMIUM ERROR CHECKING ---
            if response.status_code != 200:
                logger.error(
                    f"❌ Meta Carousel Error ({response.status_code}): {response.text}"
                )
            else:
                logger.info(f"✅ Carousel delivered to {recipient_id}")
            # ------------------------------

        except httpx.RequestError as e:
            logger.error(f"❌ Network error sending Carousel: {e}")

            # 🔹 SOCKET: Add this to the bottom of backend/app/services/meta_sender_service.py


def prepare_meta_carousel(listings: list) -> list:
    """
    Premium Visual Formatter: Turns a list of listings into Meta-ready cards.
    """
    cards = []
    for item in listings:
        # 1. Fetch main image or use high-end fallback
        image_url = (
            item.images[0].url
            if (hasattr(item, "images") and item.images)
            else "https://images.unsplash.com/photo-1560518883-ce09059eeffa"
        )

        # 2. Build the card structure
        cards.append(
            {
                "title": item.title[:80],  # Meta limit
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


# ================================================================
# PER-TENANT CREDENTIAL RESOLVER (Scenario B)
# ================================================================


def get_tenant_whatsapp_credentials(db, tenant_id):
    """Returns (phone_number_id, access_token, waba_id)
    for a tenant. Falls back to global env
    token if tenant has no stored token
    (Scenario A compatibility during
    migration). Returns (None, None, None)
    if tenant/channel not found."""
    from app.tenants.models import TenantChannel, Tenant
    from app.core.crypto import decrypt_secret
    import os

    # Try the active WhatsApp channel first
    _chan = (
        db.query(TenantChannel)
        .filter(
            TenantChannel.tenant_id == tenant_id,
            TenantChannel.platform == "whatsapp",
            TenantChannel.is_active == True,
        )
        .first()
    )

    _pid = None
    _token = None
    _waba = None

    if _chan:
        _pid = _chan.platform_id
        _waba = getattr(_chan, "waba_id", None)
        _enc = getattr(_chan, "access_token_encrypted", None)
        if _enc:
            try:
                _token = decrypt_secret(_enc)
            except Exception:
                _token = None

    # Fallback to Tenant.whatsapp_phone_number_id
    # for the number if channel missing it
    if not _pid:
        _tenant = db.get(Tenant, tenant_id)
        if _tenant:
            _pid = getattr(
                _tenant, "whatsapp_phone_number_id", None
            )

    # Fallback to global env token
    # (Scenario A compatibility — until
    # every tenant has its own token stored)
    if not _token:
        _token = os.getenv("WHATSAPP_ACCESS_TOKEN")

    return _pid, _token, _waba


# --- THE REQUIRED ALIAS ---
# Fixes the 'ImportError' in conversation_service.py without changing your naming style.
send_whatsapp_message = send_meta_message
