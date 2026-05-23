from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import date, datetime, timedelta
from typing import Optional

from app.database.db import get_db
from app.users.models import User
from app.tenants.models import Tenant
from app.conversations.models import Conversation, ConversationMessage
from app.auth.deps import require_platform_user, require_superuser

router = APIRouter(prefix="/admin/conversations", tags=["Admin Conversations"])


@router.get("")
def list_conversations(
    tenant_id: Optional[int] = Query(default=None),
    phone: Optional[str] = Query(default=None),
    tenant_name: Optional[str] = Query(default=None),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    funnel_stage: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_platform_user),
    db: Session = Depends(get_db),
):
    """List conversations with optional filters. Platform staff only."""
    query = db.query(Conversation)

    if tenant_id:
        query = query.filter(Conversation.tenant_id == tenant_id)
    if phone:
        query = query.filter(Conversation.external_user_id.contains(phone))
    if funnel_stage:
        query = query.filter(Conversation.funnel_stage == funnel_stage)
    if date_from:
        query = query.filter(Conversation.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        query = query.filter(Conversation.created_at < datetime.combine(date_to + timedelta(days=1), datetime.min.time()))

    query = query.order_by(desc(Conversation.last_active_at))
    convos = query.offset(offset).limit(limit).all()

    # Pre-load tenants in one query to avoid N+1
    tenant_ids = list({c.tenant_id for c in convos if c.tenant_id})
    tenants_map = {}
    if tenant_ids:
        tenants_map = {
            t.id: t.name
            for t in db.query(Tenant).filter(Tenant.id.in_(tenant_ids)).all()
        }

    result = []
    for c in convos:
        tenant_name_resolved = tenants_map.get(c.tenant_id, "Unknown")

        # Filter by tenant name substring if requested
        if tenant_name and tenant_name.lower() not in tenant_name_resolved.lower():
            continue

        msg_count = db.query(func.count(ConversationMessage.id)).filter(
            ConversationMessage.conversation_id == c.id
        ).scalar() or 0

        last_msg = (
            db.query(ConversationMessage)
            .filter(ConversationMessage.conversation_id == c.id)
            .order_by(desc(ConversationMessage.created_at))
            .first()
        )

        result.append({
            "id":            c.id,
            "tenant_id":     c.tenant_id,
            "tenant_name":   tenant_name_resolved,
            "buyer_name":    c.display_name or "Unknown Buyer",
            "phone":         c.external_user_id,
            "channel":       c.channel,
            "funnel_stage":  c.funnel_stage,
            "lead_score":    c.lead_score,
            "is_bot_active": c.is_bot_active,
            "message_count": msg_count,
            "last_message":  (last_msg.content[:120] if last_msg and last_msg.content else None),
            "last_active_at": c.last_active_at.isoformat() if c.last_active_at else None,
            "created_at":    c.created_at.isoformat() if c.created_at else None,
        })

    return result


@router.get("/{conversation_id}")
def get_conversation(
    conversation_id: int,
    current_user: User = Depends(require_platform_user),
    db: Session = Depends(get_db),
):
    """Get full conversation with all messages ordered by time."""
    convo = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    tenant = db.query(Tenant).filter(Tenant.id == convo.tenant_id).first()

    messages = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at)
        .all()
    )

    msgs_out = []
    for m in messages:
        is_inbound = m.role == "user"
        msgs_out.append({
            "id":                  m.id,
            "direction":           "inbound" if is_inbound else "outbound",
            "body":                m.content or "",
            "is_bot":              m.role == "assistant",
            "created_at":          m.created_at.isoformat() if m.created_at else None,
            "funnel_stage_at_time": None,
        })

    return {
        "id":            convo.id,
        "tenant_id":     convo.tenant_id,
        "tenant_name":   tenant.name if tenant else "Unknown",
        "buyer_name":    convo.display_name or "Unknown Buyer",
        "phone":         convo.external_user_id,
        "channel":       convo.channel or "whatsapp",
        "funnel_stage":  convo.funnel_stage,
        "lead_score":    convo.lead_score,
        "is_bot_active": convo.is_bot_active,
        "created_at":    convo.created_at.isoformat() if convo.created_at else None,
        "last_active_at": convo.last_active_at.isoformat() if convo.last_active_at else None,
        "messages":      msgs_out,
    }


@router.get("/{conversation_id}/export", response_class=PlainTextResponse)
def export_conversation(
    conversation_id: int,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    """Export conversation as plain text. Superuser only."""
    convo = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    tenant = db.query(Tenant).filter(Tenant.id == convo.tenant_id).first()

    messages = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at)
        .all()
    )

    def fmt(dt) -> str:
        if not dt:
            return "—"
        if isinstance(dt, str):
            try:
                dt = datetime.fromisoformat(dt)
            except Exception:
                return dt
        return dt.strftime("%H:%M %d/%m/%Y")

    first_ts = messages[0].created_at if messages else convo.created_at
    last_ts  = messages[-1].created_at if messages else convo.last_active_at

    lines = [
        "EST8GO CONVERSATION EXPORT",
        f"Buyer: {convo.display_name or 'Unknown'} | Phone: {convo.external_user_id or '—'}",
        f"Tenant: {tenant.name if tenant else 'Unknown'}",
        f"Channel: {(convo.channel or 'WhatsApp').upper()}",
        f"Period: {fmt(first_ts)} → {fmt(last_ts)}",
        "─" * 41,
    ]

    for m in messages:
        sender = "BOT" if m.role == "assistant" else "BUYER"
        lines.append(f"[{fmt(m.created_at)}] {sender}: {m.content or ''}")

    lines += [
        "─" * 41,
        f"Funnel: {convo.funnel_stage or '—'} | Score: {convo.lead_score or 0}/100",
    ]

    return PlainTextResponse(
        content="\n".join(lines),
        headers={
            "Content-Disposition": f'attachment; filename="conversation_{conversation_id}.txt"'
        },
    )
