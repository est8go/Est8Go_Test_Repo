"""
EST8GO REMINDER WORKER
========================
Runs every hour as a background process.
Executes drop-off recovery and high-value lead escalation.

Run from backend folder:
    python run_reminders.py

For production, use a process manager:
    pm2 start run_reminders.py --interpreter python
"""

import asyncio
import logging
from app.database.db import SessionLocal
from app.models_registry import register_all_models
from app.services.recovery_engine import run_dropoff_recovery
from app.operations.followup_service import run_followup_sweep

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("🚀 EST8GO REMINDER WORKER STARTED")
    logger.info("   Drop-off recovery: every 60 minutes")
    logger.info("   Follow-up task sweep: every 60 minutes")

    while True:
        db = SessionLocal()
        try:
            logger.info("⏰ Running recovery cycle...")

            # 1. Drop-off recovery (all funnel stages)
            result = await run_dropoff_recovery(db)
            logger.info(
                f"✅ Recovery: {result['sent']} sent | "
                f"{result['skipped']} skipped | "
                f"{result['errors']} errors"
            )

            # 2. Follow-up task queue (dashboard, not WhatsApp).
            #    Replaces escalate_high_value_leads(), retired because
            #    it sent free-form text Meta refuses outside the 24h
            #    window and re-alerted the same lead every hour.
            tasks = await run_followup_sweep(db)
            logger.info(
                f"📋 Follow-ups: {tasks['created']} created | "
                f"{tasks['escalated']} escalated | {tasks['expired']} expired"
            )

        except Exception as e:
            logger.error(f"❌ Worker cycle error: {e}", exc_info=True)
        finally:
            db.close()

        # Wait 60 minutes before next cycle
        logger.info("💤 Next cycle in 60 minutes...")
        await asyncio.sleep(3600)


if __name__ == "__main__":
    register_all_models()
    asyncio.run(main())
