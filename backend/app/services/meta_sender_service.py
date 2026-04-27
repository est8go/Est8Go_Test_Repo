import os
import httpx
import logging

logger = logging.getLogger(__name__)

# --- Environment Controls ---
ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_ID")


async def send_meta_message(recipient_id: str, text: str):
    """
    Sends a standard text message via Meta's Graph API.
    Includes robust error checking to prevent silent failures.
    """
    if not ACCESS_TOKEN or not PHONE_NUMBER_ID:
        logger.error("❌ CRITICAL: Meta credentials (TOKEN/ID) missing in .env")
        return

    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_id,
        "type": "text",
        "text": {"body": text},
    }

    # Your standard httpx logic + Premium Response Validation
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers)

            # --- PREMIUM ERROR CHECKING ---
            if response.status_code != 200:
                logger.error(
                    f"❌ Meta API Error ({response.status_code}): {response.text}"
                )
            else:
                logger.info(f"✅ Message delivered to {recipient_id}")
            # ------------------------------

        except httpx.RequestError as e:
            logger.error(f"❌ Network error connecting to Meta: {e}")


async def send_meta_carousel(recipient_id: str, cards: list):
    """
    Sends a high-intent property carousel.
    Requires 'property_carousel' template to be approved in Meta Dashboard.
    """
    if not ACCESS_TOKEN or not PHONE_NUMBER_ID:
        logger.error("❌ CRITICAL: Meta credentials missing.")
        return

    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}

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


# --- THE REQUIRED ALIAS ---
# Fixes the 'ImportError' in conversation_service.py without changing your naming style.
send_whatsapp_message = send_meta_message
