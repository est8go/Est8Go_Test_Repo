"""
EST8GO DROP-OFF RECOVERY ENGINE
=================================
Intelligent re-engagement sequences based on:
    - Funnel stage when buyer dropped off
    - Time since last activity
    - Lead score at drop-off
    - Number of previous reminders

Recovery Sequences:
    AWARENESS    → 4 nudges (4h, 24h, 48h, 7d)
    VERIFICATION → 3 nudges (2h, 12h, 24h)  — closer to buying
    COMMITMENT   → 3 nudges (1h, 4h, 12h)   — hottest, act fast
    HANDSHAKE    → not recovered (see choose_recovery_template)

Delivery:
    Recovery is business-initiated and therefore ALWAYS outside Meta's
    24h customer-service window. Only APPROVED TEMPLATES are sent —
    never free-form text. See choose_recovery_template + send_meta_template.

Recency:
    A template is deliverable at any age, so Meta will happily send to a
    contact who went quiet months ago. RECOVERY_MAX_AGE_DAYS is the
    judgement call Meta does not make for us: leads staler than the cutoff
    are never chased.

Rules-First (80/20):
    - All timing logic = pure Python
    - All template selection = pure Python
    - GPT never called for reminders
    - Zero AI cost per recovery sequence
"""

import logging
import random
import re
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.conversations.models import Conversation
from app.services.tenant_service import get_tenant_profile
from app.services.meta_sender_service import (
    send_meta_template,
    get_tenant_whatsapp_credentials,
)

logger = logging.getLogger(__name__)


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


# ── RECENCY CUTOFF ───────────────────────────────────────────────
# Upper bound on lead age. The timing table only ever set a LOWER
# bound ("enough hours have passed"), so without this a conversation
# dormant for a year still qualified for nudge 1. Meta will deliver a
# template at any age — this is the judgement call it does not make.
# Env-overridable; falls back to 14 on missing/malformed values.
_DEFAULT_MAX_AGE_DAYS = 14


def get_max_age_days() -> int:
    """Read RECOVERY_MAX_AGE_DAYS at call time (not import time) so the
    cron picks up an env change without a code deploy. Any unparseable
    or non-positive value falls back to the safe default."""
    import os
    try:
        _v = int(os.getenv("RECOVERY_MAX_AGE_DAYS", _DEFAULT_MAX_AGE_DAYS))
        return _v if _v > 0 else _DEFAULT_MAX_AGE_DAYS
    except (TypeError, ValueError):
        return _DEFAULT_MAX_AGE_DAYS


def is_good_send_time(window_start: int = 7, window_end: int = 21) -> bool:
    """
    Only send recovery messages within the tenant's configured send window.
    Nigerian timezone WAT = UTC+1. Defaults: 7am–9pm WAT.
    """
    wat = timezone(timedelta(hours=1))
    now = datetime.now(wat)
    return window_start <= now.hour <= window_end


