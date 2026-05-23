from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date, datetime, timedelta

from app.database.db import get_db
from app.auth.deps import require_platform_user, require_superuser
from app.conversations.models import Conversation, ConversationMessage
from app.tenants.models import Tenant

router = APIRouter(prefix="/admin/conversations", tags=["Admin Conversations"])


@router.get("")
def list_conversations(
    tenant_id: Optional[int] = Query(default=None),
    phone: Optional[str] = Query(default=None),
    tenant_name: Optional[str] = Query(default=None),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    funnel_stage: Optional[str] = Query(default=None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    current_user=Depends(require_platform_user),
    db: Session = Depends(get_db),
):
    """List conversations with filters. Platform staff only."""
    q = db.query(Conversation).join(
        Tenant, Conversation.tenant_id == Tenant.id, isouter=True
    )
    if tenant_id:
        q = q.filter(Conversation.tenant_id == tenant_id)
    if phone:
        q = q.filter(Conversation.external_user_id.contains(phone))
    if tenant_name:
        q = q.filter(Tenant.business_name.ilike(f"%{tenant_name}%"))
    if date_from:
        q = q.filter(Conversation.created_at >= date_from)
    if date_to:
        q = q.filter(
            Conversation.created_at
            < datetime.combine(date_to + timedelta(days=1), datetime.min.time())
        )
    if funnel_stage:
        q = q.filter(Conversation.funnel_stage == funnel_stage)

    total = q.count()
    convos = q.order_by(Conversation.updated_at.desc()).offset(offset).limit(limit).all()

    # Pre-load tenant names to avoid N+1
    tenant_ids = list({c.tenant_id for c in convos if c.tenant_id})
    tenants_map = {}
    if tenant_ids:
        tenants_map = {
            t.id: t
            for t in db.query(Tenant).filter(Tenant.id.in_(tenant_ids)).all()
        }

    result = []
    for c in convos:
        tenant = tenants_map.get(c.tenant_id)
        msg_count = (
            db.query(ConversationMessage)
            .filter(ConversationMessage.conversation_id == c.id)
            .count()
        )
        last_msg = (
            db.query(ConversationMessage)
            .filter(ConversationMessage.conversation_id == c.id)
            .order_by(ConversationMessage.created_at.desc())
            .first()
        )
        result.append({
            "id": c.id,
            "buyer_name": c.display_name or c.external_user_id,
            "phone": c.external_user_id,
            "channel": c.channel or "whatsapp",
            "tenant_name": tenant.business_name if tenant else "—",
            "tenant_id": c.tenant_id,
            "funnel_stage": c.funnel_stage,
            "state": c.state,
            "lead_score": c.lead_score,
            "is_bot_active": c.is_bot_active,
            "message_count": msg_count,
            "last_message": (last_msg.content[:80] if last_msg and last_msg.content else None),
            "last_active_at": c.updated_at.isoformat() if c.updated_at else None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return {"total": total, "conversations": result}


@router.get("/{conversation_id}")
def get_conversation(
    conversation_id: int,
    current_user=Depends(require_platform_user),
    db: Session = Depends(get_db),
):
    """Get full conversation with messages. Platform staff only."""
    c = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Conversation not found")

    tenant = db.query(Tenant).filter(Tenant.id == c.tenant_id).first()
    messages = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at.asc())
        .all()
    )

    return {
        "id": c.id,
        "buyer_name": c.display_name or c.external_user_id,
        "phone": c.external_user_id,
        "channel": c.channel or "whatsapp",
        "tenant_name": tenant.business_name if tenant else "—",
        "funnel_stage": c.funnel_stage,
        "state": c.state,
        "lead_score": c.lead_score,
        "is_bot_active": c.is_bot_active,
        "messages": [
            {
                "id": m.id,
                "direction": "inbound" if m.role in ("user", "inbound") else "outbound",
                "body": m.content or "",
                "is_bot": m.role not in ("user", "inbound"),
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "funnel_stage_at_time": None,
            }
            for m in messages
        ],
    }


@router.get("/{conversation_id}/export", response_class=PlainTextResponse)
def export_conversation(
    conversation_id: int,
    current_user=Depends(require_superuser),
    db: Session = Depends(get_db),
):
    """Export conversation as plain text. Superuser only."""
    c = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Not found")

    tenant = db.query(Tenant).filter(Tenant.id == c.tenant_id).first()
    messages = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at.asc())
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

    lines = [
        "EST8GO CONVERSATION EXPORT",
        "═" * 50,
        f"Buyer:   {c.display_name or c.external_user_id}",
        f"Phone:   {c.external_user_id}",
        f"Tenant:  {tenant.business_name if tenant else '—'}",
        f"Channel: {c.channel or 'WhatsApp'}",
        f"Funnel:  {c.funnel_stage} | Score: {c.lead_score}/100",
        f"State:   {c.state}",
        "─" * 50,
        "",
    ]
    for m in messages:
        ts = fmt(m.created_at)
        if m.role in ("user", "inbound"):
            sender = "BUYER"
        elif m.role == "assistant":
            sender = "KORA BOT"
        else:
            sender = "AGENT"
        lines.append(f"[{ts}] {sender}: {m.content or ''}")

    lines += ["", "─" * 50, "Exported by Est8Go Super Admin"]
    return PlainTextResponse(
        content="\n".join(lines),
        headers={
            "Content-Disposition": f'attachment; filename="conversation_{conversation_id}.txt"'
        },
    )
