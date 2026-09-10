"""
EST8GO FOLLOW-UP SWEEP
=======================
Writes and escalates the tasks defined in app/operations/models.py.

Runs as a fourth pass on the existing hourly cron (run_reminders_once.py).
Four passes, in order:

    1. close   — buyer sent a stop phrase, or the deal closed
    2. create  — a lead has gone quiet long enough to need a human
    3. escalate— nobody actioned it inside the SLA
    4. expire  — nobody actioned it at all

Close runs FIRST so a buyer who opted out overnight cannot have a fresh
task raised for them in the same sweep.

WHY THIS IS NOT recovery_engine
-------------------------------
recovery_engine sends a WhatsApp template TO THE BUYER and is gated by
RECOVERY_ENABLED. This writes a row a HUMAN reads, needs no Meta window,
no template and no approval, and is gated by its own
FOLLOWUP_TASKS_ENABLED. The two flags are deliberately separate: reusing
RECOVERY_ENABLED would have shipped this feature switched off, since that
flag is "false" on Render and is meant to stay that way.

It also REPLACES escalate_high_value_leads(), which is retired in the same
change. That function sent free-form text to a realtor — refused by Meta
outside the 24h window — and wrote no state afterwards, so the hourly cron
re-alerted the same lead every hour, forever. Both faults are structural
here: a task is a row, and uq_ft_open_convo_tier makes a duplicate open
task at the same tier impossible in the database.

NO AI
-----
Every input to the suggested opener is already structured: buyer name,
listing title, location, price, stage, days quiet. There is nothing for a
model to infer. Rules are deterministic, free, add no network call to a
cron that must never hang, and — since the message goes out under the
AGENT'S OWN NAME from their personal WhatsApp — must not be a paraphrase
nobody reviewed.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.conversations.models import Conversation
from app.listings.models import Listing
from app.users.models import User
from app.operations.models import (
    FollowUpTask,
    QUIET_HOURS_BY_STAGE,
    NON_TASKABLE_STAGES,
    KIND_LEAD_QUIET,
    KIND_INSPECTION_SILENT,
    KIND_ESCALATION,
    STATUS_OPEN,
    STATUS_DONE,
    STATUS_EXPIRED,
    STATUS_DISMISSED,
    REASON_BUYER_OPTED_OUT,
    REASON_NO_ACTION,
    REASON_NOT_INTERESTED,
    REASON_WRONG_NUMBER,
    REASON_BOUGHT_ELSEWHERE,
)
from app.services.recovery_engine import (
    _SPEED_MULTIPLIER,
    get_max_age_days,
    match_stop_phrase,
)

logger = logging.getLogger(__name__)


# Outcomes that mean "never raise this lead again". A buyer who said they
# bought elsewhere has not become a lead again just because they later
# sent a thank-you. still_deciding is deliberately NOT here — that lead is
# alive and may re-enter the queue on new activity.
TERMINAL_REASONS = (
    REASON_NOT_INTERESTED,
    REASON_WRONG_NUMBER,
    REASON_BOUGHT_ELSEWHERE,
    REASON_BUYER_OPTED_OUT,
)

# Hard ceiling on the generated opener. wa.me carries it as a URL query
# parameter; browsers cap URLs near 2000 chars and WhatsApp truncates long
# prefills inconsistently well before that. 300 keeps it comfortably clear
# of both, and a message an agent must scroll to read is too long anyway.
MAX_OPENER_CHARS = 300


def _now() -> datetime:
    """Naive UTC, matching the DateTime columns and recovery_engine's
    write style (datetime.now(timezone.utc).replace(tzinfo=None))."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _naive(dt):
    """Coerce a possibly tz-aware timestamp to naive UTC for comparison.
    Conversation mixes both: created_at is DateTime(timezone=True) while
    last_active_at is naive."""
    if dt is None:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt


