import hashlib
import hmac
import json
import logging
import os
from fastapi import APIRouter, Request, BackgroundTasks, Depends
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.orm import Session
from app.database.db import get_db

# Ensure this import matches your project structure
from app.services.conversation_service import handle_incoming_message

logger = logging.getLogger(__name__)

# 🔹 SOCKET: Define the prefix but be careful with the trailing slash
router = APIRouter(prefix="/webhooks/meta", tags=["Meta Webhooks"])


# ================================================================
# META PAYLOAD SIGNATURE VERIFICATION
# ================================================================
# Meta signs every webhook POST with HMAC-SHA256 of the RAW request
# body, keyed on the app secret, sent as:
#     X-Hub-Signature-256: sha256=<hexdigest>
#
# Without this check the endpoint accepts any POST from anyone: forged
# buyer messages into any tenant's conversation, triggered outbound
# sends, burned credits.
#
# The digest MUST be computed over the raw bytes. Re-serialising parsed
# JSON changes key order and whitespace and will never match.


def _verify_meta_signature(raw_body: bytes, signature_header: str | None) -> bool:
    """
    True if signature_header is a valid Meta signature for raw_body.

    Returns False on a missing, malformed, or wrong signature. Uses
    hmac.compare_digest — never ==, which leaks length and content
    through timing.

    Callers must handle the "no secret configured" case themselves;
    this function assumes META_APP_SECRET is set.
    """
    _secret = os.getenv("META_APP_SECRET", "")
    if not _secret:
        return False
    if not signature_header:
        return False

    # Header format is "sha256=<hex>". Anything else is malformed.
    _prefix, _, _their_digest = signature_header.partition("=")
    if _prefix != "sha256" or not _their_digest:
        return False

    _our_digest = hmac.new(
        _secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(_our_digest, _their_digest)


@router.get("/")
@router.get("")
async def verify_webhook(request: Request):
    """
    Indestructible Meta Handshake:
    Sanitized and Ruff-compliant (No redundant f-strings).
    """
    params = request.query_params

    # 1. Fetch and Sanitize the Expected Token
    raw_env_token = os.getenv("META_VERIFY_TOKEN", "Est8Go_Secure_2026")
    expected_token = raw_env_token.strip().replace('"', "").replace("'", "")

    # 2. Extract and Sanitize Meta's Token
    received_token = params.get("hub.verify_token") or params.get("hub_verify_token")
    if received_token:
        received_token = received_token.strip()

    challenge = params.get("hub.challenge") or params.get("hub_challenge")
    mode = params.get("hub.mode") or params.get("hub_mode")

    # 3. The Comparison
    if mode == "subscribe" and received_token == expected_token:
        print(f"✅ HANDSHAKE SUCCESS: Verified '{received_token}'")
        return PlainTextResponse(content=str(challenge))

    # 4. Diagnostic Log (Removed redundant 'f' to satisfy Ruff F541)
    print("❌ HANDSHAKE ERROR")
    print(f"   - Expected: [{expected_token}]")
    print(f"   - Received: [{received_token}]")

    return PlainTextResponse(content="Verification failed", status_code=403)


# --- 2. THE RECEIVER (Unified POST) ---
@router.post("/")
@router.post("")  # Standardizes the receiver for all Meta platforms
async def receive_meta_message(
    request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    """
    Unified entry point for WhatsApp, Instagram, and Facebook messages.

    Every payload is signature-checked against META_APP_SECRET before
    anything is parsed or dispatched. Fails closed: an unset secret
    rejects all traffic rather than accepting it unverified.
    """
    # Raw bytes — the signature is over these, not over parsed JSON.
    raw_body = await request.body()
    _sig = request.headers.get("X-Hub-Signature-256")

    # FAIL CLOSED. A missing META_APP_SECRET rejects every payload rather
    # than waving it through — there is deliberately no path where an
    # unset or empty secret silently disables verification. Logged
    # separately from a bad signature because the two have completely
    # different causes: this one is our misconfiguration, and without a
    # distinct message it looks like Meta sending bad signatures.
    if not os.getenv("META_APP_SECRET"):
        logger.critical(
            "❌ WEBHOOK REJECTED: META_APP_SECRET is not set — rejecting ALL "
            "webhook traffic. Kora is offline until this is set on the web "
            "service (Meta App Dashboard → Settings → Basic → App Secret)."
        )
        return JSONResponse(status_code=403, content={"detail": "Invalid signature"})

    if not _verify_meta_signature(raw_body, _sig):
        # Do not echo the signature or body back — a rejection response
        # should tell an attacker nothing beyond "no".
        logger.error(
            "❌ WEBHOOK REJECTED: bad or missing X-Hub-Signature-256 "
            f"(header {'present' if _sig else 'absent'}, "
            f"{len(raw_body)} bytes)"
        )
        return JSONResponse(status_code=403, content={"detail": "Invalid signature"})

    # Parse only after the payload is trusted. Malformed JSON from a
    # signed sender is still possible — never let it 500.
    try:
        data = json.loads(raw_body)
    except (ValueError, UnicodeDecodeError) as e:
        logger.error(f"❌ WEBHOOK: unparseable JSON body — {e}")
        return JSONResponse(status_code=400, content={"detail": "Malformed payload"})

    # Execute the brain in the background to prevent Meta timeouts
    background_tasks.add_task(handle_incoming_message, data, db)
    return {"status": "success"}
