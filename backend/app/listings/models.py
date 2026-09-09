import enum
from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    Float,
)
from sqlalchemy.orm import relationship
from app.database.base import Base

# ================================================================
# ENUMS
# ================================================================


class ListingStatus(str, enum.Enum):
    UNVERIFIED = "unverified"
    PENDING_REVIEW = "pending_review"
    VERIFIED = "verified"
    REJECTED = "rejected"


class ListingSource(str, enum.Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"


class PropertyStatus(str, enum.Enum):
    BUILT = "built"
    OFF_PLAN = "off_plan"
    LAND = "land"


class TrustGrade(str, enum.Enum):
    UNGRADED = "ungraded"
    BRONZE = "bronze"  # 0-49%
    SILVER = "silver"  # 50-74%
    GOLD = "gold"  # 75-84%
    EMERALD = "emerald"  # 85-100% (GPS + AI audit complete)


# ================================================================
# LISTING MODEL
# ================================================================


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = {"extend_existing": True}

    # --- MULTITENANCY ---
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", use_alter=True, name="fk_listing_tenant"),
        index=True,
    )
    verified_by_id = Column(
        Integer,
        ForeignKey("users.id", use_alter=True, name="fk_listing_user"),
        nullable=True,
    )
    assigned_realtor_id = Column(
        Integer,
        ForeignKey("users.id", use_alter=True,
                   name="fk_listing_assigned_realtor"),
        nullable=True,
    )

    # --- RELATIONSHIPS ---
    tenant = relationship("Tenant", back_populates="listings")
    images = relationship(
        "ListingImage", back_populates="listing", cascade="all, delete-orphan"
    )
    documents = relationship(
        "ListingDocument", back_populates="listing", cascade="all, delete-orphan"
    )
    assigned_realtor = relationship(
        "User",
        foreign_keys=[assigned_realtor_id],
        primaryjoin="Listing.assigned_realtor_id == User.id",
    )

    # --- CORE CONTENT ---
    title = Column(String(255), nullable=False)
    location = Column(String(255), nullable=False)
    description = Column(Text)
    directions = Column(Text, nullable=True)
    price = Column(Integer, nullable=False)
    property_type = Column(String(50))

    # --- STATUS ---
    status = Column(String(50), default="unverified")
    source = Column(String(20), default="internal")
    property_status = Column(String(50), default="built")

    # --- GPS TRUTH MOAT ---
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    plus_code = Column(String(50), nullable=True)
    nearest_landmark = Column(String(255), nullable=True)
    gps_verified_at = Column(DateTime, nullable=True)  # when GPS was captured
    gps_expires_at = Column(DateTime, nullable=True)  # Emerald expires after 60 days
    gps_location_match = Column(Boolean, default=False)  # coords match claimed address
    gps_photo_match = Column(Boolean, default=False)  # photos geotagged on site

    # --- AI VISION MOAT ---
    ai_verified_real = Column(Boolean, default=False)
    ai_audit_report = Column(Text, nullable=True)

    # --- DOCUMENT VERIFICATION ---
    cof_uploaded = Column(Boolean, default=False)  # Certificate of Occupancy
    deed_uploaded = Column(Boolean, default=False)  # Deed of Assignment
    survey_uploaded = Column(Boolean, default=False)  # Survey Plan
    document_score = Column(Integer, default=0)  # +5 per verified document
    # Agency-controlled headline state for the property page:
    # none | on_request | viewable (per-document control lives on ListingDocument)
    documents_status = Column(String(20), default="none")

    # --- TRUST SCORING ---
    trust_score = Column(Integer, default=0)  # 0-100 calculated score
    trust_grade = Column(String(20), default="ungraded")  # bronze/silver/gold/emerald

    # --- TIMESTAMPS ---
    created_at = Column(DateTime, default=datetime.utcnow)
    verified_at = Column(DateTime, nullable=True)


# ================================================================
# LISTING IMAGE MODEL
# ================================================================


class ListingImage(Base):
    __tablename__ = "listing_images"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(
        Integer,
        ForeignKey(
            "listings.id", ondelete="CASCADE", use_alter=True, name="fk_image_listing"
        ),
    )
    url = Column(String(500), nullable=False)
    is_main = Column(Boolean, default=False)
    listing = relationship("Listing", back_populates="images")


# ================================================================
# LISTING DOCUMENT MODEL
# Stores uploaded legal documents (C of O, Deed, Survey, etc.).
# storage_path is the Supabase OBJECT PATH — delivery is access-
# controlled via signed URLs / a proxy (A2), never a raw public URL.
# ================================================================


class ListingDocument(Base):
    __tablename__ = "listing_documents"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)

    listing_id = Column(
        Integer,
        ForeignKey(
            "listings.id", ondelete="CASCADE",
            use_alter=True, name="fk_document_listing",
        ),
        index=True,
        nullable=False,
    )
    # Tenant isolation — every document query is tenant-scoped.
    tenant_id = Column(
        Integer,
        ForeignKey(
            "tenants.id", use_alter=True, name="fk_document_tenant",
        ),
        index=True,
        nullable=False,
    )

    doc_type = Column(String(50), nullable=False)    # key, e.g. "c_of_o"
    label = Column(String(255), nullable=False)      # human label
    tier = Column(Integer, nullable=True)            # 1–5
    score_value = Column(Integer, nullable=True)     # points value

    # Storage — PATH drives signed-URL delivery in A2; file_url kept only as a
    # reference and is NOT served directly once the bucket is private.
    storage_path = Column(String(500), nullable=False)   # Supabase object path
    file_url = Column(String(500), nullable=True)        # legacy/public URL ref
    file_hash = Column(String(64), nullable=True)        # SHA-256 hex (64 chars)

    # Per-document visibility — SAFE default: private until the agency opts in.
    visibility = Column(String(20), nullable=False, default="on_request")
    # "viewable" | "on_request"

    # Audit trail on legal docs: id is the source of truth, email a snapshot.
    uploaded_by_id = Column(
        Integer,
        ForeignKey("users.id", use_alter=True, name="fk_document_uploader"),
        nullable=True,
    )
    uploaded_by_email = Column(String(255), nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    listing = relationship("Listing", back_populates="documents")
