from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime,
    ForeignKey, JSON, Enum as SAEnum, UniqueConstraint,
    CheckConstraint, Text,
)
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.base import Base
import enum


class LedgerEvent(str, enum.Enum):
    TOPUP      = "TOPUP"
    RESERVE    = "RESERVE"
    COMMIT     = "COMMIT"
    REFUND     = "REFUND"
    AWARD      = "AWARD"
    WELCOME    = "WELCOME"
    BONUS      = "BONUS"
    EXPIRY     = "EXPIRY"
    ADJUSTMENT = "ADJUSTMENT"
    PENALTY    = "PENALTY"
    MMEF_HOLD  = "MMEF_HOLD"


class CreditWallet(Base):
    __tablename__ = "credit_wallets"

    id                = Column(Integer, primary_key=True)
    tenant_id         = Column(Integer, ForeignKey("tenants.id"), unique=True, nullable=False)
    purchased_balance = Column(Integer, nullable=False, default=0)
    bonus_balance     = Column(Integer, nullable=False, default=0)
    reserved          = Column(Integer, nullable=False, default=0)
    total_purchased   = Column(Integer, nullable=False, default=0)
    total_spent       = Column(Integer, nullable=False, default=0)
    total_awarded     = Column(Integer, nullable=False, default=0)
    last_activity_at  = Column(DateTime, default=datetime.utcnow)
    is_dormant        = Column(Boolean, default=False)
    updated_at        = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("purchased_balance >= 0"),
        CheckConstraint("bonus_balance >= 0"),
        CheckConstraint("reserved >= 0"),
    )


class CreditLedger(Base):
    __tablename__ = "credit_ledger"

    id               = Column(Integer, primary_key=True)
    tenant_id        = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    event_type       = Column(SAEnum(LedgerEvent), nullable=False)
    credits_debited  = Column(Integer, nullable=False, default=0)
    credits_credited = Column(Integer, nullable=False, default=0)
    balance_after    = Column(Integer, nullable=False)
    credit_type      = Column(String(20), default="purchased")
    reference        = Column(String(255), nullable=True)
    action_type      = Column(String(100), nullable=True)
    ledger_metadata  = Column("metadata", JSON, nullable=True)
    created_by       = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at       = Column(DateTime, default=datetime.utcnow)


class CreditExpiry(Base):
    __tablename__ = "credit_expiry"

    id              = Column(Integer, primary_key=True)
    tenant_id       = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    credits         = Column(Integer, nullable=False)
    credit_type     = Column(String(20), nullable=False)
    expires_at      = Column(DateTime, nullable=True)
    expired         = Column(Boolean, default=False)
    warning_sent_14 = Column(Boolean, default=False)
    warning_sent_3  = Column(Boolean, default=False)
    created_at      = Column(DateTime, default=datetime.utcnow)


class CreditBundle(Base):
    __tablename__ = "credit_bundles"

    id            = Column(Integer, primary_key=True)
    name          = Column(String(50), nullable=False)
    credits       = Column(Integer, nullable=False)
    bonus_credits = Column(Integer, default=0)
    price_ngn     = Column(Integer, nullable=False)
    is_active     = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)
    created_at    = Column(DateTime, default=datetime.utcnow)


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"

    id            = Column(Integer, primary_key=True)
    tenant_id     = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    bundle_id     = Column(Integer, ForeignKey("credit_bundles.id"), nullable=True)
    paystack_ref  = Column(String(255), unique=True, nullable=True)
    amount_ngn    = Column(Integer, nullable=False)
    credits       = Column(Integer, nullable=False)
    bonus_credits = Column(Integer, default=0)
    status        = Column(String(20), default="pending")
    month_year    = Column(String(7), nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    completed_at  = Column(DateTime, nullable=True)


class MmefTracking(Base):
    __tablename__ = "mmef_tracking"

    id            = Column(Integer, primary_key=True)
    tenant_id     = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    month_year    = Column(String(7), nullable=False)
    tier          = Column(String(20), nullable=False)
    required_ngn  = Column(Integer, nullable=False)
    purchased_ngn = Column(Integer, default=0)
    met           = Column(Boolean, default=False)
    grace_until   = Column(DateTime, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "month_year"),
    )
