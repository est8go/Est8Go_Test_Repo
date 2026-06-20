"""
EST8GO DROP-OFF RECOVERY ENGINE
=================================
Intelligent re-engagement sequences based on:
    - Funnel stage when buyer dropped off
    - Time since last activity
    - Lead score at drop-off
    - Number of previous reminders

Recovery Sequences:
    AWARENESS    → 3 nudges (4h, 12h, 24h)
    VERIFICATION → 2 nudges (2h, 8h)   — closer to buying
    COMMITMENT   → 2 nudges (1h, 4h)   — hottest, act fast
    HANDSHAKE    → 1 nudge  (1h)       — inspection no-show recovery

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
from app.services.meta_sender_service import (
    send_meta_template,
    get_tenant_whatsapp_credentials,
)

logger = logging.getLogger(__name__)


# ================================================================
# RECOVERY MESSAGE TEMPLATES
# Per funnel stage, per reminder sequence position
# ================================================================

RECOVERY_MESSAGES = {
    # --- AWARENESS STAGE (Buyer just said hi, gave no data yet) ---
    "awareness": [
        # Nudge 1 — 4h after drop-off
        (
            "Hi {name}! 👋\n\n"
            "Just checking in — we were having a great conversation about your property search a few hours ago. "
            "At *{biz_name}*, we have fresh verified listings arriving daily — "
            "GPS-checked, AI-audited, and document-verified.\n\n"
            "What location are you targeting? I'll pull the best options for you. 🏠"
        ),
        # Nudge 2 — 12h after drop-off
        (
            "Hello {name}! 🏠\n\n"
            "The property market moves fast in Nigeria — "
            "verified deals don't stay available for long.\n\n"
            "Tell me your preferred area and budget and I'll show you "
            "what's currently in our vault. Takes less than 2 minutes. ⚡"
        ),
        # Nudge 3 — 24h after drop-off
        (
            "Hi {name}, one last check-in from *{biz_name}*. 🙏\n\n"
            "We respect your time — so this is our final message unless you reach out.\n\n"
            "Whenever your property search is ready, our verified vault will be here. "
            "Just say *Hi* to reconnect anytime. ✅"
        ),
        # Nudge 4 — 7 days (final)
        (
            "Hi {name}. 🙏\n\n"
            "This is our final message from *{biz_name}*.\n\n"
            "We completely understand — life gets busy and "
            "property decisions take time.\n\n"
            "Whenever you're ready to find a verified, "
            "GPS-confirmed property in Nigeria, just send "
            "us a message and we'll be ready for you. ✅\n\n"
            "Wishing you all the best. 🏠"
        ),
    ],
    # --- VERIFICATION STAGE (Buyer gave location OR budget, not both) ---
    "verification": [
        # Nudge 1 — 2h after drop-off (closer to buying — act fast)
        (
            "Hi {name}! 🔍\n\n"
            "You were in the middle of qualifying a property just a couple of hours ago — "
            "and I have verified listings that match what you're looking for.\n\n"
            "Can you share your {missing_field} so I can send your exact matches right now?"
        ),
        # Nudge 2 — 8h after drop-off (final — property may be gone)
        (
            "Hi {name}! ⏰\n\n"
            "Heads up from *{biz_name}*: verified properties at your price point "
            "don't stay available long — some have already been taken today.\n\n"
            "Share your {missing_field} now and I'll lock in your top matches before they're gone. 🏠"
        ),
    ],
    # --- COMMITMENT STAGE (Buyer gave both location AND budget) ---
    "commitment": [
        # Nudge 1 — 1h after drop-off (very urgent — they were ready to buy)
        (
            "Hi {name}! 🔥\n\n"
            "You were this close — just an hour ago you were ready to secure a verified property.\n\n"
            "That listing is still available *right now*, but at this trust grade it will go fast.\n\n"
            "Say *Yes* to schedule your site inspection today. Our agent is standing by. ⚡"
        ),
        # Nudge 2 — 4h after drop-off (final — last chance)
        (
            "Hello {name}. 🏠\n\n"
            "*Last chance* — the verified property we found for you is still available, "
            "but we can't hold it beyond today.\n\n"
            "At *{biz_name}*, Emerald-rated listings move quickly — GPS-verified, AI-audited, "
            "and clean documents.\n\n"
            "Say *Yes* to claim your inspection slot, or *New Search* to explore alternatives."
        ),
    ],
    # --- HANDSHAKE STAGE (Inspection was scheduled, buyer no-showed) ---
    "handshake": [
        # Nudge 1 — 1h after missed inspection (reschedule same day)
        (
            "Hi {name}! 👋\n\n"
            "It looks like you missed the site inspection today — no worries at all!\n\n"
            "Our agent has a slot available *later today* if you'd like to reschedule. "
            "What time works for you? 📅"
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
    # funnel_stage: [(hours_after_dropoff, nudge_number)]
    "awareness":    [(4, 1), (24, 2), (48, 3), (168, 4)],  # 4h, 24h, 48h, 7d
    "verification": [(2, 1), (12, 2), (24, 3)],             # 2h, 12h, 24h
    "commitment":   [(1, 1), (4, 2), (12, 3)],              # 1h, 4h, 12h
    "handshake":    [(1, 1), (4, 2)],                       # 1h, 4h
    "closed":       [],
}


_SPEED_MULTIPLIER = {"gentle": 2.0, "standard": 1.0, "aggressive": 0.5}


def is_good_send_time(window_start: int = 7, window_end: int = 21) -> bool:
    """
    Only send recovery messages within the tenant's configured send window.
    Nigerian timezone WAT = UTC+1. Defaults: 7am–9pm WAT.
    """
    wat = timezone(timedelta(hours=1))
    now = datetime.now(wat)
    return window_start <= now.hour <= window_end


STOP_KEYWORDS = [
    "stop", "no", "leave me", "not interested",
    "don't contact", "do not contact", "unsubscribe",
    "remove me", "cancel", "quit", "bye", "goodbye",
    "go away", "enough", "too many messages",
    "stop messaging", "don't message", "block",
    # Pidgin Nigerian
    "abeg no", "no vex", "i no want", "commot",
    "no disturb", "i don see am",
]


async def check_buyer_opted_out(
    convo_id: int,
    db: Session,
) -> bool:
    """
    Check if buyer has sent any stop/opt-out keywords
    in their recent messages. If yes, halt all recovery.
    """
    try:
        from app.conversations.models import ConversationMessage
        recent = (
            db.query(ConversationMessage)
            .filter(
                ConversationMessage.conversation_id == convo_id,
                ConversationMessage.role.in_(["user", "inbound"]),
            )
            .order_by(ConversationMessage.created_at.desc())
            .limit(10)
            .all()
        )
        for msg in recent:
            content = (msg.content or "").lower().strip()
            for keyword in STOP_KEYWORDS:
                if keyword in content:
                    return True
        return False
    except Exception as e:
        logger.error(f"Opt-out check failed: {e}")
        return False


def should_send_reminder(
    convo: Conversation,
    speed: str = "standard",
    window_start: int = 7,
    window_end: int = 21,
) -> tuple:
    """
    Determines if a conversation should receive a reminder.

    Returns:
        (should_send: bool, nudge_index: int, reason: str)
    """
    if not getattr(convo, "is_bot_active", True):
        return False, 0, "Bot inactive"

    if convo.funnel_stage == "closed":
        return False, 0, "Conversation closed"

    if not is_good_send_time(window_start, window_end):
        return False, 0, f"Outside send window ({window_start}:00–{window_end}:00 WAT)"

    stage = convo.funnel_stage or "awareness"
    timing = REMINDER_TIMING.get(stage, [])
    count = convo.reminder_count or 0
    score = convo.lead_score or 0

    if count >= len(timing):
        return False, 0, f"Max reminders ({count}) reached for {stage}"

    last_active = convo.last_active_at or convo.updated_at
    if not last_active:
        return False, 0, "No activity timestamp"

    now = datetime.now(timezone.utc)
    if last_active.tzinfo is None:
        last_active = last_active.replace(tzinfo=timezone.utc)

    hours_since = (now - last_active).total_seconds() / 3600
    multiplier = _SPEED_MULTIPLIER.get(speed, 1.0)
    required_hours = max(0.5, timing[count][0] * multiplier)

    if hours_since < required_hours:
        return False, 0, f"Too soon ({hours_since:.1f}h < {required_hours:.1f}h required)"

    nudge_index = count
    if score >= 70:
        return True, -1, f"High-value buyer (score={score})"

    return True, nudge_index, f"Stage={stage}, Nudge={count+1}, Speed={speed}"


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

    # Build search context string from previous preferences
    location  = (prefs.get("location") or "").title()
    prop_type = (prefs.get("property_type") or "").title()
    budget    = prefs.get("budget_max") or prefs.get("budget")
    search_context = ""
    if prop_type or location:
        _parts = []
        if prop_type:
            _parts.append(prop_type)
        if location:
            _parts.append(f"in {location}")
        if budget:
            try:
                _b = int(budget)
                if _b >= 1_000_000:
                    _parts.append(f"around ₦{_b / 1_000_000:.0f}M")
            except (ValueError, TypeError):
                pass
        search_context = " ".join(_parts)

    # Awareness nudge 1 with context — override template if context available
    if stage == "awareness" and nudge_index == 0 and search_context:
        return (
            f"Hi {name}! 👋\n\n"
            f"Just checking in — you were looking for "
            f"*{search_context}* a few hours ago.\n\n"
            f"We have verified listings that match your criteria. "
            f"Would you like to continue your search? 🏠"
        )

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
# APPROVED-TEMPLATE SELECTOR
# Maps a conversation to one of the 5 approved reengaged_* templates.
# Precedence: properties_images > high_values > stage.
# Never uses a stock image — drops to a name-only template instead.
# ================================================================


def choose_recovery_template(convo, score, db) -> dict:
    """
    Returns {"name", "body_params", "header_image_url"} for the approved
    template to send, or None to skip this conversation.

    Precedence:
      1. reengaged_properties_images — needs last_viewed_id + area + a REAL
         listing image. Missing any of the three → fall through (never a
         stock image).
      2. reengaged_high_values — score >= 70 (any stage).
      3. stage template — awareness / verification / commitment.
      handshake / closed / unknown → None (no recovery).
    """
    import json
    from app.listings.models import Listing

    # Only these three stages are recoverable. Guard FIRST so a high-value
    # (score>=70) closed/handshake/unknown conversation can't slip through
    # the high_value branch below. (Decisions: drop handshake; closed → None.)
    if convo.funnel_stage not in ("awareness", "verification", "commitment"):
        return None

    _data = {}
    try:
        _data = json.loads(convo.data_json or "{}")
    except Exception:
        _data = {}

    _name = (convo.display_name or "there").split()[0] if convo.display_name else "there"
    _area = (_data.get("location") or "").title()
    _last_id = _data.get("last_viewed_id")

    # 1. properties_images — needs last_viewed_id + area + a real image
    if _last_id and _area:
        _img_url = None
        try:
            _lst = db.get(Listing, int(_last_id))
            if _lst:
                _img = next(
                    (i for i in _lst.images if getattr(i, "is_main", False)),
                    None,
                ) or (_lst.images[0] if _lst.images else None)
                if _img and _img.url:
                    _img_url = _img.url
        except Exception:
            _img_url = None
        if _img_url:
            return {
                "name": "reengaged_properties_images",
                "body_params": [_name, _area],
                "header_image_url": _img_url,
            }
        # no real image → fall through (NEVER a stock image)

    # 2. high_value — score >= 70
    if score and score >= 70:
        return {
            "name": "reengaged_high_values",
            "body_params": [_name],
            "header_image_url": None,
        }

    # 3. stage template
    _stage_map = {
        "awareness": "reengaged_awareness",
        "verification": "reengaged_verifications",
        "commitment": "reengaged_commitments",
    }
    _tmpl = _stage_map.get(convo.funnel_stage)
    if _tmpl:
        return {
            "name": _tmpl,
            "body_params": [_name],
            "header_image_url": None,
        }

    # handshake / closed / unknown → no recovery
    return None


# ================================================================
# MAIN RECOVERY ENGINE
# ================================================================


def _get_tenant_recovery_settings(db: Session, tenant_id: int, cache: dict) -> dict:
    """Returns recovery settings for a tenant, cached per run to avoid repeat queries."""
    if tenant_id not in cache:
        try:
            from app.company_profiles.models import CompanyProfile
            profile = (
                db.query(CompanyProfile)
                .filter(CompanyProfile.tenant_id == tenant_id)
                .first()
            )
            if profile:
                cache[tenant_id] = {
                    "speed": getattr(profile, "recovery_speed", "standard") or "standard",
                    "window_start": getattr(profile, "send_window_start", 7) if profile.send_window_start is not None else 7,
                    "window_end": getattr(profile, "send_window_end", 21) if profile.send_window_end is not None else 21,
                }
            else:
                cache[tenant_id] = {"speed": "standard", "window_start": 7, "window_end": 21}
        except Exception:
            cache[tenant_id] = {"speed": "standard", "window_start": 7, "window_end": 21}
    return cache[tenant_id]


async def run_dropoff_recovery(db: Session):
    """
    Master recovery function.
    Called every hour by run_reminders.py.

    Scans all active conversations, identifies drop-offs,
    sends personalised recovery messages per funnel stage.
    """
    # ── CODE-LEVEL KILL SWITCH (default OFF) ──────────────────────
    # Recovery stays paused unless RECOVERY_ENABLED is EXPLICITLY "true".
    # Missing/malformed env, or any redeploy, leaves it OFF — safe by
    # default. Must be before any DB query or send.
    import os
    if os.getenv("RECOVERY_ENABLED", "false").lower() != "true":
        print("[recovery] RECOVERY_ENABLED is not 'true' — skipping (code-level pause).")
        return {"sent": 0, "skipped": 0, "errors": 0}

    logger.info("🔄 DROP-OFF RECOVERY: Scanning conversations...")

    try:
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
        _settings_cache: dict = {}

        for convo in active_convos:
            try:
                settings = _get_tenant_recovery_settings(db, convo.tenant_id, _settings_cache)
                should_send, nudge_index, reason = should_send_reminder(
                    convo,
                    speed=settings["speed"],
                    window_start=settings["window_start"],
                    window_end=settings["window_end"],
                )

                if not should_send:
                    skipped += 1
                    continue

                # Check if buyer opted out
                opted_out = await check_buyer_opted_out(convo.id, db)
                if opted_out:
                    convo.is_bot_active = False
                    db.commit()
                    logger.info(
                        f"🚫 OPT-OUT: {convo.external_user_id} "
                        f"requested no more messages. Bot deactivated."
                    )
                    skipped += 1
                    continue

                # Choose the right APPROVED template (precedence +
                # no-stock-image fallback; None = skip this conversation)
                score = convo.lead_score or 0
                _spec = choose_recovery_template(convo, score, db)
                if not _spec:
                    skipped += 1
                    continue

                # Per-tenant credentials — send from the tenant's OWN
                # number/token, never the global number.
                _pid, _token, _ = get_tenant_whatsapp_credentials(
                    db, convo.tenant_id
                )

                _ok = await send_meta_template(
                    convo.external_user_id,
                    _spec["name"],
                    body_params=_spec.get("body_params"),
                    header_image_url=_spec.get("header_image_url"),
                    language="en",
                    phone_number_id=_pid,
                    access_token=_token,
                )

                if _ok:
                    # Honest SENT counter for visibility only — NOT billing
                    # (flat monthly model). Advance the nudge solely on a
                    # confirmed 200. (Item 6 will stop the onupdate bump of
                    # last_active_at that this commit may still trigger.)
                    convo.reminder_count = (convo.reminder_count or 0) + 1
                    convo.last_reminder_sent_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    db.commit()
                    sent += 1
                    logger.info(
                        f"✅ RECOVERY: Sent to {convo.external_user_id} | "
                        f"Template={_spec['name']} | "
                        f"Stage={convo.funnel_stage} | "
                        f"Score={score} | {reason}"
                    )
                else:
                    # Send failed — do NOT count as sent, do NOT advance
                    # the nudge (so it can be retried next eligible run).
                    errors += 1
                    logger.error(
                        f"❌ RECOVERY: Template send FAILED for "
                        f"{convo.external_user_id} | Template={_spec['name']}"
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
    # ── CODE-LEVEL KILL SWITCH (default OFF) ──────────────────────
    # This path also sends (realtor alerts) → gated identically. Stays
    # paused unless RECOVERY_ENABLED is EXPLICITLY "true". Before any
    # DB query or send.
    import os
    if os.getenv("RECOVERY_ENABLED", "false").lower() != "true":
        print("[recovery] RECOVERY_ENABLED is not 'true' — skipping (code-level pause).")
        return 0

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
