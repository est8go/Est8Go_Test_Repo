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
from app.services.recovery_engine import (
    run_dropoff_recovery,
    escalate_high_value_leads,
)

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

        escalated = await escalate_high_value_leads(db)
        logger.info(f"🚨 Escalated: {escalated} high-value leads to Realtors")
    except Exception as e:
        logger.error(f"❌ Worker error: {e}", exc_info=True)
    finally:
        db.close()

    logger.info("✅ One-shot cycle complete. Exiting.")


if __name__ == "__main__":
    asyncio.run(main())
