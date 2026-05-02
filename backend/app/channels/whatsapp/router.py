import os
from fastapi import APIRouter, Request, BackgroundTasks, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from app.database.db import get_db

# Ensure this import matches your project structure
from app.services.conversation_service import handle_incoming_message

# 🔹 SOCKET: Define the prefix but be careful with the trailing slash
router = APIRouter(prefix="/webhooks/meta", tags=["Meta Webhooks"])


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
    """
    data = await request.json()
    # Execute the brain in the background to prevent Meta timeouts
    background_tasks.add_task(handle_incoming_message, data, db)
    return {"status": "success"}
