"""
EST8GO REMINDER WORKER — ONE-SHOT
===================================
Runs the recovery cycle once and exits.
Designed for Render scheduled jobs (cron).

Run manually:
    python backend/run_reminders_once.py
"""

from app.models_registry import register_all_models
register_all_models()

import asyncio
import logging
from app.database.db import SessionLocal
from app.services.recovery_engine import run_dropoff_recovery
from app.operations.followup_service import run_followup_sweep

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("🚀 EST8GO REMINDER WORKER — ONE-SHOT STARTED")
    db = SessionLocal()
    try:
        result = await run_dropoff_recovery(db)
        logger.info(
            f"✅ Recovery: {result['sent']} sent | "
            f"{result['skipped']} skipped | "
            f"{result['errors']} errors"
        )

        # Follow-up task queue. Gated by FOLLOWUP_TASKS_ENABLED, which is
        # DELIBERATELY NOT RECOVERY_ENABLED: that flag is "false" on
        # Render and is meant to stay that way, so reusing it would have
        # shipped this feature permanently switched off. Nothing here
        # sends a message — it writes rows a human reads in the dashboard.
        #
        # Replaces escalate_high_value_leads(), retired in the same
        # change: it alerted realtors with free-form WhatsApp text that
        # Meta refuses outside the 24h window, and wrote no state, so it
        # re-alerted the same lead every hour forever.
        tasks = await run_followup_sweep(db)
        logger.info(
            f"📋 Follow-ups: {tasks['created']} created | "
            f"{tasks['escalated']} escalated | {tasks['expired']} expired | "
            f"{tasks['closed_optout']} opt-out | {tasks['errors']} errors"
        )
    except Exception as e:
        logger.error(f"❌ Worker error: {e}", exc_info=True)
    finally:
        db.close()

    logger.info("✅ One-shot cycle complete. Exiting.")


if __name__ == "__main__":
    asyncio.run(main())
