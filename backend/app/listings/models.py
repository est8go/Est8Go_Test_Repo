import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database.db import Base


class ListingStatus(str, enum.Enum):
    UNVERIFIED = "unverified"
    PENDING = "pending_review"
    VERIFIED = "verified"
    REJECTED = "rejected"


class ListingSource(str, enum.Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)

    # Safe Links: 'use_alter' helps prevent the 'Table not found' error
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

    title = Column(String(255))
    description = Column(Text)
    location = Column(String(255))
    price = Column(Integer)
    property_type = Column(String(50))

    status = Column(String(50), default=ListingStatus.UNVERIFIED, nullable=False)
    source = Column(String(20), default=ListingSource.INTERNAL)

    created_at = Column(DateTime, default=datetime.utcnow)
    verified_at = Column(DateTime, nullable=True)
    verification_notes = Column(Text, nullable=True)

    images = relationship(
        "ListingImage", back_populates="listing", cascade="all, delete-orphan"
    )


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
