"""
006 — create followup_tasks + followup_digest_log, and add per-tenant
      follow-up SLA settings to company_profiles

Kora notices a lead has gone quiet and writes a TASK assigned to the
responsible professional, carrying the action rather than just an alert.
This is the schema behind that queue.

WHY A TABLE AND NOT A WHATSAPP ALERT
------------------------------------
alert_realtor_of_lead() (notification_service.py) sends FREE-FORM text.
Outside Meta's 24h customer-service window free-form is refused — the
same file already defines WINDOW_CLOSED_CODES = {131047, 470} to detect
exactly this. An agent who has not messaged the business number in the
last day therefore cannot receive a lead alert at all, and the function's
third fallback tier sends to the tenant's OWN Business API line, which by
definition has no open window to itself.

A row in this table has no window, no template, no Meta approval and no
per-message fee. A tenant still waiting on WhatsApp provisioning gets
follow-up value on day one.

uq_ft_open_convo_tier IS THE POINT
----------------------------------
escalate_high_value_leads() writes no state after alerting, so the hourly
cron re-alerts the same lead every hour, forever. A partial unique index
on (conversation_id, tier) WHERE status = 'open' makes a duplicate open
task impossible in the DATABASE rather than relying on the sweep to
remember — so a double cron run, a retry or a race cannot produce a
duplicate card.

FK BEHAVIOUR IS DELIBERATE
--------------------------
tenant_id / conversation_id  ON DELETE CASCADE  — tasks for a deleted
    tenant or conversation are meaningless.
listing_id, assigned_user_id, escalated_from_id, closed_by_id
    ON DELETE SET NULL — a task must SURVIVE the agent leaving the
    company, or the owner's "why leads die" history develops holes
    exactly where staff turnover happened.

NO followup_quiet_hours COLUMN
------------------------------
How long a lead must be silent before a task is raised lives in
QUIET_HOURS_BY_STAGE (app/operations/models.py), scaled by the
recovery_speed control the tenant already has UI for. A second, separate
speed setting would contradict the first.

Idempotent — safe to run repeatedly:
  - CREATE TABLE / INDEX IF NOT EXISTS
  - ADD COLUMN IF NOT EXISTS
  - ADD CONSTRAINT wrapped in DO blocks (no IF NOT EXISTS form exists)
  - ENABLE ROW LEVEL SECURITY is a no-op when already enabled
  - ON CONFLICT DO NOTHING on the self-record

Run from the backend folder:
    PYTHONPATH=. python migrations/006_followup_tasks.py --dry-run
    PYTHONPATH=. python migrations/006_followup_tasks.py

--dry-run executes every statement against the real database inside a
transaction and then ROLLS BACK. Postgres DDL is transactional, so this
genuinely validates the SQL — FK targets resolve, syntax is accepted,
constraints hold — without persisting anything.
"""

import sys

MIGRATION_NAME = "006_followup_tasks"

DRY_RUN = "--dry-run" in sys.argv

# ⚠️ register_all_models() CALLS Base.metadata.create_all(). That runs on
# its own connection and AUTOCOMMITS, before any transaction this script
# opens. So under --dry-run it would create followup_tasks and
# followup_digest_log for real, the CREATE TABLE IF NOT EXISTS below
# would become a no-op, and the closing rollback would have nothing to
# undo — leaving both tables behind WITHOUT the ENABLE ROW LEVEL
# SECURITY that only this script applies.
#
# That is not hypothetical: it is exactly what the first --dry-run of
# this migration did, and the tables had to be cleaned up by hand.
#
# The registration is only needed so create_all can resolve the models on
# a real apply. A dry run wants the opposite, so it is skipped entirely
# and the DB session is imported directly.
#
# NOTE FOR THE NEXT MIGRATION AUTHOR: the template in migrations/README.md
# opens with register_all_models(). That is safe for a plain ALTER, and
# unsafe for any migration that CREATEs a table and then needs to harden
# it. Guard it the way this file does.
if not DRY_RUN:
    from app.models_registry import register_all_models

    register_all_models()

from app.database.db import get_db
from sqlalchemy import text

