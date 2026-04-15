import os
from fastapi import APIRouter, Request, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.db import get_db
from app.services.conversation_service import handle_incoming_message

router = APIRouter(prefix="/webhooks/meta", tags=["Meta Webhooks"])


# 1. THE VERIFICATION (Meta needs this to trust your server)
@router.get("/")
async def verify_webhook(request: Request):
    params = request.query_params
    # You will put this same token in the Meta Developer Portal
    VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "BraviesTrust2024")

    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == VERIFY_TOKEN
    ):
        return int(params.get("hub.challenge"))
    return "Verification failed"


# 2. THE RECEIVER (Listens to messages from WhatsApp/IG/FB)
@router.post("/")
async def receive_meta_message(
    request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    data = await request.json()

    # We use 'BackgroundTasks' so Meta doesn't time out (Trust-first speed)
    background_tasks.add_task(handle_incoming_message, data, db)

    return {"status": "success"}
