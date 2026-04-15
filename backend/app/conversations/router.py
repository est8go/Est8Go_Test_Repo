from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.db import SessionLocal
from app.tenants.deps import get_tenant_id
from app.services.conversation_service import (
    start_conversation_service,
    add_message_service,
)

router = APIRouter(prefix="/conversations", tags=["Conversations"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/start")
def start_conversation(
    channel: str = "web",
    external_user_id: str = "anonymous",
    display_name: str | None = None,
    tenant_id: int = Depends(get_tenant_id),
    db: Session = Depends(get_db),
):
    return start_conversation_service(
        channel,
        external_user_id,
        display_name,
        tenant_id,
        db
    )


@router.post("/{conversation_id}/message")
def add_message(
    conversation_id: int,
    text: str,
    tenant_id: int = Depends(get_tenant_id),
    db: Session = Depends(get_db),
):
    return add_message_service(
        conversation_id,
        text,
        tenant_id,
        db
    )