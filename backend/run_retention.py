"""Daily retention cron — anonymises suspended PII and disables dormant automation."""
import sys
import logging
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("retention")

from app.models_registry import register_all_models
register_all_models()

from app.database.db import SessionLocal
from app.services.retention_service import run_retention_checks


def main():
    db = SessionLocal()
    try:
        results = run_retention_checks(db)
        logger.info(f"Retention complete: {results}")
        if results["errors"]:
            logger.error(f"Retention errors: {results['errors']}")
            sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
