from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.base import Base

# ================================================================
# ROLE CONSTANTS
# ================================================================

# Est8Go platform-level roles (cross-tenant)
PLATFORM_ROLES = ("superuser", "super_staff")

# Tenant-level roles (scoped to one tenant)
TENANT_ROLES = ("admin", "realtor", "staff", "support", "marketing")

# All valid roles combined
VALID_ROLES = PLATFORM_ROLES + TENANT_ROLES


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)

    # --- TENANCY ---
    # NULL for platform users (superuser, super_staff) — they belong to Est8Go
    # Set for all tenant users — points to their company
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,  # nullable because platform users have no tenant
        index=True,
    )

    # --- IDENTITY ---
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    first_name = Column(Text, nullable=True)
    phone_number = Column(String(20), nullable=True)

    # --- ROLE (single source of truth) ---
    # Enforced at DB level via CHECK constraint in migration SQL
    role = Column(String(50), nullable=False, default="realtor")

    # --- PLATFORM FLAG ---
    # True for Est8Go staff (superuser, super_staff)
    # This is the authoritative way to check if a user is platform staff
    is_platform_user = Column(Boolean, default=False, nullable=False)

    # --- STATUS ---
    is_active = Column(Boolean, default=True)

    # --- LEGACY BOOLEANS (deprecated — do not write to these) ---
    # Kept so existing queries don't crash.
    # Will be dropped in a future cleanup migration.
    is_admin = Column(Boolean, default=False)
    is_superuser = Column(Boolean, default=False)

    # --- TEMPORARY ROLE ELEVATION ---
    role_expires_at = Column(DateTime, nullable=True)
    previous_role   = Column(String(50), nullable=True)

    # --- TIMESTAMPS ---
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # --- RETENTION ---
    deleted_at = Column(DateTime, nullable=True)    # soft-delete timestamp
    anonymised_at = Column(DateTime, nullable=True) # set after 30-day PII wipe

    # --- RELATIONSHIPS ---
    tenant = relationship("Tenant", back_populates="users")

    # ── ROLE HELPERS ─────────────────────────────────────────────

    @property
    def effective_role(self) -> str:
        """
        Single source of truth for this user's role.
        Falls back to legacy booleans for rows that predate the RBAC migration.
        """
        if self.role and self.role in VALID_ROLES:
            return self.role
        # Legacy fallback
        if self.is_superuser:
            return "superuser"
        if self.is_admin:
            return "admin"
        return "realtor"

    @property
    def can_access_all_tenants(self) -> bool:
        """True if user can see data across all tenants."""
        return self.is_platform_user or self.effective_role in PLATFORM_ROLES

    @property
    def can_manage_billing(self) -> bool:
        """Only the founder can touch billing."""
        return self.effective_role == "superuser"

    @property
    def can_delete_tenants(self) -> bool:
        """Only the founder can delete tenants."""
        return self.effective_role == "superuser"

    @property
    def can_verify_listings(self) -> bool:
        """Platform staff and tenant admins can verify listings."""
        return self.effective_role in ("superuser", "super_staff", "admin")

    @property
    def can_manage_users(self) -> bool:
        """Who can add/remove users within a tenant."""
        return self.effective_role in ("superuser", "super_staff", "admin")
