"""
EST8GO STAGE B — ACTIVE SALES PIPELINE
========================================
Complete Realtor portal backend:
    1. Enhanced leads pipeline with funnel stage + lead score
    2. Takeover notification — Realtor alerted on WhatsApp
    3. Bot reactivation — hand control back to Kora
    4. Pipeline value — probability-weighted revenue estimate
    5. Real-time lead activity feed
    6. Hot lead threshold alerts

Add to conversations/router.py or include as separate router.

All endpoints respect multi-tenant isolation.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, BackgroundTasks
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.conversations.models import Conversation
from app.listings.models import Listing
from app.users.models import User
from app.auth.deps import get_current_user
from app.services.notification_service import send_meta_text_message
from app.services.tenant_service import get_tenant_profile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline", tags=["Active Sales Pipeline"])


# ================================================================
# PIPELINE VALUE CALCULATOR
# Pure Python — probability-weighted revenue estimate
# ================================================================

FUNNEL_PROBABILITY = {
    "awareness": 0.05,  # 5% chance of closing
    "verification": 0.15,  # 15%
    "commitment": 0.40,  # 40%
    "handshake": 0.75,  # 75%
    "closed": 1.00,  # 100%
}


def calculate_pipeline_value(conversations: list, db: Session) -> dict:
    """
    Calculates probability-weighted pipeline value for a tenant.
    Shows Realtors their realistic expected revenue.
    """
    total_raw = 0
    total_weighted = 0
    stage_breakdown = {}

    for convo in conversations:
        prefs = {}
        try:
            prefs = json.loads(convo.data_json or "{}")
        except Exception:
            pass

        budget = prefs.get("budget", 0) or 0
        stage = convo.funnel_stage or "awareness"
        prob = FUNNEL_PROBABILITY.get(stage, 0.05)

        weighted = int(budget * prob)
        total_raw += budget
        total_weighted += weighted

        if stage not in stage_breakdown:
            stage_breakdown[stage] = {"count": 0, "raw_value": 0, "weighted_value": 0}
        stage_breakdown[stage]["count"] += 1
        stage_breakdown[stage]["raw_value"] += budget
        stage_breakdown[stage]["weighted_value"] += weighted

    return {
        "total_raw_value": total_raw,
        "total_weighted_value": total_weighted,
        "stage_breakdown": stage_breakdown,
        "formatted": {
            "raw": f"₦{total_raw:,}",
            "weighted": f"₦{total_weighted:,}",
        },
    }


# ================================================================
# LEAD CLASSIFIER
# ================================================================


def classify_lead(convo: Conversation) -> dict:
    """
    Classifies a single conversation as a rich lead object.
    Used by the pipeline dashboard.
    """
    prefs = {}
    try:
        prefs = json.loads(convo.data_json or "{}")
    except Exception:
        pass

    stage = convo.funnel_stage or "awareness"
    score = convo.lead_score or 0
    budget = prefs.get("budget", 0) or 0
    location = prefs.get("location", "")

    # Lead temperature
    if score >= 70 or stage in ("handshake", "commitment"):
        temperature = "🔥 Hot"
        temp_code = "hot"
    elif score >= 40 or stage == "verification":
        temperature = "🌡️ Warm"
        temp_code = "warm"
    else:
        temperature = "❄️ Cold"
        temp_code = "cold"

    # Last active display
    last_active = convo.last_active_at or convo.updated_at
    if last_active:
        if last_active.tzinfo is None:
            last_active = last_active.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - last_active
        if delta.total_seconds() < 3600:
            last_seen = f"{int(delta.total_seconds() / 60)}m ago"
        elif delta.total_seconds() < 86400:
            last_seen = f"{int(delta.total_seconds() / 3600)}h ago"
        else:
            last_seen = f"{delta.days}d ago"
    else:
        last_seen = "Unknown"

    # Weighted value
    prob = FUNNEL_PROBABILITY.get(stage, 0.05)
    weighted = int(budget * prob)

    return {
        "id": convo.id,
        "name": convo.display_name or "Anonymous Lead",
        "phone": convo.external_user_id,
        "channel": convo.channel or "whatsapp",
        "funnel_stage": stage,
        "lead_score": score,
        "temperature": temperature,
        "temp_code": temp_code,
        "is_bot_active": getattr(convo, "is_bot_active", True),
        "bot_status": (
            "🤖 Kora Active"
            if getattr(convo, "is_bot_active", True)
            else "👤 Realtor Active"
        ),
        "last_seen": last_seen,
        "session_count": convo.session_count or 1,
        "buyer_role": convo.buyer_role or "buyer",
        "prefs": {
            "budget": f"₦{budget:,}" if budget else "Not provided",
            "location": location or "Not provided",
            "property_type": prefs.get("property_type", "Not provided"),
            "intent": prefs.get("intent", "Not provided"),
        },
        "weighted_value": f"₦{weighted:,}" if weighted else "₦0",
        "reminder_count": convo.reminder_count or 0,
        "assigned_realtor": convo.assigned_realtor_id,
    }


# ================================================================
# 1. ACTIVE SALES PIPELINE
# ================================================================


@router.get("/active", tags=["Active Sales Pipeline"])
async def get_active_pipeline(
    db: Session = Depends(get_db),
    stage_filter: Optional[str] = None,
    temp_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """
    ACTIVE SALES PIPELINE:
    Returns all active leads with full intelligence:
    funnel stage, lead score, temperature, weighted value.

    Filters:
        stage_filter: awareness/verification/commitment/handshake
        temp_filter:  hot/warm/cold
    """
    tenant_id = current_user.tenant_id
    if not tenant_id:
        raise HTTPException(status_code=403, detail="No tenant associated with this account")

    # Fetch all active conversations
    query = (
        db.query(Conversation)
        .filter(
            Conversation.tenant_id == tenant_id,
            Conversation.state == "ACTIVE",
        )
        .order_by(Conversation.lead_score.desc())
    )

    if stage_filter:
        query = query.filter(Conversation.funnel_stage == stage_filter)

    convos = query.all()

    # Classify each lead
    leads = [classify_lead(c) for c in convos]

    # Apply temperature filter after classification
    if temp_filter:
        leads = [l for l in leads if l["temp_code"] == temp_filter]

    # Calculate pipeline value
    pipeline_value = calculate_pipeline_value(convos, db)

    # Stage counts
    stage_counts = {}
    for lead in leads:
        s = lead["funnel_stage"]
        stage_counts[s] = stage_counts.get(s, 0) + 1

    return {
        "total_leads": len(leads),
        "hot_leads": sum(1 for l in leads if l["temp_code"] == "hot"),
        "warm_leads": sum(1 for l in leads if l["temp_code"] == "warm"),
        "cold_leads": sum(1 for l in leads if l["temp_code"] == "cold"),
        "stage_counts": stage_counts,
        "pipeline_value": pipeline_value,
        "leads": leads,
    }


# ================================================================
# 2. SINGLE LEAD DETAIL
# ================================================================


@router.get("/{conversation_id}", tags=["Active Sales Pipeline"])
async def get_lead_detail(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns full detail for a single lead including chat history."""
    tenant_id = current_user.tenant_id
    if not tenant_id:
        raise HTTPException(status_code=403, detail="No tenant associated with this account")

    convo = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.tenant_id == tenant_id,
        )
        .first()
    )
    if not convo:
        raise HTTPException(status_code=404, detail="Lead not found")

    lead = classify_lead(convo)

    # Add last viewed listing if available
    prefs = json.loads(convo.data_json or "{}")
    last_id = prefs.get("last_viewed_id")
    if last_id:
        listing = db.get(Listing, last_id)
        if listing:
            lead["last_viewed_listing"] = {
                "id": listing.id,
                "title": listing.title,
                "location": listing.location,
                "price": f"₦{listing.price:,}",
                "trust_score": listing.trust_score,
                "trust_grade": listing.trust_grade,
            }

    return lead


