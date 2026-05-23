from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from datetime import datetime
from app.database.base import Base


class TenantSignupLink(Base):
    __tablename__ = "tenant_signup_links"
    __table_args__ = {"extend_existing": True}

    id             = Column(Integer, primary_key=True)
    code           = Column(String(64), unique=True, nullable=False, index=True)
    plan           = Column(String(50), default="Starter")
    created_by     = Column(Integer, ForeignKey("users.id"), nullable=False)
    invited_email  = Column(String(255), nullable=True)
    max_uses       = Column(Integer, default=1)
    uses_count     = Column(Integer, default=0)
    expires_at     = Column(DateTime, nullable=False)
    used_at        = Column(DateTime, nullable=True)
    created_at     = Column(DateTime, default=datetime.utcnow)
    is_active      = Column(Boolean, default=True)


class ReferralCode(Base):
    __tablename__ = "referral_codes"
    __table_args__ = {"extend_existing": True}

    id              = Column(Integer, primary_key=True)
    code            = Column(String(32), unique=True, nullable=False, index=True)
    tenant_id       = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    commission_rate = Column(Integer, default=5)
    uses_count      = Column(Integer, default=0)
    max_uses        = Column(Integer, nullable=True)
    expires_at      = Column(DateTime, nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    is_active       = Column(Boolean, default=True)


class ReferralConversion(Base):
    __tablename__ = "referral_conversions"
    __table_args__ = {"extend_existing": True}

    id                 = Column(Integer, primary_key=True)
    referral_code_id   = Column(Integer, ForeignKey("referral_codes.id"))
    referred_tenant_id = Column(Integer, ForeignKey("tenants.id"))
    conversion_value   = Column(Integer, default=0)
    commission_earned  = Column(Integer, default=0)
    paid_at            = Column(DateTime, nullable=True)
    created_at         = Column(DateTime, default=datetime.utcnow)
