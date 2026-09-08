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


# ================================================================
# TEMPLATE MESSAGE SENDER (re-engagement beyond 24h window)
# ================================================================


async def send_meta_template(
    recipient_id: str,
    template_name: str,
    body_params: list = None,
    header_image_url: str = None,
    language: str = "en",
    phone_number_id: str = None,
    access_token: str = None,
) -> bool:
    """
    Sends an APPROVED Meta template message (the only message type Meta
    permits outside the 24h customer-care window — i.e. recovery sends).

    Components are built conditionally: a header only when an image URL is
    given (template 5), a body only when body_params are given. All approved
    buttons are static Quick-Reply → NO button component is sent.

    Credential handling mirrors send_meta_message: per-tenant
    phone_number_id + access_token when supplied, global env fallback.

    Returns True ONLY on HTTP 200. Non-200 / exception → logs and returns
    False (this bool gates billing in Item 7 — it must be honest).
    """
    pid = phone_number_id or PHONE_NUMBER_ID
    _token = access_token or ACCESS_TOKEN
    if not _token or not pid:
        logger.error("❌ META ERROR: Credentials missing — template not sent")
        return False
    if not recipient_id:
        logger.error("❌ META ERROR: Cannot send template, recipient_id is empty!")
        return False

    components = []
    if header_image_url:
        components.append({
            "type": "header",
            "parameters": [
                {"type": "image", "image": {"link": header_image_url}}
            ],
        })
    if body_params:
        components.append({
            "type": "body",
            "parameters": [
                {"type": "text", "text": str(p)} for p in body_params
            ],
        })

    url = f"https://graph.facebook.com/v19.0/{pid}/messages"
    headers = {
        "Authorization": f"Bearer {_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": str(recipient_id),
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language},
            "components": components,
        },
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                logger.error(
                    f"❌ Meta Template Error ({response.status_code}): "
                    f"{response.text} | template={template_name} | to={recipient_id}"
                )
                return False
            logger.info(
                f"✅ Template '{template_name}' sent to {recipient_id}"
            )
            return True
        except Exception as e:
            logger.error(
                f"❌ Connection error sending template '{template_name}': {e}"
            )
            return False


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
