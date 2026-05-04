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
from app.services.recovery_engine import (
    run_dropoff_recovery,
    escalate_high_value_leads,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("🚀 EST8GO REMINDER WORKER STARTED")
    logger.info("   Drop-off recovery: every 60 minutes")
    logger.info("   High-value escalation: every 60 minutes")

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

            # 2. High-value lead escalation (score >= 70)
            escalated = await escalate_high_value_leads(db)
            logger.info(f"🚨 Escalated: {escalated} high-value leads to Realtors")

        except Exception as e:
            logger.error(f"❌ Worker cycle error: {e}", exc_info=True)
        finally:
            db.close()

        # Wait 60 minutes before next cycle
        logger.info("💤 Next cycle in 60 minutes...")
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
