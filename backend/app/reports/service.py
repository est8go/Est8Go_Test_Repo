"""
Listing report service
======================
Creation of listing_reports rows, kept out of the model module so the
model stays a plain table definition.
"""
import logging
import random

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.reports.models import ListingReport

logger = logging.getLogger(__name__)

_REF_ATTEMPTS = 6


def generate_reference() -> str:
    """
    EST-nnnnnn. Random, not derived from the row id: a sequential
    reference would tell every reporter the platform's total report volume.
    """
    return f"EST-{random.randint(100000, 999999)}"


def create_listing_report(
    db: Session,
    detail: str,
    reporter_phone: str = None,
    reporter_name: str = None,
    tenant_id: int = None,
    reference: str = None,
) -> ListingReport:
    """
    Writes one report and returns it.

    `reference` is the value already quoted back to the reporter over
    WhatsApp, so it is used as-is when supplied. If it collides with an
    existing row the caller-visible reference would be a lie, so a
    collision falls back to generating a fresh one and the mismatch is
    logged loudly rather than silently storing a duplicate.

    Raises on failure. Callers decide whether a failed write should stop
    them replying to the reporter (it should not).
    """
    _ref = reference or generate_reference()

    for _attempt in range(_REF_ATTEMPTS):
        report = ListingReport(
            reference=_ref,
            reporter_phone=reporter_phone,
            reporter_name=reporter_name,
            detail=detail,
            tenant_id=tenant_id,
            status="new",
        )
        try:
            db.add(report)
            db.commit()
            db.refresh(report)
            return report
        except IntegrityError:
            db.rollback()
            _clash = _ref
            _ref = generate_reference()
            logger.warning(
                f"listing_reports reference collision on {_clash} "
                f"— retrying as {_ref}"
            )

    raise RuntimeError(
        f"Could not allocate a unique listing report reference after "
        f"{_REF_ATTEMPTS} attempts"
    )
