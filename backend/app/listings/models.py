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
    Enum,
)
from sqlalchemy.orm import relationship
from app.database.db import Base


# 1. TRUST STATUS (The Admin Workflow)
class ListingStatus(str, enum.Enum):
    UNVERIFIED = "unverified"
    PENDING_REVIEW = "pending_review"
    VERIFIED = "verified"
    REJECTED = "rejected"


# 2. SOURCE (Company vs Realtor)
class ListingSource(str, enum.Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"


# 3. PROPERTY TIERS (Built vs Prototype vs Land)
class PropertyStatus(str, enum.Enum):
    BUILT = "built"
    OFF_PLAN = "off_plan"  # For Prototypes/3D Renderings
    LAND = "land"


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)

    # --- MULTITENANCY & AUDIT ---
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

    # --- THE BRIDGES (The Fix for your Login Error) ---
    tenant = relationship("Tenant", back_populates="listings")
    images = relationship(
        "ListingImage", back_populates="listing", cascade="all, delete-orphan"
    )

    # --- CORE CONTENT ---
    title = Column(String(255), nullable=False)
    description = Column(Text)
    price = Column(Integer, nullable=False)
    property_type = Column(String(50))  # Mansion, Duplex, etc.

    # --- DYNAMIC STATUS ---
    status = Column(String(50), default=ListingStatus.UNVERIFIED)
    source = Column(String(20), default=ListingSource.INTERNAL)
    property_status = Column(Enum(PropertyStatus), default=PropertyStatus.BUILT)

    # --- LOCATION MOATS (GPS & NEW SITES) ---
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    plus_code = Column(String(50), nullable=True)  # Digital Address for 'Bush' sites
    nearest_landmark = Column(String(255), nullable=True)  # Anchoring

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
