"""
EST8GO FOLLOW-UP TASK QUEUE
============================
Kora notices a lead has gone quiet and writes a TASK assigned to the
responsible professional. The task carries the ACTION, not just an alert:
who the buyer is, what they were looking at, how long they have been
quiet, and a suggested opening message.

Why a table and not a WhatsApp alert
------------------------------------
alert_realtor_of_lead() sends FREE-FORM text. Outside Meta's 24h window
free-form is refused (error 131047 / 470 — see WINDOW_CLOSED_CODES in
notification_service.py), so an agent who has not messaged the business
number in the last day cannot receive an alert at all. Its third fallback
tier sends to the tenant's own Business API line, which by definition has
no open window to itself. Alerts-by-WhatsApp were never deliverable for
the agents who most need them.

A row in this table has no window, no template, no Meta approval and no
per-message fee. A tenant still waiting on WhatsApp provisioning gets
follow-up value on day one.

Escalation (v1 — role model option (a))
---------------------------------------
    tier 1  -> the responsible agent
    tier 2  -> the tenant admin, as an ASSIGNED task carrying the original
               agent's name (escalated_from_id)
    tier 3  -> the same admin, but surfaced in the owner's Exceptions view
               plus an email — different surface, different urgency

VALID_TENANT_ROLES has exactly one level of authority above `realtor`
(`admin`), so "supervisor" and "owner" are the same person in a small
agency. v1 accepts that deliberately and separates the two by SURFACE
rather than by recipient.

GROWTH PATH (not built): add `reports_to_id` (self-FK) to User for a real
org chart, then resolve tier 2 to the agent's actual manager instead of
to the tenant admin. Everything else here stays as-is — only the
assignee resolver changes.
"""

from sqlalchemy import (
    Column,
    Integer,
    SmallInteger,
    BigInteger,
    String,
    Text,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    CheckConstraint,
    text,
)
from sqlalchemy.sql import func

from app.database.base import Base


# ================================================================
# CONSTANTS
# ================================================================

# Why the task exists.
KIND_LEAD_QUIET = "lead_quiet"                # buyer went quiet mid-funnel
KIND_INSPECTION_SILENT = "inspection_silent"  # booked an inspection, then silence
KIND_ESCALATION = "escalation"                # nobody actioned the parent task
VALID_KINDS = (KIND_LEAD_QUIET, KIND_INSPECTION_SILENT, KIND_ESCALATION)

# Lifecycle. `superseded` exists so an escalated parent stops competing
# for attention without pretending it was dealt with.
STATUS_OPEN = "open"
STATUS_DONE = "done"
STATUS_DISMISSED = "dismissed"
STATUS_EXPIRED = "expired"
STATUS_SUPERSEDED = "superseded"
VALID_STATUSES = (
    STATUS_OPEN, STATUS_DONE, STATUS_DISMISSED,
    STATUS_EXPIRED, STATUS_SUPERSEDED,
)
CLOSED_STATUSES = (
    STATUS_DONE, STATUS_DISMISSED, STATUS_EXPIRED, STATUS_SUPERSEDED,
)

# Why the lead died. The whole point of forcing a reason on dismiss: it
# gives the owner data no Nigerian agency currently has. Two seconds for
# the agent, a real number for the business.
REASON_NOT_INTERESTED = "not_interested"
REASON_WRONG_NUMBER = "wrong_number"
REASON_BOUGHT_ELSEWHERE = "bought_elsewhere"
REASON_STILL_DECIDING = "still_deciding"
DISMISS_REASONS = (
    REASON_NOT_INTERESTED, REASON_WRONG_NUMBER,
    REASON_BOUGHT_ELSEWHERE, REASON_STILL_DECIDING,
)

# Set by the system rather than chosen by an agent.
REASON_CONTACTED = "contacted"              # agent marked done
REASON_BOOKED = "booked"                    # buyer re-engaged and booked
REASON_BUYER_OPTED_OUT = "buyer_opted_out"  # STOP keyword — auto-closed
REASON_NO_ACTION = "no_action"              # ran past followup_expiry_hours
SYSTEM_REASONS = (
    REASON_CONTACTED, REASON_BOOKED,
    REASON_BUYER_OPTED_OUT, REASON_NO_ACTION,
)

VALID_REASONS = DISMISS_REASONS + SYSTEM_REASONS

# How long a conversation must be quiet before a task is written, per
# funnel stage, in hours. Deliberately COARSER than REMINDER_TIMING in
# recovery_engine.py: that table paces automated nudges (4h is fine for a
# bot) while this one paces a HUMAN. No agent chases a four-hour-old
# browse, and a queue full of such tasks is a queue nobody opens.
#
# Scaled per tenant by CompanyProfile.recovery_speed via the existing
# _SPEED_MULTIPLIER (gentle 2.0 / standard 1.0 / aggressive 0.5), so the
# speed control the tenant already has UI for governs this too and there
# is no second, contradictory setting.
QUIET_HOURS_BY_STAGE = {
    "awareness":    48,   # still browsing — give it room
    "verification": 24,
    "commitment":   24,
    "handshake":    24,   # booked an inspection then went silent: the
                          # highest-value follow-up in the system
}

# Stages that never produce a task. Unknown stages fall through the
# QUIET_HOURS_BY_STAGE lookup and are skipped the same way.
NON_TASKABLE_STAGES = ("closed",)


