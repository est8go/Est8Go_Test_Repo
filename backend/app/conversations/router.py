from __future__ import annotations
import json
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

# Database & Dependencies
from app.database.db import get_db  # Use the central one, don't redefine it
from app.tenants.deps import get_tenant_id
from app.auth.deps import get_current_user
from app.users.models import User

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
    current_user: User = Depends(get_current_user),
):
    """
    Silences the bot so a human Realtor can chat directly.
    Ensures that Realtor A cannot silence Realtor B's bot.
    """
    tenant_id = current_user.tenant_id
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No tenant associated with this account")

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


# --- ADD TO backend/app/conversations/router.py ---


@router.get("/realtor/leads", tags=["Realtor Portal"])
async def get_realtor_leads(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns all active leads and their chat status for a specific Realtor.
    """
    tenant_id = current_user.tenant_id
    if not tenant_id:
        raise HTTPException(status_code=403, detail="No tenant associated with this account")

    # Fetch conversations for this tenant, ordered by most recent activity
    convos = (
        db.query(Conversation)
        .filter(Conversation.tenant_id == tenant_id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )

    leads = []
    for c in convos:
        # We classify a lead as 'Hot' if they have preferences or reached Handoff state
        is_hot = True if c.state == "HANDOFF" or c.data_json != "{}" else False

        leads.append(
            {
                "id": c.id,
                "name": c.display_name or "New Lead",
                "phone": c.external_user_id,
                "channel": c.channel,  # 🔹 SOCKET: This tells the UI which icon to show
                "status": "HOT LEAD" if is_hot else "Browsing",
                "is_bot_active": getattr(c, "is_bot_active", True),
                "last_active": c.updated_at.strftime("%I:%M %p"),
                "prefs": json.loads(c.data_json or "{}"),
            }
        )

    return leads