def is_enabled() -> bool:
    """Read at call time, not import time, so the flag can be flipped on
    Render without a code deploy. Default OFF, like RECOVERY_ENABLED —
    but a SEPARATE flag, so enabling the dashboard queue never implies
    enabling buyer-facing sends."""
    return os.getenv("FOLLOWUP_TASKS_ENABLED", "false").lower() == "true"


# ================================================================
# PER-TENANT SETTINGS
# ================================================================


def _get_settings(db: Session, tenant_id: int, cache: dict) -> dict:
    """SLA windows + speed for a tenant, cached per sweep run."""
    if tenant_id in cache:
        return cache[tenant_id]
    _d = {
        "speed": "standard",
        "sla_hours": 24,
        "owner_hours": 48,
        "expiry_hours": 168,
    }
    try:
        from app.company_profiles.models import CompanyProfile
        p = (
            db.query(CompanyProfile)
            .filter(CompanyProfile.tenant_id == tenant_id)
            .first()
        )
        if p:
            _d = {
                "speed": getattr(p, "recovery_speed", None) or "standard",
                "sla_hours": getattr(p, "followup_sla_hours", None) or 24,
                "owner_hours": getattr(p, "followup_owner_hours", None) or 48,
                "expiry_hours": getattr(p, "followup_expiry_hours", None) or 168,
            }
    except Exception as e:
        logger.warning(
            f"FOLLOWUP: settings lookup failed for tenant {tenant_id} "
            f"({e}) — using defaults."
        )
    cache[tenant_id] = _d
    return _d


def _quiet_threshold_hours(stage: str, speed: str):
    """How long this stage must be silent before a HUMAN is asked to act.

    Scaled by the tenant's existing recovery_speed control rather than a
    second setting of its own, so "Aggressive" means one thing across the
    product. Returns None for a stage that never produces a task.
    """
    base = QUIET_HOURS_BY_STAGE.get(stage)
    if base is None:
        return None
    return max(1.0, base * _SPEED_MULTIPLIER.get(speed, 1.0))


# ================================================================
# ASSIGNMENT
# ================================================================


def _active_user(db: Session, user_id):
    if not user_id:
        return None
    return (
        db.query(User)
        .filter(User.id == user_id, User.is_active == True)
        .first()
    )


def _resolve_assignee(db: Session, convo: Conversation, listing):
    """Who owns this lead at tier 1.

    1. The realtor who took the conversation over. If a human stepped in
       and then went quiet, the task is theirs — that is exactly the case
       recovery_engine skips (it filters is_bot_active == True) and the
       one most in need of a nudge.
    2. The listing's assigned realtor — the DURABLE ownership signal.
       Conversation.assigned_realtor_id is cleared on reactivate, so it
       means "driving right now", not "owns this lead".
    3. None — the unassigned pool, visible to the whole tenant.

    Deliberately NOT falling back to the tenant admin: that is tier 2's
    recipient, and pre-assigning there leaves escalation nowhere to go.
    """
    _u = _active_user(db, getattr(convo, "assigned_realtor_id", None))
    if _u:
        return _u
    if listing is not None:
        _u = _active_user(db, getattr(listing, "assigned_realtor_id", None))
        if _u:
            return _u
    return None


def _resolve_tenant_admin(db: Session, tenant_id: int, cache: dict):
    """The escalation recipient for tiers 2 and 3.

    v1 role-model option (a): VALID_TENANT_ROLES has exactly one level of
    authority above `realtor`, so "supervisor" and "owner" are the same
    person in a small agency. Tier 2 and tier 3 therefore differ by
    SURFACE (an assigned task vs the Exceptions view plus an email), not
    by recipient.

    GROWTH PATH (not built): add reports_to_id (self-FK) to User, then
    resolve tier 2 to the agent's actual manager. Only this function
    changes.
    """
    if tenant_id in cache:
        return cache[tenant_id]
    _a = (
        db.query(User)
        .filter(
            User.tenant_id == tenant_id,
            User.role == "admin",
            User.is_active == True,
        )
        .order_by(User.id)
        .first()
    )
    cache[tenant_id] = _a
    return _a