# ── OPT-OUT DETECTION ────────────────────────────────────────────
# Matching a buyer as "opted out" PERMANENTLY deactivates automation for
# them (is_bot_active=False) and, under the follow-up task queue, also
# auto-closes their open tasks. It is therefore a high-cost false
# positive and the list is written defensively.
#
# Two rules, learned the hard way from the previous version:
#
#   1. WHOLE PHRASES ONLY. The old check was `if keyword in content`,
#      a substring test. With "no" in the list, "I know that area"
#      contained "no" (inside "know") and opted the buyer out. So did
#      "No wahala", "I no fit come today" and "Nothing spoil". With
#      "block" in the list, "Block 5, Lekki Phase 1" — an ADDRESS in
#      every Nigerian estate — opted the buyer out. 24 of 57 ordinary
#      messages in the test corpus tripped it.
#
#   2. NO AMBIGUOUS SINGLE WORDS. Several entries were simply wrong for
#      this market, boundaries or not:
#        "no"          — bare negation, ubiquitous in Pidgin
#        "no vex"      — an APOLOGY ("sorry, don't be annoyed"), usually
#                        followed by a polite question
#        "i don see am"— means "I HAVE SEEN IT", often the reply to a photo
#        "enough"      — "big enough", "not enough bedrooms"
#        "cancel"      — cancelling one inspection is RESCHEDULING, which
#                        is a buying signal, not an opt-out
#        "bye"         — ends a conversation, not a relationship
#      Each was either removed or promoted into an unambiguous phrase.
#
# "abeg no" is deliberately absent: "Abeg no vex" is an apology. The
# refusal forms are spelled out ("abeg no send", "abeg no call", ...) so
# the apology cannot match.
STOP_PHRASES = [
    # Explicit English opt-out
    "stop", "stop messaging", "stop texting", "stop disturbing",
    "unsubscribe", "opt out", "take me off",
    "remove me", "remove my number",
    "leave me alone", "go away",
    "not interested", "no longer interested", "im not interested",
    "dont contact", "do not contact",
    "dont message", "do not message",
    "dont call", "do not call",
    "dont text", "do not text",
    "no thanks", "no thank you",
    "too many messages", "block me",
    # Nigerian Pidgin
    "abeg stop", "abeg leave me", "abeg comot",
    "abeg no send", "abeg no call", "abeg no message", "abeg no text",
    "no disturb", "no dey disturb", "make you no disturb",
    "i no want", "i no want am", "i no interested",
    "i no dey interested", "no send again", "no send me again",
    "commot my number", "commot my number for your list",
]

# Kept as an alias: this name is part of the module's surface and may be
# imported elsewhere. STOP_PHRASES is the one to edit.
STOP_KEYWORDS = STOP_PHRASES

# (?<!\w) / (?!\w) rather than \b so a phrase is matched as a whole unit.
_STOP_RE = re.compile(
    r"(?<!\w)(?:" + "|".join(re.escape(p) for p in STOP_PHRASES) + r")(?!\w)",
    re.IGNORECASE,
)


def _normalise_for_optout(content: str) -> str:
    """Lowercase, fold both curly apostrophes to straight, then DROP
    apostrophes entirely and collapse whitespace.

    Dropping them means "don't", "dont" and "don’t" all reduce to the one
    stored phrase "dont contact". The old list carried only the
    typographically correct "don't contact", so the far more common
    apostrophe-less "Dont message me again" — and "Don't call me again",
    which was never listed at all — sailed straight through.
    """
    t = (content or "").lower()
    t = t.replace("’", "'").replace("ʼ", "'")
    t = t.replace("'", "")
    return re.sub(r"\s+", " ", t).strip()


def match_stop_phrase(content: str) -> str | None:
    """The matched opt-out phrase, or None. Exposed separately so the
    task sweep can close a task with the same verdict the recovery engine
    uses, and so this is unit-testable without a database."""
    _m = _STOP_RE.search(_normalise_for_optout(content))
    return _m.group(0) if _m else None


