"""
Data Retention Service
======================
Runs daily. Three jobs:
  1. Backfill suspended_at for tenants already inactive with no timestamp.
  2. Anonymise PII for tenants suspended > 30 days.
  3. Disable automation for tenants dormant > 12 months.
"""
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def run_retention_checks(db: Session) -> dict:
    now = datetime.utcnow()
    results = {
        "suspended_backfilled": 0,
        "pii_anonymised": 0,
        "dormant_bots_disabled": 0,
        "errors": [],
    }

    # ── 1. BACKFILL suspended_at ──────────────────────────────────
    try:
        from app.tenants.models import Tenant
        no_date = db.query(Tenant).filter(
            Tenant.is_active == False,
            Tenant.suspended_at == None,
        ).all()
        for t in no_date:
            t.suspended_at = now
        db.commit()
        results["suspended_backfilled"] = len(no_date)
        if no_date:
            logger.info(f"Retention: backfilled suspended_at for {len(no_date)} tenant(s)")
    except Exception as e:
        db.rollback()
        results["errors"].append(f"suspended_backfill: {e}")
        logger.error(f"Retention: suspended_backfill failed: {e}")

    # ── 2. ANONYMISE PII after 30 days ───────────────────────────
    try:
        from app.tenants.models import Tenant
        from app.users.models import User
        cutoff_30 = now - timedelta(days=30)
        to_anonymise = db.query(Tenant).filter(
            Tenant.is_active == False,
            Tenant.suspended_at != None,
            Tenant.suspended_at <= cutoff_30,
            Tenant.anonymised_at == None,
        ).all()
        for t in to_anonymise:
            logger.info(f"Retention: anonymising tenant {t.id} (suspended {t.suspended_at})")
            t.name = "[Suspended]"
            t.business_name = "[Suspended]"
            users = db.query(User).filter(
                User.tenant_id == t.id,
                User.anonymised_at == None,
            ).all()
            for u in users:
                u.email = f"redacted_{u.id}@deleted.est8go"
                u.first_name = "[Redacted]"
                u.phone_number = None
                u.anonymised_at = now
            t.anonymised_at = now
        db.commit()
        results["pii_anonymised"] = len(to_anonymise)
        if to_anonymise:
            logger.info(f"Retention: anonymised {len(to_anonymise)} tenant(s)")
    except Exception as e:
        db.rollback()
        results["errors"].append(f"pii_anonymise: {e}")
        logger.error(f"Retention: pii_anonymise failed: {e}")

    # ── 3. DORMANT — disable automation after 12 months ─────────
    try:
        from app.tenants.models import Tenant
        from app.conversations.models import Conversation
        cutoff_12m = now - timedelta(days=365)
        active_tenants = db.query(Tenant).filter(Tenant.is_active == True).all()
        disabled = 0
        for t in active_tenants:
            # Skip brand-new tenants
            if t.created_at and t.created_at.replace(tzinfo=None) > cutoff_12m:
                continue
            last = (
                db.query(Conversation)
                .filter(Conversation.tenant_id == t.id)
                .order_by(Conversation.updated_at.desc())
                .first()
            )
            is_dormant = (
                last is None
                or (
                    last.updated_at is not None
                    and last.updated_at.replace(tzinfo=None) <= cutoff_12m
                )
            )
            if is_dormant:
                updated = db.query(Conversation).filter(
                    Conversation.tenant_id == t.id,
                    Conversation.is_bot_active == True,
                ).update({"is_bot_active": False}, synchronize_session=False)
                if updated:
                    disabled += 1
                    logger.info(f"Retention: automation disabled for dormant tenant {t.id}")
        db.commit()
        results["dormant_bots_disabled"] = disabled
    except Exception as e:
        db.rollback()
        results["errors"].append(f"dormant_check: {e}")
        logger.error(f"Retention: dormant_check failed: {e}")

    return results