class FollowUpTask(Base):
    __tablename__ = "followup_tasks"
    __table_args__ = (
        # Queue reads: "open tasks for this tenant, soonest due first".
        Index("ix_ft_tenant_status_due", "tenant_id", "status", "due_at"),
        # "My follow-ups" — the realtor's default view.
        Index("ix_ft_assignee_status", "assigned_user_id", "status"),
        # IDEMPOTENCY, and the fix for the bug this feature replaces.
        # escalate_high_value_leads() writes no state after alerting, so
        # the hourly cron re-alerts the same lead every hour forever.
        # This makes a duplicate open task at the same tier impossible at
        # the DATABASE level rather than relying on the sweep to remember.
        Index(
            "uq_ft_open_convo_tier",
            "conversation_id", "tier",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
        # Value domains enforced at the DB, matching the CHECK-constraint
        # convention already used for users.role and tenants.tenant_type.
        # Declared here as well as in migrate_followup_tasks.py so that
        # create_all() on a fresh database produces the SAME schema the
        # migration does, rather than a subtly weaker one.
        CheckConstraint(
            "status IN ('open','done','dismissed','expired','superseded')",
            name="ck_ft_status",
        ),
        CheckConstraint(
            "kind IN ('lead_quiet','inspection_silent','escalation')",
            name="ck_ft_kind",
        ),
        CheckConstraint("tier BETWEEN 1 AND 3", name="ck_ft_tier"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)

    # --- TENANCY ---
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # --- SUBJECT ---
    conversation_id = Column(
        Integer,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # What they were last looking at. Nullable: a lead can go quiet before
    # reaching a specific property, and that lead still deserves a task.
    # (escalate_high_value_leads() skips those entirely and silently —
    # this does not.)
    listing_id = Column(
        Integer,
        ForeignKey("listings.id", ondelete="SET NULL"),
        nullable=True,
    )

    # --- ASSIGNMENT ---
    # NULL = unassigned pool, visible to the whole tenant. Better than
    # guessing an owner: an unclaimed task in a shared queue still gets
    # worked, a task assigned to the wrong person does not.
    #
    # NOT derived from Conversation.assigned_realtor_id — that field is
    # set on HITL takeover and cleared on reactivate, so it means "who is
    # driving this chat right now", not "who owns this lead".
    # Listing.assigned_realtor_id is the durable signal.
    assigned_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Whose inaction caused this escalation. Put on the tier-2 card so
    # there is a NAME against the miss, not just a status colour.
    escalated_from_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    parent_task_id = Column(
        Integer,
        ForeignKey("followup_tasks.id", ondelete="SET NULL"),
        nullable=True,
    )

    # --- CLASSIFICATION ---
    tier = Column(SmallInteger, nullable=False, default=1)  # 1 agent 2 admin 3 owner
    kind = Column(String(30), nullable=False, default=KIND_LEAD_QUIET)
    status = Column(String(20), nullable=False, default=STATUS_OPEN, index=True)

    outcome_reason = Column(String(30), nullable=True)
    outcome_note = Column(Text, nullable=True)

    # --- SNAPSHOT AT CREATION ---
    # Denormalised on purpose. The card must render without joining a
    # conversation whose stage and score keep moving, and the owner's
    # "why leads die" report must reflect the lead AS IT WAS when the
    # follow-up was raised, not as it looks months later.
    #
    # WARNING: buyer_name, buyer_phone and suggested_message are PII and
    # are wiped by retention_service.run_retention_checks() on the same
    # 30-day tenant-suspension trigger as users.
    buyer_name = Column(String(255), nullable=True)
    buyer_phone = Column(String(32), nullable=True)
    funnel_stage = Column(String(30), nullable=True)
    lead_score = Column(Integer, nullable=False, default=0)
    # Buyer's stated budget. Orders the daily digest by LEAD VALUE rather
    # than age, so an agent who reads only the first line still acts on
    # the right lead. BigInteger: Nigerian property prices in naira
    # overflow a 32-bit int at ~2.1bn and listings above that exist.
    priority_value = Column(BigInteger, nullable=False, default=0)

    quiet_since = Column(DateTime, nullable=False)
    suggested_message = Column(Text, nullable=True)

    # --- SLA ---
    due_at = Column(DateTime, nullable=False, index=True)

    # --- LIFECYCLE ---
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )
    # Set when the agent taps "Message on WhatsApp". Named `opened_at`,
    # NOT `contacted_at`, and it does NOT close the task. The agent
    # messages from their PERSONAL WhatsApp, so the reply lands on their
    # phone and Kora never sees it — the platform cannot know whether
    # contact actually happened. Tapping a button is the only thing we
    # observed, so it is the only thing we record. "Mark Done" stays a
    # deliberate human act.
    opened_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    closed_by_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


class FollowUpDigestLog(Base):
    """One row per agent per day per channel — the digest's idempotency
    record.

    The sweep rides the existing HOURLY cron, so "has today's digest gone
    out?" cannot be inferred from the clock: Render cron runs can be
    delayed or skipped, and an hour-equality check would silently drop a
    day. The sweep instead fires when the tenant's local WAT hour has
    REACHED digest_hour and no row exists here for today.

    RESERVED FOR STEP 7 (email digest). Created now so production takes
    one migration for this feature rather than two. Nothing writes to it
    yet.
    """

    __tablename__ = "followup_digest_log"
    __table_args__ = (
        Index(
            "uq_fdl_user_day_channel",
            "user_id", "sent_on", "channel",
            unique=True,
        ),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sent_on = Column(Date, nullable=False)      # WAT calendar day
    channel = Column(String(20), nullable=False, default="email")  # email | whatsapp
    task_count = Column(Integer, nullable=False, default=0)
    delivered = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=func.now())