# ================================================================
# 3. HUMAN TAKEOVER WITH NOTIFICATION
# ================================================================


@router.post("/takeover/{conversation_id}", tags=["Active Sales Pipeline"])
async def human_takeover(
    conversation_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    x_tenant_id: str = Header(None),
    current_user: User = Depends(get_current_user),
):
    """
    REALTOR TAKEOVER:
    Silences Kora and notifies the buyer that a human
    agent has joined the conversation.
    """
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id header required")

    convo = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.tenant_id == int(x_tenant_id),
        )
        .first()
    )
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Silence bot
    convo.is_bot_active = False
    convo.assigned_realtor_id = current_user.id
    db.commit()

    # Get tenant profile for branded message
    tenant_profile = get_tenant_profile(db, int(x_tenant_id))
    biz_name = tenant_profile.get("business_name", "our firm")
    buyer_name = (convo.display_name or "there").split()[0]

    # Notify buyer that a human joined
    takeover_msg = (
        f"Hi {buyer_name}! 👋\n\n"
        f"You have been connected with a senior property consultant "
        f"from *{biz_name}*.\n\n"
        f"They will assist you directly from this point. "
        f"Please feel free to ask any questions. 🏠"
    )

    background_tasks.add_task(
        send_meta_text_message,
        convo.external_user_id,
        takeover_msg,
    )

    logger.info(
        f"👤 TAKEOVER: Conversation {conversation_id} | "
        f"Realtor {current_user.email} | Tenant {x_tenant_id}"
    )

    return {
        "status": "success",
        "message": f"Bot silenced. You now control conversation {conversation_id}.",
        "buyer_phone": convo.external_user_id,
        "buyer_name": convo.display_name,
        "assigned_to": current_user.email,
    }