# ================================================================
# THE SUGGESTED OPENER (rules — no AI)
# ================================================================


# Honorifics are extremely common in Nigerian WhatsApp profile names, and
# a naive split()[0] turns "Mrs Adaeze Okonkwo" into "Hello Mrs," — which
# is the first thing a buyer sees from an unknown number. Stripped with
# and without the trailing dot.
_HONORIFICS = {
    "mr", "mrs", "miss", "ms", "mister", "madam", "ma", "sir",
    "dr", "prof", "engr", "engineer", "barr", "barrister", "arc",
    "architect", "chief", "alhaji", "alhaja", "hajia", "otunba",
    "prince", "princess", "pastor", "rev", "reverend", "bishop",
    "evang", "evangelist", "imam", "amb", "ambassador", "hon",
    "honourable", "honorable", "elder", "deacon", "capt", "col",
}


def _first_name(full) -> str:
    """First given name, with honorifics removed.

    Returns "" when nothing usable survives — the caller falls back to
    "there". A WhatsApp profile name is buyer-controlled free text: it is
    routinely a title, a phone number, a business name or an emoji, and
    none of those should be greeted by name.
    """
    _parts = (full or "").replace(",", " ").split()
    for _p in _parts:
        _clean = _p.strip(".").strip()
        if not _clean:
            continue
        if _clean.lower() in _HONORIFICS:
            continue
        # A name that is mostly digits is a phone number, not a name.
        _alpha = sum(c.isalpha() for c in _clean)
        if _alpha < 2 or _alpha < len(_clean) / 2:
            continue
        return _clean
    return ""


def _shorten(title: str, budget: int) -> str:
    """Trim a property title to a character budget on a word boundary."""
    t = (title or "").strip()
    if len(t) <= budget:
        return t
    _cut = t[:budget].rsplit(" ", 1)[0].rstrip(" ,-–—")
    return _cut or t[:budget]


def build_followup_opener(
    buyer_name: str,
    agent_name: str,
    agency_name: str,
    listing=None,
    stage: str = "awareness",
    area: str = "",
) -> str:
    """A ready-to-send WhatsApp opener, under MAX_OPENER_CHARS.

    It MUST identify both the agent and the agency. The message goes from
    the agent's PERSONAL number, which the buyer has never seen — an
    unattributed "following up on the duplex" from an unknown Nigerian
    mobile number reads exactly like the property scams Est8Go exists to
    displace.
    """
    _buyer = _first_name(buyer_name) or "there"
    _agent = _first_name(agent_name)
    _agency = (agency_name or "").strip()

    if _agent and _agency:
        opening = f"Hello {_buyer}, this is {_agent} from {_agency}."
    elif _agency:
        opening = f"Hello {_buyer}, this is {_agency}."
    elif _agent:
        opening = f"Hello {_buyer}, this is {_agent}."
    else:
        opening = f"Hello {_buyer}."

    # Neutral greeting on purpose. "Good morning" is the Nigerian business
    # convention, but the agent taps this button whenever they open the
    # dashboard — a "Good morning" arriving at 4pm reads as a bulk send.
    _area = (area or "").strip().title()
    _title = (listing.title or "").strip() if listing is not None else ""

    _budget = max(20, MAX_OPENER_CHARS - len(opening) - 120)
    _short = _shorten(_title, _budget)

    if _short:
        _where = f" in {_area}" if _area else ""
        bodies = {
            "awareness": (
                f" Following up on the {_short}{_where} you were looking at"
                f" — is it still of interest? I can arrange a viewing."
            ),
            "verification": (
                f" You were checking the verification details on the"
                f" {_short}. I can send the documents and GPS report"
                f" across — shall I?"
            ),
            "commitment": (
                f" You were about to book an inspection for the {_short}."
                f" Shall I hold a slot for you this week?"
            ),
            "handshake": (
                f" About your inspection for the {_short} — shall we lock"
                f" in a date that works for you?"
            ),
        }
    else:
        _where = f" in {_area}" if _area else ""
        bodies = {
            "awareness": (
                f" Following up on your property search{_where}."
                f" Would you like me to send a few options that fit?"
            ),
            "verification": (
                f" Following up on the property details you asked about."
                f" Happy to send the verification documents across."
            ),
            "commitment": (
                f" Following up on the inspection you were arranging."
                f" Shall I hold a slot for you this week?"
            ),
            "handshake": (
                f" Following up on your inspection — shall we lock in a"
                f" date that works for you?"
            ),
        }

    msg = opening + bodies.get(stage, bodies["awareness"])
    if len(msg) > MAX_OPENER_CHARS:
        msg = msg[:MAX_OPENER_CHARS].rsplit(" ", 1)[0].rstrip(" ,-–—") + "..."
    return msg


