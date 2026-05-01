import os
from fastapi import APIRouter, Request, BackgroundTasks, Depends
from fastapi.responses import PlainTextResponse  # 🔹 SOCKET: Add this import

# (HTTPException is removed)
from sqlalchemy.orm import Session
from app.database.db import get_db
from app.services.conversation_service import handle_incoming_message

router = APIRouter(prefix="/webhooks/meta", tags=["Meta Webhooks"])


@router.get("/")
async def verify_webhook(request: Request):
    params = request.query_params

    # 1. Get the token from your .env
    # Note: Ensure this variable name matches what you put in the Meta Dashboard
    EXPECTED_TOKEN = os.getenv("META_VERIFY_TOKEN", "Est8Go_Secure_2026")

    # 2. Extract Meta's query parameters
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    # 3. Perform the Handshake
    if mode == "subscribe" and token == EXPECTED_TOKEN:
        print("✅ Meta Webhook Verified Successfully!")
        # 🔹 SOCKET: Return the challenge as PLAIN TEXT (This is what Meta requires)
        return PlainTextResponse(content=challenge)

    print("❌ Meta Webhook Verification Failed: Token Mismatch")
    return PlainTextResponse(content="Verification failed", status_code=403)


# 2. THE RECEIVER (Listens to messages from WhatsApp/IG/FB)
@router.post("/")
async def receive_meta_message(
    request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    data = await request.json()

    # We use 'BackgroundTasks' so Meta doesn't time out (Trust-first speed)
    background_tasks.add_task(handle_incoming_message, data, db)

    return {"status": "success"}
