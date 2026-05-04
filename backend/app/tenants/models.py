from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.base import Base


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = {"extend_existing": True}

    # --- CORE IDENTITY ---
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    business_name = Column(String(255), nullable=True)
    plan = Column(String(50), default="pilot")
    is_active = Column(Boolean, default=True)

    # --- BOT PERSONA ---
    tone = Column(String(20), default="friendly")
    emoji = Column(String(10), default="🏠")
    areas_covered = Column(String(500), default="Abuja")

    # --- DIRECT CHANNEL IDs (single channel per platform) ---
    # For multiple numbers use TenantChannel table instead
    whatsapp_phone_number_id = Column(String(100), unique=True, nullable=True)
    facebook_page_id = Column(String(100), unique=True, nullable=True)
    instagram_account_id = Column(String(100), unique=True, nullable=True)

    # --- TIMESTAMPS ---
    created_at = Column(DateTime, default=func.now())

    # --- RELATIONSHIPS ---
    channels = relationship(
        "TenantChannel", back_populates="tenant", cascade="all, delete-orphan"
    )
    profile = relationship(
        "CompanyProfile",
        back_populates="tenant",
        uselist=False,
        cascade="all, delete-orphan",
    )
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    listings = relationship(
        "Listing", back_populates="tenant", cascade="all, delete-orphan"
    )
    messages = relationship(
        "Message", back_populates="tenant", cascade="all, delete-orphan"
    )


class TenantChannel(Base):
    """
    Supports multiple WhatsApp numbers, IG accounts, and FB pages per tenant.
    When a company changes their number: set is_active=False on old row,
    insert new row. History is preserved, resolution still works instantly.
    """

    __tablename__ = "tenant_channels"
    __table_args__ = (
        Index("idx_tenant_channels_platform_id", "platform_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform = Column(String(20), nullable=False)  # whatsapp, instagram, facebook
    platform_id = Column(
        String(100), nullable=False, unique=True
    )  # the actual ID from Meta
    label = Column(String(100), nullable=True)  # e.g. "Sales Line", "Rentals Line"
    is_active = Column(Boolean, default=True)

    # --- TIMESTAMPS ---
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # --- RELATIONSHIP ---
    tenant = relationship("Tenant", back_populates="channels")