# ================================================================
# HELPERS SHARED WITH THE ROUTER (step 4)
# ================================================================


def close_sibling_tasks(
    db: Session,
    task: FollowUpTask,
    status: str,
    reason: str,
    closed_by_id=None,
) -> int:
    """Close every OTHER open task on the same conversation.

    When an agent finally acts on a tier-1 task, the tier-2 escalation
    sitting in the admin's queue is answered too — leaving it open would
    have the supervisor chase something already handled. Commit is the
    caller's job.
    """
    _now_ = _now()
    _siblings = (
        db.query(FollowUpTask)
        .filter(
            FollowUpTask.conversation_id == task.conversation_id,
            FollowUpTask.id != task.id,
            FollowUpTask.status == STATUS_OPEN,
        )
        .all()
    )
    for s in _siblings:
        s.status = status
        s.outcome_reason = reason
        s.closed_at = _now_
        s.closed_by_id = closed_by_id
    return len(_siblings)


def _latest_task(db: Session, conversation_id: int):
    return (
        db.query(FollowUpTask)
        .filter(FollowUpTask.conversation_id == conversation_id)
        .order_by(FollowUpTask.created_at.desc(), FollowUpTask.id.desc())
        .first()
    )


# ================================================================
# PASS 1 — CLOSE
# ================================================================


async def _pass_close(db: Session, stats: dict):
    """Close tasks whose lead has opted out or whose deal has closed.

    Runs FIRST so a buyer who sent "stop" overnight cannot have a fresh
    task raised for them later in the same sweep.
    """
    from app.conversations.models import ConversationMessage

    _open = (
        db.query(FollowUpTask)
        .filter(FollowUpTask.status == STATUS_OPEN)
        .all()
    )
    for t in _open:
        try:
            convo = db.get(Conversation, t.conversation_id)
            if convo is None:
                continue

            # Deal done — the task is answered by the outcome.
            if (convo.funnel_stage or "") == "closed":
                t.status = STATUS_DONE
                t.outcome_reason = "booked"
                t.closed_at = _now()
                stats["closed_won"] += 1
                continue

            _recent = (
                db.query(ConversationMessage)
                .filter(
                    ConversationMessage.conversation_id == convo.id,
                    ConversationMessage.role.in_(["user", "inbound"]),
                )
                .order_by(ConversationMessage.created_at.desc())
                .limit(10)
                .all()
            )
            _hit = next(
                (h for m in _recent if (h := match_stop_phrase(m.content))),
                None,
            )
            if _hit:
                t.status = STATUS_DISMISSED
                t.outcome_reason = REASON_BUYER_OPTED_OUT
                t.outcome_note = f"Auto-closed: buyer said {_hit!r}"
                t.closed_at = _now()
                # An opt-out is about the RELATIONSHIP, not this task.
                convo.is_bot_active = False
                stats["closed_optout"] += 1
                logger.info(
                    f"🚫 FOLLOWUP OPT-OUT: task={t.id} convo={convo.id} "
                    f"phrase={_hit!r} — task closed, automation disabled."
                )
        except Exception as e:
            stats["errors"] += 1
            logger.error(f"FOLLOWUP close error on task {t.id}: {e}")
    db.commit()