STATEMENTS = [
    # ── FOLLOWUP_TASKS ────────────────────────────────────────────
    ("create followup_tasks", """
        CREATE TABLE IF NOT EXISTS followup_tasks (
            id                  SERIAL PRIMARY KEY,
            tenant_id           INTEGER NOT NULL
                                  REFERENCES tenants(id) ON DELETE CASCADE,
            conversation_id     INTEGER NOT NULL
                                  REFERENCES conversations(id) ON DELETE CASCADE,
            listing_id          INTEGER
                                  REFERENCES listings(id) ON DELETE SET NULL,

            assigned_user_id    INTEGER
                                  REFERENCES users(id) ON DELETE SET NULL,
            escalated_from_id   INTEGER
                                  REFERENCES users(id) ON DELETE SET NULL,
            parent_task_id      INTEGER
                                  REFERENCES followup_tasks(id) ON DELETE SET NULL,

            tier                SMALLINT     NOT NULL DEFAULT 1,
            kind                VARCHAR(30)  NOT NULL DEFAULT 'lead_quiet',
            status              VARCHAR(20)  NOT NULL DEFAULT 'open',
            outcome_reason      VARCHAR(30),
            outcome_note        TEXT,

            buyer_name          VARCHAR(255),
            buyer_phone         VARCHAR(32),
            funnel_stage        VARCHAR(30),
            lead_score          INTEGER      NOT NULL DEFAULT 0,
            priority_value      BIGINT       NOT NULL DEFAULT 0,

            quiet_since         TIMESTAMP    NOT NULL,
            suggested_message   TEXT,
            due_at              TIMESTAMP    NOT NULL,

            created_at          TIMESTAMP    NOT NULL DEFAULT now(),
            updated_at          TIMESTAMP    NOT NULL DEFAULT now(),
            opened_at           TIMESTAMP,
            closed_at           TIMESTAMP,
            closed_by_id        INTEGER
                                  REFERENCES users(id) ON DELETE SET NULL
        )
    """),

    # Value domains at the DB, matching the CHECK convention already used
    # for users.role and tenants.tenant_type. ADD CONSTRAINT has no
    # IF NOT EXISTS form, hence the DO blocks.
    ("check ck_ft_status", """
        DO $$ BEGIN
            ALTER TABLE followup_tasks ADD CONSTRAINT ck_ft_status
              CHECK (status IN ('open','done','dismissed','expired','superseded'));
        EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """),
    ("check ck_ft_kind", """
        DO $$ BEGIN
            ALTER TABLE followup_tasks ADD CONSTRAINT ck_ft_kind
              CHECK (kind IN ('lead_quiet','inspection_silent','escalation'));
        EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """),
    ("check ck_ft_tier", """
        DO $$ BEGIN
            ALTER TABLE followup_tasks ADD CONSTRAINT ck_ft_tier
              CHECK (tier BETWEEN 1 AND 3);
        EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """),

    # Composite reads. Index names match EXACTLY what SQLAlchemy's
    # create_all() emits for these columns, so the model and this
    # migration describe one schema rather than two overlapping ones.
    ("index ix_ft_tenant_status_due",
     "CREATE INDEX IF NOT EXISTS ix_ft_tenant_status_due "
     "ON followup_tasks (tenant_id, status, due_at)"),
    ("index ix_ft_assignee_status",
     "CREATE INDEX IF NOT EXISTS ix_ft_assignee_status "
     "ON followup_tasks (assigned_user_id, status)"),

    ("index ix_followup_tasks_id",
     "CREATE INDEX IF NOT EXISTS ix_followup_tasks_id "
     "ON followup_tasks (id)"),
    ("index ix_followup_tasks_tenant_id",
     "CREATE INDEX IF NOT EXISTS ix_followup_tasks_tenant_id "
     "ON followup_tasks (tenant_id)"),
    ("index ix_followup_tasks_conversation_id",
     "CREATE INDEX IF NOT EXISTS ix_followup_tasks_conversation_id "
     "ON followup_tasks (conversation_id)"),
    ("index ix_followup_tasks_status",
     "CREATE INDEX IF NOT EXISTS ix_followup_tasks_status "
     "ON followup_tasks (status)"),
    ("index ix_followup_tasks_due_at",
     "CREATE INDEX IF NOT EXISTS ix_followup_tasks_due_at "
     "ON followup_tasks (due_at)"),

    # THE IMPORTANT ONE — see the module docstring.
    ("unique index uq_ft_open_convo_tier",
     "CREATE UNIQUE INDEX IF NOT EXISTS uq_ft_open_convo_tier "
     "ON followup_tasks (conversation_id, tier) WHERE status = 'open'"),

    # New table → lock it down per migrations/README.md. Rows carry a
    # buyer's name, phone number and a drafted message naming them.
    # None of that belongs to any Supabase client key.
    ("rls followup_tasks",
     "ALTER TABLE followup_tasks ENABLE ROW LEVEL SECURITY"),

    # ── FOLLOWUP_DIGEST_LOG ──────────────────────────────────────
    # Idempotency record for the daily digest: one row per agent per day
    # per channel. The sweep rides the existing HOURLY cron, so "has
    # today's digest gone out?" cannot be inferred from the clock —
    # Render cron runs can be delayed or skipped, and an hour-equality
    # check would silently drop a day.
    #
    # RESERVED FOR STEP 7 (email digest). Created now so production takes
    # one migration for this feature rather than two. Nothing writes to
    # it yet.
    ("create followup_digest_log", """
        CREATE TABLE IF NOT EXISTS followup_digest_log (
            id           SERIAL PRIMARY KEY,
            tenant_id    INTEGER NOT NULL
                           REFERENCES tenants(id) ON DELETE CASCADE,
            user_id      INTEGER NOT NULL
                           REFERENCES users(id) ON DELETE CASCADE,
            sent_on      DATE        NOT NULL,
            channel      VARCHAR(20) NOT NULL DEFAULT 'email',
            task_count   INTEGER     NOT NULL DEFAULT 0,
            delivered    BOOLEAN     NOT NULL DEFAULT FALSE,
            created_at   TIMESTAMP   NOT NULL DEFAULT now()
        )
    """),
    ("unique index uq_fdl_user_day_channel",
     "CREATE UNIQUE INDEX IF NOT EXISTS uq_fdl_user_day_channel "
     "ON followup_digest_log (user_id, sent_on, channel)"),
    ("index ix_followup_digest_log_id",
     "CREATE INDEX IF NOT EXISTS ix_followup_digest_log_id "
     "ON followup_digest_log (id)"),
    ("index ix_followup_digest_log_tenant_id",
     "CREATE INDEX IF NOT EXISTS ix_followup_digest_log_tenant_id "
     "ON followup_digest_log (tenant_id)"),
    ("index ix_followup_digest_log_user_id",
     "CREATE INDEX IF NOT EXISTS ix_followup_digest_log_user_id "
     "ON followup_digest_log (user_id)"),
    ("rls followup_digest_log",
     "ALTER TABLE followup_digest_log ENABLE ROW LEVEL SECURITY"),

    # ── COMPANY_PROFILES — per-tenant SLA windows ────────────────
    # Defaults: 24h to supervisor, 48h to owner, 7d to expiry. An owner
    # who chooses the window will defend it to their staff, so these are
    # editable in the Settings tab rather than hardcoded.
    ("column followup_sla_hours",
     "ALTER TABLE company_profiles ADD COLUMN IF NOT EXISTS "
     "followup_sla_hours INTEGER NOT NULL DEFAULT 24"),
    ("column followup_owner_hours",
     "ALTER TABLE company_profiles ADD COLUMN IF NOT EXISTS "
     "followup_owner_hours INTEGER NOT NULL DEFAULT 48"),
    ("column followup_expiry_hours",
     "ALTER TABLE company_profiles ADD COLUMN IF NOT EXISTS "
     "followup_expiry_hours INTEGER NOT NULL DEFAULT 168"),
    ("column digest_hour",
     "ALTER TABLE company_profiles ADD COLUMN IF NOT EXISTS "
     "digest_hour INTEGER NOT NULL DEFAULT 8"),
    # Digest OFF by default, same discipline as RECOVERY_ENABLED —
    # nothing that sends switches itself on during a migration.
    ("column digest_enabled",
     "ALTER TABLE company_profiles ADD COLUMN IF NOT EXISTS "
     "digest_enabled BOOLEAN NOT NULL DEFAULT FALSE"),
]