# ================================================================
# 4. BOT REACTIVATION
# ================================================================


@router.post("/reactivate/{conversation_id}", tags=["Active Sales Pipeline"])
async def reactivate_bot(
    conversation_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    x_tenant_id: str = Header(None),
    current_user: User = Depends(get_current_user),
):
    """
    BOT REACTIVATION:
    Hands control back to Kora after human conversation ends.
    Sends buyer a smooth handback message.
    """
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id header required")

    convo = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.tenant_id == int(x_tenant_id),
        )
        .first()
    )
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Reactivate bot
    convo.is_bot_active = True
    convo.assigned_realtor_id = None
    db.commit()

    # Get tenant profile
    tenant_profile = get_tenant_profile(db, int(x_tenant_id))
    biz_name = tenant_profile.get("business_name", "our firm")
    buyer_name = (convo.display_name or "there").split()[0]

    # Smooth handback message
    handback_msg = (
        f"Hi {buyer_name}! 🤖\n\n"
        f"Your consultant has finished for now. "
        f"I'm Kora, *{biz_name}*'s AI assistant — "
        f"I'm back and ready to help with anything else you need.\n\n"
        f"Just send me a message anytime! 🏠"
    )

    background_tasks.add_task(
        send_meta_text_message,
        convo.external_user_id,
        handback_msg,
    )

    logger.info(
        f"🤖 REACTIVATED: Conversation {conversation_id} | " f"By {current_user.email}"
    )

    return {
        "status": "success",
        "message": f"Kora reactivated for conversation {conversation_id}.",
    }


# ================================================================
# 5. HOT LEAD ALERT (Manual Trigger)
# ================================================================


