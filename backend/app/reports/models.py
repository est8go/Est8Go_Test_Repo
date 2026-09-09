"""
Listing reports
===============
Fraud / misrepresentation reports filed by buyers through the Est8Go
platform-care WhatsApp flow (platform_care.py, option 5).

Deliberately NOT stored in platform_issues. That table is the health
monitor's — severity-filtered, dominated by automated check output, and
sorted so a 'low' row sinks. A fraud report that sinks is a fraud report
that never gets read.

Every report carries a persistent `reference` (EST-nnnnnn) because the
confirmation message quotes one back to the reporter. Before this table
existed the reference was generated with random.randint, shown, and
discarded — a reporter quoting it had nothing to quote against.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Index
from sqlalchemy.sql import func

from app.database.base import Base


class ListingReport(Base):
    __tablename__ = "listing_reports"
    __table_args__ = (
        Index("ix_listing_reports_status", "status"),
        Index("ix_listing_reports_created_at", "created_at"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)

    # EST-nnnnnn, shown to the reporter. Random rather than derived from id:
    # a sequential reference tells every reporter the platform's total
    # report volume.
    reference = Column(String(16), unique=True, nullable=False, index=True)

    # Who filed it. reporter_phone is the WhatsApp sender id, which is the
    # only way to reach them again — the flow never asks for an email.
    reporter_phone = Column(String(32), nullable=True)
    reporter_name = Column(String(255), nullable=True)

    # The report exactly as sent. Option 5 asks for the listing, the problem
    # and any evidence in one prompt, so it arrives as a single blob.
    detail = Column(Text, nullable=False)

    # Filled in by an admin once they work out which listing this is about.
    # Nothing populates it automatically.
    listing_reference = Column(Text, nullable=True)

    # The platform tenant that received the report.
    tenant_id = Column(Integer, nullable=True)

    # new | reviewing | actioned | dismissed
    status = Column(String(20), nullable=False, default="new")

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
