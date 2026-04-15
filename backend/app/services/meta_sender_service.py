import os
import httpx
import logging

logger = logging.getLogger(__name__)

ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
# Note: For WhatsApp, you need your 'Phone Number ID' from Meta
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_ID")


async def send_meta_message(recipient_id: str, text: str):
    """Sends a standard text message to the user."""
    if not ACCESS_TOKEN or not PHONE_NUMBER_ID:
        logger.warning("⚠️ Meta credentials missing. Message not sent.")
        return

    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_id,
        "type": "text",
        "text": {"body": text},
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            logger.error(f"❌ Meta Text Error: {response.text}")


async def send_meta_carousel(recipient_id: str, cards: list):
    """Sends the horizontal scrolling property carousel."""
    if not ACCESS_TOKEN or not PHONE_NUMBER_ID:
        logger.warning("⚠️ Meta credentials missing. Carousel not sent.")
        return

    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}

    # This is the 'Premium' structure for WhatsApp Carousels
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_id,
        "type": "template",
        "template": {
            "name": "property_carousel",  # You must create this template in Meta
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
                        for i, card in enumerate(cards[:10])  # Meta limit is 10 cards
                    ],
                }
            ],
        },
    }

    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload, headers=headers)