# ================================================================
# PASS 2 — CREATE
# ================================================================


def _should_raise(db: Session, convo: Conversation, quiet_hours: float):
    """(bool, reason). Whether this conversation needs a NEW tier-1 task."""
    _last_active = _naive(convo.last_active_at) or _naive(convo.updated_at)
    if not _last_active:
        return False, "no activity timestamp"

    _hours_quiet = (_now() - _last_active).total_seconds() / 3600.0
    if _hours_quiet < quiet_hours:
        return False, f"only {_hours_quiet:.1f}h quiet (<{quiet_hours:.0f}h)"

    # Same recency cutoff recovery uses. A lead cold for months is not
    # worth an agent's morning, and a queue full of them is a queue
    # nobody opens.
    _max_days = get_max_age_days()
    if _hours_quiet > _max_days * 24:
        return False, f"too stale ({_hours_quiet / 24:.0f}d > {_max_days}d)"

    _prev = _latest_task(db, convo.id)
    if _prev is not None:
        if _prev.status == STATUS_OPEN:
            return False, "task already open"
        if _prev.outcome_reason in TERMINAL_REASONS:
            return False, f"terminal outcome ({_prev.outcome_reason})"
        # THE ANTI-ZOMBIE RULE. Re-raise only if the buyer has done
        # something since the last task was closed. Without this, a
        # dismissed lead who stays quiet — which is precisely what a
        # dismissed lead does — is resurrected on the very next sweep,
        # and the agent who dealt with it watches it reappear forever.
        _closed = _naive(_prev.closed_at)
        if _closed and _last_active <= _closed:
            return False, "no new buyer activity since last task closed"

    return True, f"{_hours_quiet:.0f}h quiet"


async def _pass_create(db: Session, stats: dict, settings_cache, admin_cache):
    from app.services.recovery_engine import _is_platform_tenant

    _platform_cache: dict = {}
    _max_days = get_max_age_days()
    _floor = _now() - timedelta(days=_max_days)

    candidates = (
        db.query(Conversation)
        .filter(
            Conversation.state == "ACTIVE",
            or_(
                Conversation.funnel_stage.is_(None),
                Conversation.funnel_stage.notin_(NON_TASKABLE_STAGES),
            ),
        )
        .all()
    )

    for convo in candidates:
        try:
            # Platform-care guard, same discipline as recovery: these are
            # people asking Est8Go about the PRODUCT, not buyers browsing
            # property. funnel_stage is "awareness" for them too, so stage
            # alone cannot tell them apart.
            if _is_platform_tenant(db, convo.tenant_id, _platform_cache):
                stats["skipped"] += 1
                continue

            _data = {}
            try:
                _data = json.loads(convo.data_json or "{}")
            except Exception:
                _data = {}
            if "platform_state" in _data:
                stats["skipped"] += 1
                continue

            _stage = convo.funnel_stage or "awareness"
            _cfg = _get_settings(db, convo.tenant_id, settings_cache)
            _quiet = _quiet_threshold_hours(_stage, _cfg["speed"])
            if _quiet is None:
                stats["skipped"] += 1
                continue

            _ok, _why = _should_raise(db, convo, _quiet)
            if not _ok:
                stats["skipped"] += 1
                continue

            listing = None
            _lid = _data.get("last_viewed_id")
            if _lid:
                try:
                    listing = db.get(Listing, int(_lid))
                except Exception:
                    listing = None

            assignee = _resolve_assignee(db, convo, listing)

            from app.services.tenant_service import get_tenant_profile
            _agency = get_tenant_profile(db, convo.tenant_id).get(
                "business_name", ""
            )
            _area = (_data.get("location") or "").strip()
            if not _area and listing is not None:
                _area = listing.location or ""

            _opener = build_followup_opener(
                buyer_name=convo.display_name,
                # first_name ONLY — never the email local-part. Elsewhere
                # in the codebase `first_name or email.split("@")[0]` is a
                # reasonable fallback because the reader is staff, but
                # this string is sent TO A BUYER: "this is admin from
                # Bravehomes Ltd" is worse than no name at all. When
                # first_name is unset the opener falls back cleanly to
                # introducing the agency alone.
                agent_name=(assignee.first_name or "") if assignee else "",
                agency_name=_agency,
                listing=listing,
                stage=_stage,
                area=_area,
            )

            _budget = 0
            try:
                _budget = int(
                    _data.get("budget_max") or _data.get("budget") or 0
                )
            except (TypeError, ValueError):
                _budget = 0

            _last_active = _naive(convo.last_active_at) or _naive(
                convo.updated_at
            )

            task = FollowUpTask(
                tenant_id=convo.tenant_id,
                conversation_id=convo.id,
                listing_id=listing.id if listing is not None else None,
                assigned_user_id=assignee.id if assignee else None,
                tier=1,
                kind=(
                    KIND_INSPECTION_SILENT
                    if _stage == "handshake"
                    else KIND_LEAD_QUIET
                ),
                status=STATUS_OPEN,
                buyer_name=convo.display_name,
                buyer_phone=convo.external_user_id,
                funnel_stage=_stage,
                lead_score=convo.lead_score or 0,
                priority_value=_budget,
                quiet_since=_last_active,
                suggested_message=_opener,
                due_at=_now() + timedelta(hours=_cfg["sla_hours"]),
            )
            db.add(task)
            try:
                db.commit()
            except IntegrityError:
                # uq_ft_open_convo_tier. Another runner beat us to it —
                # the duplicate this feature exists to prevent, refused by
                # the database rather than by our bookkeeping.
                db.rollback()
                stats["skipped"] += 1
                continue

            stats["created"] += 1
            logger.info(
                f"📋 FOLLOWUP TASK {task.id}: convo={convo.id} "
                f"tenant={convo.tenant_id} stage={_stage} "
                f"assignee={assignee.id if assignee else 'UNASSIGNED'} "
                f"({_why})"
            )
        except Exception as e:
            stats["errors"] += 1
            db.rollback()
            logger.error(f"FOLLOWUP create error on convo {convo.id}: {e}")


