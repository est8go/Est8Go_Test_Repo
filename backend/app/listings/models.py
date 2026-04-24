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
from app.database.db import Base


# 1. Python Enums for Business Logic
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


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)

    # --- MULTITENANCY ---
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

    # --- RELATIONSHIPS ---
    tenant = relationship("Tenant", back_populates="listings")
    images = relationship(
        "ListingImage", back_populates="listing", cascade="all, delete-orphan"
    )

    # --- CORE CONTENT ---
    title = Column(String(255), nullable=False)
    location = Column(String(255), nullable=False)
    description = Column(Text)
    price = Column(Integer, nullable=False)
    property_type = Column(String(50))

    # --- DYNAMIC STATUS ---
    status = Column(String(50), default="unverified")
    source = Column(String(20), default="internal")
    property_status = Column(String(50), default="built")  # String for DB stability

    # --- LOCATION MOATS (GPS & NEW SITES) ---
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    plus_code = Column(String(50), nullable=True)
    nearest_landmark = Column(String(255), nullable=True)

    # --- TRUST MOATS (AI VISION) ---
    ai_verified_real = Column(Boolean, default=True)
    ai_audit_report = Column(Text, nullable=True)

    # --- TIMESTAMPS ---
    created_at = Column(DateTime, default=datetime.utcnow)
    verified_at = Column(DateTime, nullable=True)


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