db = next(get_db())

if DRY_RUN:
    print(f"DRY RUN — {MIGRATION_NAME}")
    print("Executing every statement against the real database, then "
          "ROLLING BACK.")
    print("Postgres DDL is transactional, so nothing below persists.\n")

for label, stmt in STATEMENTS:
    db.execute(text(stmt))
    print(f"  [ok] {label}")

# Verification — reads run inside the same transaction, so under
# --dry-run they observe the uncommitted schema and prove it is real.
print()
for _t in ("followup_tasks", "followup_digest_log"):
    _cols = db.execute(text(
        "SELECT count(*) FROM information_schema.columns "
        "WHERE table_name = :t"
    ), {"t": _t}).scalar()
    _rows = db.execute(text(f"SELECT count(*) FROM {_t}")).scalar()
    _rls = db.execute(text(
        "SELECT relrowsecurity FROM pg_class WHERE relname = :t"
    ), {"t": _t}).scalar()
    print(f"  {_t}: {_cols} columns, {_rows} rows, RLS={_rls}")

_new_cols = db.execute(text(
    "SELECT column_name, data_type, column_default "
    "FROM information_schema.columns "
    "WHERE table_name = 'company_profiles' "
    "AND column_name IN ('followup_sla_hours','followup_owner_hours',"
    "'followup_expiry_hours','digest_hour','digest_enabled') "
    "ORDER BY column_name"
)).fetchall()
print(f"  company_profiles new columns: {len(_new_cols)}")
for _c in _new_cols:
    print(f"    {_c[0]:<24} {_c[1]:<10} default={_c[2]}")

if DRY_RUN:
    db.rollback()
    print(f"\nROLLED BACK — nothing was written. "
          f"{MIGRATION_NAME} NOT recorded.")
    print("Re-run without --dry-run to apply.")
    sys.exit(0)

db.execute(
    text(
        "INSERT INTO applied_migrations (name) VALUES (:name) "
        "ON CONFLICT (name) DO NOTHING"
    ),
    {"name": MIGRATION_NAME},
)
db.commit()

print(f"\napplied {MIGRATION_NAME}")
print("  (a re-run reports the existing column/row counts — idempotent)")
