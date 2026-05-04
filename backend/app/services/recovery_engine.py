"""
EST8GO DROP-OFF RECOVERY ENGINE
=================================
Intelligent re-engagement sequences based on:
    - Funnel stage when buyer dropped off
    - Time since last activity
    - Lead score at drop-off
    - Number of previous reminders

Recovery Sequences:
    AWARENESS  → 3 nudges (24h, 72h, 7d)
    VERIFICATION → 2 nudges (24h, 72h) — more urgent
    COMMITMENT → 2 nudges (4h, 24h)   — hottest, act fast
    HANDSHAKE  → 1 nudge  (2h)        — inspection no-show recovery

Rules-First (80/20):
    - All timing logic = pure Python
    - All message selection = pure Python
    - GPT never called for reminders
    - Zero AI cost per recovery sequence
"""

import logging
import random
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.conversations.models import Conversation
from app.services.notification_service import send_meta_text_message
from app.services.tenant_service import get_tenant_profile

logger = logging.getLogger(__name__)


# ================================================================
# RECOVERY MESSAGE TEMPLATES
# Per funnel stage, per reminder sequence position
# ================================================================

RECOVERY_MESSAGES = {
    # --- AWARENESS STAGE (Buyer just said hi, gave no data yet) ---
    "awareness": [
        # Nudge 1 — 24 hours after drop-off
        (
            "Hi {name}! 👋\n\n"
            "I noticed we got disconnected earlier. "
            "At *{biz_name}*, we have fresh verified listings arriving daily — "
            "GPS-checked, AI-audited, and document-verified.\n\n"
            "What location are you targeting? I'll pull the best options for you. 🏠"
        ),
        # Nudge 2 — 72 hours after drop-off
        (
            "Hello {name}! 🏠\n\n"
            "The property market moves fast in Nigeria — "
            "verified deals don't stay available for long.\n\n"
            "Tell me your preferred area and budget and I'll show you "
            "what's currently in our vault. Takes less than 2 minutes. ⚡"
        ),
        # Nudge 3 — 7 days after drop-off (final)
        (
            "Hi {name}, one last check-in from *{biz_name}*. 🙏\n\n"
            "We respect your time — so this is our final message unless you reach out.\n\n"
            "Whenever your property search is ready, our verified vault will be here. "
            "Just say *Hi* to reconnect anytime. ✅"
        ),
    ],
    # --- VERIFICATION STAGE (Buyer gave location OR budget, not both) ---
    "verification": [
        # Nudge 1 — 24 hours
        (
            "Hello {name}! 👋\n\n"
            "We were just getting to the good part of your property search. 🔍\n\n"
            "I have verified listings matching your criteria — "
            "GPS-confirmed and AI-audited.\n\n"
            "Can you share {missing_field} so I can pull your exact matches?"
        ),
        # Nudge 2 — 72 hours (final for this stage)
        (
            "Hi {name}! ⏰\n\n"
            "Quick update from *{biz_name}*: new verified properties "
            "have just been added to our vault in your area of interest.\n\n"
            "Share your {missing_field} and I'll send you the top 5 matches immediately. 🏠"
        ),
    ],
    # --- COMMITMENT STAGE (Buyer gave both location AND budget) ---
    "commitment": [
        # Nudge 1 — 4 hours (urgent — they were close to buying)
        (
            "Hi {name}! 🔥\n\n"
            "You were this close to securing a verified property. 📍\n\n"
            "The listing I showed you is still available — but at this trust grade, "
            "it won't last long.\n\n"
            "Would you like to schedule a site inspection today? "
            "Just say *Yes* and I'll connect you with the agent. ⚡"
        ),
        # Nudge 2 — 24 hours (final for this stage)
        (
            "Hello {name}. 🏠\n\n"
            "I want to make sure you don't miss the verified property we found for you.\n\n"
            "At *{biz_name}*, Emerald-rated listings move quickly — "
            "they're the only ones with GPS verification, AI audit, and clean documents.\n\n"
            "Say *Yes* to schedule your inspection or *New Search* to explore other options."
        ),
    ],
    # --- HANDSHAKE STAGE (Inspection was scheduled, buyer no-showed) ---
    "handshake": [
        # Nudge 1 — 2 hours after scheduled inspection
        (
            "Hi {name}! 👋\n\n"
            "We noticed you may have missed the site inspection today. "
            "No problem at all — things come up!\n\n"
            "Our agent is available to reschedule at your convenience. "
            "What day works best for you? 📅"
        ),
    ],
    # --- HIGH LEAD SCORE (score >= 70, any stage) ---
    "high_value": [
        # Special sequence for high-intent buyers
        (
            "Hi {name}! 🌟\n\n"
            "Based on our conversation, you're looking for exactly what "
            "*{biz_name}* specialises in.\n\n"
            "I've reserved a *Priority Viewing* slot for you — "
            "this means our lead agent will personally guide your site inspection.\n\n"
            "Would you like to confirm your slot? Just say *Yes*. 🏠"
        ),
    ],
}


