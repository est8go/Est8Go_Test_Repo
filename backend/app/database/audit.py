from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from app.database.base import Base

# ================================================================
# AUDIT LOG MODEL
# ================================================================


class AuditLog(Base):
    """
    Immutable platform audit trail.
    Every critical action — role changes, tenant deactivations,
    listing verifications, trust overrides — is recorded here.
    Never delete or edit these records.
    """

    __tablename__ = "audit_logs"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)

    # Who did it
    actor_id = Column(Integer, nullable=True)
    actor_email = Column(String(255), nullable=True)
    actor_role = Column(String(50), nullable=True)

    # What happened
    action = Column(String(100), nullable=False)
    target_table = Column(String(50), nullable=False)
    target_id = Column(Integer, nullable=True)

    # Before and after
    old_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)

    # Context
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)

    # When
    created_at = Column(DateTime, default=func.now(), nullable=False)


# ================================================================
# HELPER — write an audit log entry
# ================================================================


def log_action(
    db: Session,
    actor,
    action: str,
    target_table: str,
    target_id: int = None,
    old_value: dict = None,
    new_value: dict = None,
    ip_address: str = None,
):
    """
    Write a single audit log entry.

    Usage:
        log_action(db, actor=current_user, action="tenant_created",
                   target_table="tenants", target_id=tenant.id,
                   new_value={"name": tenant.name})
    """
    entry = AuditLog(
        actor_id=getattr(actor, "id", None),
        actor_email=getattr(actor, "email", None),
        actor_role=getattr(actor, "effective_role", None),
        action=action,
        target_table=target_table,
        target_id=target_id,
        old_value=old_value,
        new_value=new_value,
        ip_address=ip_address,
    )
    db.add(entry)
    db.commit()