# ================================================================
# PASS 3 — ESCALATE
# ================================================================


async def _pass_escalate(db: Session, stats: dict, settings_cache, admin_cache):
    """Tier 1 breached -> tier 2. Tier 2 breached -> tier 3.

    The parent stays OPEN on purpose. Superseding it would clear the
    agent's queue the moment they missed the SLA, which rewards the miss;
    the work is still theirs to do. close_sibling_tasks() ties them off
    together when either one is actioned.
    """
    _now_ = _now()
    _breached = (
        db.query(FollowUpTask)
        .filter(
            FollowUpTask.status == STATUS_OPEN,
            FollowUpTask.due_at < _now_,
            FollowUpTask.tier < 3,
        )
        .all()
    )

    for parent in _breached:
        try:
            _next_tier = parent.tier + 1
            _exists = (
                db.query(FollowUpTask)
                .filter(
                    FollowUpTask.conversation_id == parent.conversation_id,
                    FollowUpTask.tier == _next_tier,
                    FollowUpTask.status == STATUS_OPEN,
                )
                .first()
            )
            if _exists:
                continue

            admin = _resolve_tenant_admin(db, parent.tenant_id, admin_cache)
            if admin is None:
                # Nobody to escalate TO. Loud, because it is a tenant
                # misconfiguration a human must fix, not a quiet skip.
                stats["errors"] += 1
                logger.error(
                    f"❌ FOLLOWUP ESCALATION: tenant {parent.tenant_id} has "
                    f"no active admin — task {parent.id} cannot escalate to "
                    f"tier {_next_tier}."
                )
                continue

            _cfg = _get_settings(db, parent.tenant_id, settings_cache)
            _window = (
                _cfg["owner_hours"] if _next_tier == 2 else _cfg["expiry_hours"]
            )

            child = FollowUpTask(
                tenant_id=parent.tenant_id,
                conversation_id=parent.conversation_id,
                listing_id=parent.listing_id,
                assigned_user_id=admin.id,
                escalated_from_id=parent.assigned_user_id,
                parent_task_id=parent.id,
                tier=_next_tier,
                kind=KIND_ESCALATION,
                status=STATUS_OPEN,
                buyer_name=parent.buyer_name,
                buyer_phone=parent.buyer_phone,
                funnel_stage=parent.funnel_stage,
                lead_score=parent.lead_score,
                priority_value=parent.priority_value,
                quiet_since=parent.quiet_since,
                suggested_message=parent.suggested_message,
                due_at=_now_ + timedelta(hours=_window),
            )
            db.add(child)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                continue

            stats["escalated"] += 1
            logger.info(
                f"⬆️  FOLLOWUP ESCALATED: task={parent.id} -> {child.id} "
                f"tier={_next_tier} tenant={parent.tenant_id} "
                f"from_user={parent.assigned_user_id} to_admin={admin.id}"
            )
        except Exception as e:
            stats["errors"] += 1
            db.rollback()
            logger.error(f"FOLLOWUP escalate error on task {parent.id}: {e}")


