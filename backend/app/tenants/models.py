from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index, JSON, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.base import Base

# ================================================================
# TENANT TYPES — what kind of business is this tenant?
# ================================================================
#
#   agency      → Traditional real estate company e.g. TrustHomes Ltd
#   freelance   → Independent realtor operating as a micro-business
#   developer   → Property developer managing multiple projects
#   investor    → Active investor managing listings, leads, or teams
#
VALID_TENANT_TYPES = ("agency", "freelance", "developer", "investor")

# ================================================================
# TENANT-LEVEL ROLES — roles that exist inside any tenant
# ================================================================
#
#   admin       → Company owner / tenant manager. Full control of their tenant.
#   realtor     → Licensed agent managing listings and conversations.
#   staff       → Office/admin support staff.
#   support     → Customer-facing support representative.
#   marketing   → Marketing team member.
#
VALID_TENANT_ROLES = ("admin", "realtor", "staff", "support", "marketing")


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = {"extend_existing": True}

    # --- CORE IDENTITY ---
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    business_name = Column(String(255), nullable=True)
    slug = Column(String(100), nullable=True, unique=True, index=True)

    # What kind of business is this tenant?
    # Enforced at DB level via CHECK constraint — see migration SQL.
    tenant_type = Column(String(50), nullable=False, default="agency")

    # Subscription plan: pilot | starter | growth | enterprise
    plan = Column(String(50), default="pilot")
    is_active = Column(Boolean, default=True)

    # --- BRANDING (Workstream C: agency co-branding on the property page) ---
    # logo_url: public URL of the agency logo (non-sensitive, public bucket).
    # brand_color: validated hex like #4F46E5 — accent on the property page.
    # Both nullable: no logo/colour falls back to Est8Go-neutral styling.
    logo_url = Column(String(500), nullable=True)
    brand_color = Column(String(7), nullable=True)

    # --- BOT PERSONA ---
    tone = Column(String(20), default="friendly")
    emoji = Column(String(10), default="🏠")
    areas_covered = Column(String(500), default="Abuja")

    # --- DIRECT CHANNEL IDs (single channel per platform) ---
    # For multiple numbers per tenant use TenantChannel table instead
    whatsapp_phone_number = Column(String(20), nullable=True)   # Option A setup: plain +234... number
    whatsapp_phone_number_id = Column(String(100), unique=True, nullable=True)
    facebook_page_id = Column(String(100), unique=True, nullable=True)
    instagram_account_id = Column(String(100), unique=True, nullable=True)

    # --- TIMESTAMPS ---
    created_at = Column(DateTime, default=func.now())

    # --- COVERAGE ---
    coverage_cities = Column(JSON, default=list, nullable=True)

    # --- RETENTION ---
    suspended_at = Column(DateTime, nullable=True)   # set when is_active → False
    anonymised_at = Column(DateTime, nullable=True)  # set after 30-day PII wipe

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

    # ── HELPER PROPERTIES ────────────────────────────────────────

    @property
    def is_solo(self) -> bool:
        """True for freelance realtors operating as solo micro-businesses."""
        return self.tenant_type == "freelance"

    @property
    def display_type(self) -> str:
        """Human-readable tenant type for UI display."""
        return {
            "agency": "Real Estate Agency",
            "freelance": "Independent Realtor",
            "developer": "Property Developer",
            "investor": "Investor Group",
        }.get(self.tenant_type, "Unknown")


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
    platform = Column(String(20), nullable=False)  # whatsapp | instagram | facebook
    platform_id = Column(String(100), nullable=False, unique=True)  # Meta platform ID
    label = Column(String(100), nullable=True)  # e.g. "Sales Line", "Rentals Line"
    is_active = Column(Boolean, default=True)

    # --- PER-TENANT META CREDENTIALS (Scenario B) ---
    waba_id = Column(String(100), nullable=True)
    access_token_encrypted = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)

    # --- TIMESTAMPS ---
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # --- RELATIONSHIP ---
    tenant = relationship("Tenant", back_populates="channels")