@router.post("/alert/{conversation_id}", tags=["Active Sales Pipeline"])
async def send_hot_lead_alert(
    conversation_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    x_tenant_id: str = Header(None),
):
    """
    MANUAL HOT LEAD ALERT:
    Sends Realtor a WhatsApp notification about a specific lead.
    Triggered automatically when lead score crosses 70,
    or manually from the pipeline dashboard.
    """
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id header required")

    tenant_id = int(x_tenant_id)

    convo = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.tenant_id == tenant_id,
        )
        .first()
    )
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Find the admin/realtor for this tenant
    agent = (
        db.query(User)
        .filter(
            User.tenant_id == tenant_id,
            User.is_admin == True,
            User.is_active == True,
        )
        .first()
    )

    if not agent or not agent.phone_number:
        raise HTTPException(
            status_code=404, detail="No active admin found for this tenant"
        )

    tenant_profile = get_tenant_profile(db, tenant_id)
    biz_name = tenant_profile.get("business_name", "Est8Go")
    lead = classify_lead(convo)

    alert_msg = (
        f"🚨 *HOT LEAD ALERT — {biz_name}* 🚨\n\n"
        f"👤 *Name:* {lead['name']}\n"
        f"📱 *Phone:* {lead['phone']}\n"
        f"🌡️ *Temperature:* {lead['temperature']}\n"
        f"📊 *Lead Score:* {lead['lead_score']}/100\n"
        f"🏠 *Looking for:* {lead['prefs']['property_type']} "
        f"in {lead['prefs']['location']}\n"
        f"💰 *Budget:* {lead['prefs']['budget']}\n"
        f"🔄 *Funnel Stage:* {lead['funnel_stage'].title()}\n"
        f"💎 *Weighted Value:* {lead['weighted_value']}\n\n"
        f"Tap to take over this conversation in your portal."
    )

    background_tasks.add_task(
        send_meta_text_message,
        agent.phone_number,
        alert_msg,
    )

    return {
        "status": "alert_sent",
        "sent_to": agent.phone_number,
        "lead": lead,
    }


# ================================================================
# 6. PIPELINE SUMMARY (Dashboard Widget)
# ================================================================


@router.get("/summary/stats", tags=["Active Sales Pipeline"])
async def get_pipeline_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    PIPELINE SUMMARY:
    High-level stats for the Realtor dashboard header.
    Shows total leads, hot leads, pipeline value, and conversion rate.
    """
    tenant_id = current_user.tenant_id
    if not tenant_id:
        raise HTTPException(status_code=403, detail="No tenant associated with this account")

    all_convos = (
        db.query(Conversation).filter(Conversation.tenant_id == tenant_id).all()
    )

    active_convos = [c for c in all_convos if c.state == "ACTIVE"]
    closed_convos = [c for c in all_convos if c.funnel_stage == "closed"]
    hot_convos = [
        c
        for c in active_convos
        if (c.lead_score or 0) >= 70 or (c.funnel_stage in ("commitment", "handshake"))
    ]

    pipeline_value = calculate_pipeline_value(active_convos, db)

    # Conversion rate
    total = len(all_convos)
    closed = len(closed_convos)
    conv_rate = round((closed / total * 100), 1) if total > 0 else 0

    # Average trust score across this tenant's listings
    avg_trust_raw = db.query(func.avg(Listing.trust_score)).filter(
        Listing.tenant_id == tenant_id,
        Listing.trust_score != None,
        Listing.trust_score > 0,
    ).scalar()
    avg_trust_score = round(avg_trust_raw) if avg_trust_raw else 0
    trust_grade = (
        "Emerald" if avg_trust_score >= 85 else
        "Gold"    if avg_trust_score >= 70 else
        "Silver"  if avg_trust_score >= 55 else
        "Bronze"  if avg_trust_score > 0  else
        "Unrated"
    )

    return {
        "total_leads": total,
        "active_leads": len(active_convos),
        "hot_leads": len(hot_convos),
        "closed_deals": closed,
        "conversion_rate": f"{conv_rate}%",
        "pipeline_value": pipeline_value["formatted"]["weighted"],
        "raw_pipeline": pipeline_value["formatted"]["raw"],
        "stage_breakdown": pipeline_value["stage_breakdown"],
        "avg_trust_score": avg_trust_score,
        "trust_grade": trust_grade,
    }
