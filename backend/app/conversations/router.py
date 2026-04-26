from __future__ import annotations
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

# Database & Dependencies
from app.database.db import get_db  # Use the central one, don't redefine it
from app.tenants.deps import get_tenant_id

# Models & Services
from app.conversations.models import Conversation
from app.services.conversation_service import (
    start_conversation_service,
    add_message_service,
)

router = APIRouter(prefix="/conversations", tags=["Conversations"])

# ---------------------------------------------------------
# WEB/APP CONVERSATION ENDPOINTS
# ---------------------------------------------------------


@router.post("/start")
def start_conversation(
    channel: str = "web",
    external_user_id: str = "anonymous",
    display_name: Optional[str] = None,
    tenant_id: int = Depends(get_tenant_id),
    db: Session = Depends(get_db),
):
    """Initializes a new session for web or app users."""
    return start_conversation_service(
        channel, external_user_id, display_name, tenant_id, db
    )


@router.post("/{conversation_id}/message")
def add_message(
    conversation_id: int,
    text: str,
    tenant_id: int = Depends(get_tenant_id),
    db: Session = Depends(get_db),
):
    """Processes a message through the Rules-First state machine."""
    return add_message_service(conversation_id, text, tenant_id, db)


# ---------------------------------------------------------
# HUMAN-IN-THE-LOOP (HITL) TAKEOVER
# ---------------------------------------------------------


@router.post("/takeover/{user_phone}")
async def human_takeover(
    user_phone: str,
    db: Session = Depends(get_db),
    x_tenant_id: Optional[str] = Header(None),  # Header now correctly imported
):
    """
    Silences the bot so a human Realtor can chat directly.
    Ensures that Realtor A cannot silence Realtor B's bot.
    """
    # 1. Convert Header to Integer (since your tenant IDs are integers)
    try:
        tenant_id = int(x_tenant_id) if x_tenant_id else 1
    except ValueError:
        tenant_id = 1

    # 2. Find the conversation for this specific user AND specific tenant
    convo = (
        db.query(Conversation)
        .filter(
            Conversation.external_user_id == user_phone,
            Conversation.tenant_id == tenant_id,
        )
        .first()
    )

    if not convo:
        # HTTPException now correctly imported
        raise HTTPException(
            status_code=404, detail="Conversation not found for this tenant."
        )

    # 3. Silence the Bot
    # This flag is checked in conversation_service.py before every bot reply
    convo.is_bot_active = False
    db.commit()

    return {
        "status": "success",
        "message": f"Bot silenced for {user_phone}. Human Realtor is now in control.",
    }