async def check_buyer_opted_out(
    convo_id: int,
    db: Session,
) -> bool:
    """
    Check if buyer has sent any stop/opt-out phrase in their recent
    messages. If yes, halt all recovery.
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
            _hit = match_stop_phrase(msg.content)
            if _hit:
                # Record WHICH phrase matched. This call permanently
                # deactivates automation for a buyer; when someone later
                # asks why a conversation went silent, the log is the
                # only place that answer exists.
                logger.info(
                    f"🚫 OPT-OUT MATCH: conversation={convo_id} "
                    f"phrase={_hit!r} message_id={msg.id}"
                )
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

    # RECENCY CUTOFF — refuse to chase stale leads. Checked before the
    # timing table so no amount of elapsed time can make a dead lead
    # eligible. Deliberately independent of `speed`: a tenant on
    # "gentle" should not get a longer chase window, only a slower one.
    _max_age_days = get_max_age_days()
    if hours_since > _max_age_days * 24:
        return False, 0, (
            f"Too stale ({hours_since / 24:.0f}d > {_max_age_days}d cutoff)"
        )

    multiplier = _SPEED_MULTIPLIER.get(speed, 1.0)
    required_hours = max(0.5, timing[count][0] * multiplier)

    if hours_since < required_hours:
        return False, 0, f"Too soon ({hours_since:.1f}h < {required_hours:.1f}h required)"

    nudge_index = count
    if score >= 70:
        return True, -1, f"High-value buyer (score={score})"

    return True, nudge_index, f"Stage={stage}, Nudge={count+1}, Speed={speed}"


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

    # PLATFORM-CARE GUARD (belt). A `platform_state` key means this
    # conversation ran through platform_care.py — someone asking Est8Go
    # about the PRODUCT, not a buyer browsing property. funnel_stage is
    # still "awareness" for them, so stage alone cannot tell them apart
    # and they would wrongly receive a property re-engagement template.
    # Braces: the tenant_type check in run_dropoff_recovery.
    if "platform_state" in _data:
        return None

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


def _is_platform_tenant(db: Session, tenant_id: int, cache: dict) -> bool:
    """True when the tenant is the Est8Go platform tenant itself, whose
    conversations are customer-care chats about the product rather than
    property leads. Uses the same `tenant_type == "platform"` discriminator
    the live webhook dispatches on (conversation_service.py), not a
    hardcoded id. Cached per run. Unknown/error → True (skip), because
    failing closed here costs one unsent nudge and failing open sends the
    wrong message from the platform's own number."""
    if tenant_id not in cache:
        try:
            from app.tenants.models import Tenant
            _t = db.get(Tenant, tenant_id)
            if _t is None:
                cache[tenant_id] = True
            else:
                cache[tenant_id] = (
                    getattr(_t, "tenant_type", "") or ""
                ) == "platform"
        except Exception as e:
            logger.error(
                f"❌ RECOVERY: tenant_type lookup failed for tenant "
                f"{tenant_id} ({e}) — treating as platform, skipping."
            )
            cache[tenant_id] = True
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
        _platform_cache: dict = {}

        for convo in active_convos:
            try:
                # PLATFORM-CARE GUARD (braces). Skip the platform tenant's
                # own customer-care conversations before any other work.
                if _is_platform_tenant(db, convo.tenant_id, _platform_cache):
                    skipped += 1
                    continue

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

                # HARD REFUSAL. get_tenant_whatsapp_credentials returns
                # _pid=None when a tenant has no active WhatsApp channel
                # AND no whatsapp_phone_number_id. send_meta_template would
                # then silently fall back to the global env number, sending
                # THIS tenant's branded template from the PLATFORM's number
                # — a cross-tenant leak the buyer sees. That env fallback is
                # correct for the reply path (Scenario A compatibility) and
                # wrong here, so it is refused at the call site rather than
                # in the shared resolver.
                #
                # Counted as an error, not a skip: a tenant with no channel
                # row is a misconfiguration someone must fix, and it should
                # be loud in the cron logs.
                if not _pid:
                    errors += 1
                    logger.error(
                        f"❌ RECOVERY CONFIG: tenant {convo.tenant_id} has no "
                        f"WhatsApp phone_number_id (no active tenant_channels "
                        f"row and no Tenant.whatsapp_phone_number_id). "
                        f"Refusing to send from the global number. "
                        f"Conversation {convo.id} not contacted."
                    )
                    continue

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
    # Same recency cutoff as should_send_reminder. This loop had only a
    # LOWER bound (>6h idle), so a lead cold for a year still escalated to
    # a realtor. No template is involved here (the alert goes to staff),
    # but chasing a dead lead wastes the realtor's time either way.
    _max_age_days = get_max_age_days()
    stale_before = now - timedelta(days=_max_age_days)

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

        if last_active < stale_before:
            logger.info(
                f"⏭️  ESCALATION SKIP: {convo.external_user_id} too stale "
                f"({(now - last_active).days}d > {_max_age_days}d cutoff)"
            )
            continue

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
