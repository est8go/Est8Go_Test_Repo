import os
from fastapi import APIRouter, Request, BackgroundTasks, Depends
from fastapi.responses import PlainTextResponse  # 🔹 SOCKET: Add this import

# (HTTPException is removed)
from sqlalchemy.orm import Session
from app.database.db import get_db
from app.services.conversation_service import handle_incoming_message

router = APIRouter(prefix="/webhooks/meta", tags=["Meta Webhooks"])


router.get("/")


async def verify_webhook(request: Request):
    """
    World-Class Meta Handshake: Returns hub.challenge as raw text.
    """
    params = request.query_params

    # Use the corporate Est8Go token
    expected_token = os.getenv("META_VERIFY_TOKEN", "Est8Go_Secure_2026")

    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    # Meta sometimes sends the params with underscores too, let's be safe
    if not mode:
        mode = params.get("hub_mode")
    if not token:
        token = params.get("hub_verify_token")
    if not challenge:
        challenge = params.get("hub_challenge")

    if mode == "subscribe" and token == expected_token:
        print(f"✅ Meta Handshake Success! Sending challenge: {challenge}")
        # 🔹 SOCKET: This MUST be a string in PlainTextResponse
        return PlainTextResponse(content=str(challenge))

    print(f"❌ Meta Handshake Failed. Received token: {token}")
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