# ================================================================
# TIMING RULES (Pure Python — no AI)
# ================================================================

REMINDER_TIMING = {
    # funnel_stage: [(hours_after_dropoff, max_reminders)]
    "awareness": [(24, 1), (72, 2), (168, 3)],  # 1d, 3d, 7d
    "verification": [(24, 1), (72, 2)],  # 1d, 3d
    "commitment": [(4, 1), (24, 2)],  # 4h, 1d
    "handshake": [(2, 1)],  # 2h
    "closed": [],  # no reminders for closed
}


def should_send_reminder(convo: Conversation) -> tuple:
    """
    Determines if a conversation should receive a reminder.

    Returns:
        (should_send: bool, nudge_index: int, reason: str)
    """
    # Never remind if bot is inactive (Realtor took over)
    if not getattr(convo, "is_bot_active", True):
        return False, 0, "Bot inactive"

    # Never remind if closed
    if convo.funnel_stage == "closed":
        return False, 0, "Conversation closed"

    stage = convo.funnel_stage or "awareness"
    timing = REMINDER_TIMING.get(stage, [])
    count = convo.reminder_count or 0
    score = convo.lead_score or 0

    # Max reminders reached for this stage
    if count >= len(timing):
        return False, 0, f"Max reminders ({count}) reached for {stage}"

    # Check timing — has enough time passed since last activity?
    last_active = convo.last_active_at or convo.updated_at
    if not last_active:
        return False, 0, "No activity timestamp"

    now = datetime.now(timezone.utc)

    # Handle timezone-naive datetimes
    if last_active.tzinfo is None:
        last_active = last_active.replace(tzinfo=timezone.utc)

    hours_since = (now - last_active).total_seconds() / 3600
    required_hours = timing[count][0]

    if hours_since < required_hours:
        return False, 0, f"Too soon ({hours_since:.1f}h < {required_hours}h required)"

    # High-value override — use special template
    nudge_index = count
    if score >= 70:
        return True, -1, f"High-value buyer (score={score})"

    return True, nudge_index, f"Stage={stage}, Nudge={count+1}"


def build_reminder_message(
    convo: Conversation,
    nudge_index: int,
    name: str,
    biz_name: str,
) -> str:
    """
    Builds the personalised reminder message.
    Fills in missing_field dynamically based on prefs.
    """
    import json

    stage = convo.funnel_stage or "awareness"
    prefs = {}
    try:
        prefs = json.loads(convo.data_json or "{}")
    except Exception:
        pass

    # Determine missing field for verification stage
    missing_field = "budget" if prefs.get("location") else "preferred location"

    # High-value buyers get special template
    if nudge_index == -1:
        templates = RECOVERY_MESSAGES.get("high_value", [])
    else:
        templates = RECOVERY_MESSAGES.get(stage, RECOVERY_MESSAGES["awareness"])
        nudge_index = min(nudge_index, len(templates) - 1)

    if not templates:
        return (
            f"Hi {name}! 👋\n\n"
            f"Just checking in from *{biz_name}*. "
            f"Are you still looking for a property? "
            f"I'm here whenever you're ready. 🏠"
        )

    template = templates[nudge_index]
    return template.format(
        name=name,
        biz_name=biz_name,
        missing_field=missing_field,
    )


