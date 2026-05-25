"""
Health check cron — runs every 15 minutes via Render.
OpenAI check runs only every 120 minutes to control cost.
"""
import sys
import logging
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("health")

from app.models_registry import register_all_models
register_all_models()

from datetime import datetime, timedelta
from app.database.db import SessionLocal
from app.services.health_service import run_all_checks, HealthCheck


def _should_run_openai(db) -> bool:
    """Only run OpenAI check every 120 minutes to limit cost (~₦216/mo)."""
    cutoff = datetime.utcnow() - timedelta(minutes=120)
    last = (
        db.query(HealthCheck)
        .filter(HealthCheck.system == "openai")
        .order_by(HealthCheck.checked_at.desc())
        .first()
    )
    return last is None or last.checked_at < cutoff


def main():
    db = SessionLocal()
    try:
        run_openai = _should_run_openai(db)
        results = run_all_checks(db, include_openai=run_openai)
        critical = [r for r in results if r["status"] == "critical"]
        warnings  = [r for r in results if r["status"] == "warning"]
        logger.info(
            f"Health sweep done — {len(results)} checks: "
            f"{len(critical)} critical, {len(warnings)} warning"
        )
        if critical:
            logger.error(
                f"CRITICAL systems: {[(r['system'], r['detail']) for r in critical]}"
            )
            sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