# ================================================================
# PASS 4 — EXPIRE
# ================================================================


async def _pass_expire(db: Session, stats: dict, settings_cache):
    """Auto-close what nobody ever touched.

    A permanently red dashboard gets ignored, and "expired, no action" is
    itself a number the owner should see — it is the difference between a
    lead that died and a lead nobody tried.
    """
    _now_ = _now()
    _open = (
        db.query(FollowUpTask)
        .filter(FollowUpTask.status == STATUS_OPEN)
        .all()
    )
    for t in _open:
        try:
            _cfg = _get_settings(db, t.tenant_id, settings_cache)
            _age_h = (_now_ - _naive(t.created_at)).total_seconds() / 3600.0
            if _age_h < _cfg["expiry_hours"]:
                continue
            t.status = STATUS_EXPIRED
            t.outcome_reason = REASON_NO_ACTION
            t.closed_at = _now_
            stats["expired"] += 1
            logger.info(
                f"⌛ FOLLOWUP EXPIRED: task={t.id} tenant={t.tenant_id} "
                f"tier={t.tier} age={_age_h / 24:.1f}d — no action taken."
            )
        except Exception as e:
            stats["errors"] += 1
            logger.error(f"FOLLOWUP expire error on task {t.id}: {e}")
    db.commit()


# ================================================================
# ENTRY POINT
# ================================================================


async def run_followup_sweep(db: Session) -> dict:
    """Called hourly by run_reminders_once.py."""
    stats = {
        "created": 0,
        "escalated": 0,
        "expired": 0,
        "closed_optout": 0,
        "closed_won": 0,
        "skipped": 0,
        "errors": 0,
    }

    if not is_enabled():
        print("[followup] FOLLOWUP_TASKS_ENABLED is not 'true' — skipping.")
        return stats

    logger.info("📋 FOLLOW-UP SWEEP: starting...")
    _settings_cache: dict = {}
    _admin_cache: dict = {}

    try:
        await _pass_close(db, stats)
        await _pass_create(db, stats, _settings_cache, _admin_cache)
        await _pass_escalate(db, stats, _settings_cache, _admin_cache)
        await _pass_expire(db, stats, _settings_cache)
    except Exception as e:
        stats["errors"] += 1
        db.rollback()
        logger.error(f"❌ FOLLOWUP SWEEP FAILED: {e}", exc_info=True)

    logger.info(
        f"📋 FOLLOW-UP SWEEP COMPLETE: "
        f"{stats['created']} created | {stats['escalated']} escalated | "
        f"{stats['expired']} expired | {stats['closed_optout']} opt-out | "
        f"{stats['closed_won']} won | {stats['skipped']} skipped | "
        f"{stats['errors']} errors"
    )
    return stats