# ================================================================
# MAIN RECOVERY ENGINE
# ================================================================


async def run_dropoff_recovery(db: Session):
    """
    Master recovery function.
    Called every hour by run_reminders.py.

    Scans all active conversations, identifies drop-offs,
    sends personalised recovery messages per funnel stage.
    """
    logger.info("🔄 DROP-OFF RECOVERY: Scanning conversations...")

    try:
        # Fetch all active conversations that haven't been closed
        active_convos = (
            db.query(Conversation)
            .filter(
                Conversation.state == "ACTIVE",
                Conversation.is_bot_active == True,
                Conversation.funnel_stage != "closed",
            )
            .all()
        )

        sent = 0
        skipped = 0
        errors = 0

        for convo in active_convos:
            try:
                should_send, nudge_index, reason = should_send_reminder(convo)

                if not should_send:
                    skipped += 1
                    continue

                # Get tenant profile for branded messaging
                tenant_profile = get_tenant_profile(db, convo.tenant_id)
                biz_name = tenant_profile.get("business_name", "our firm")
                name = (convo.display_name or "there").split()[0]

                # Build personalised message
                message = build_reminder_message(convo, nudge_index, name, biz_name)

                # Send via Meta
                await send_meta_text_message(convo.external_user_id, message)

                # Update conversation
                convo.reminder_count = (convo.reminder_count or 0) + 1
                convo.last_reminder_sent_at = datetime.now(timezone.utc)
                db.commit()

                sent += 1
                logger.info(
                    f"✅ RECOVERY: Sent to {convo.external_user_id} | "
                    f"Stage={convo.funnel_stage} | "
                    f"Score={convo.lead_score} | "
                    f"Nudge={nudge_index} | {reason}"
                )

            except Exception as e:
                errors += 1
                logger.error(f"❌ RECOVERY ERROR for conversation {convo.id}: {e}")
                db.rollback()

        logger.info(
            f"🔄 RECOVERY COMPLETE: "
            f"{sent} sent | {skipped} skipped | {errors} errors"
        )
        return {"sent": sent, "skipped": skipped, "errors": errors}

    except Exception as e:
        logger.error(f"❌ CRITICAL RECOVERY ERROR: {e}", exc_info=True)
        db.rollback()
        return {"sent": 0, "skipped": 0, "errors": 1}


# ================================================================
# PRIORITY ESCALATION
# (High-score leads get Realtor notified too)
# ================================================================


async def escalate_high_value_leads(db: Session):
    """
    Finds leads with score >= 70 that have gone cold
    and alerts the Realtor directly.
    Runs alongside the standard recovery engine.
    """
    from app.services.notification_service import alert_realtor_of_lead
    import json

    now = datetime.now(timezone.utc)
    threshold = now - timedelta(hours=6)

    high_value = (
        db.query(Conversation)
        .filter(
            Conversation.lead_score >= 70,
            Conversation.state == "ACTIVE",
            Conversation.funnel_stage.in_(["commitment", "handshake"]),
        )
        .all()
    )

    escalated = 0
    for convo in high_value:
        last_active = convo.last_active_at or convo.updated_at
        if not last_active:
            continue

        if last_active.tzinfo is None:
            last_active = last_active.replace(tzinfo=timezone.utc)

        if last_active > threshold:
            continue  # still recent — skip

        try:
            prefs = json.loads(convo.data_json or "{}")
            last_id = prefs.get("last_viewed_id")

            if last_id:
                tenant_profile = get_tenant_profile(db, convo.tenant_id)
                biz_name = tenant_profile.get("business_name", "Est8Go")

                await alert_realtor_of_lead(
                    db, last_id, convo.external_user_id, biz_name
                )
                escalated += 1
                logger.info(
                    f"🚨 ESCALATED: Lead {convo.external_user_id} | "
                    f"Score={convo.lead_score} | "
                    f"Stage={convo.funnel_stage}"
                )

        except Exception as e:
            logger.error(f"Escalation error for {convo.id}: {e}")

    logger.info(f"🚨 ESCALATION: {escalated} high-value leads escalated to Realtors")
    return escalated
