import os
from fastapi import APIRouter, Request, BackgroundTasks, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from app.database.db import get_db

# Ensure this import matches your project structure
from app.services.conversation_service import handle_incoming_message

# 🔹 SOCKET: Define the prefix but be careful with the trailing slash
router = APIRouter(prefix="/webhooks/meta", tags=["Meta Webhooks"])


# --- 1. THE HANDSHAKE (Unified GET) ---
@router.get("/")  # Maps to /webhooks/meta/
@router.get("")  # Maps to /webhooks/meta/ (Fixes 405 error)
async def verify_webhook(request: Request):
    """
    World-Class Meta Handshake: Handles both trailing slash and no-slash paths.
    """
    params = request.query_params
    expected_token = os.getenv("META_VERIFY_TOKEN", "Est8Go_Secure_2026")

    # Extract params from either format (Meta varies by region)
    mode = params.get("hub.mode") or params.get("hub_mode")
    token = params.get("hub.verify_token") or params.get("hub_verify_token")
    challenge = params.get("hub.challenge") or params.get("hub_challenge")

    if mode == "subscribe" and token == expected_token:
        print(f"✅ Meta Handshake Success: {token}")
        return PlainTextResponse(content=str(challenge))

    print(f"❌ Meta Handshake Failed: Token Mismatch. Got: {token}")
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
