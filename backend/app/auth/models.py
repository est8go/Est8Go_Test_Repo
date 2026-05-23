from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.sql.elements import quoted_name
from datetime import datetime
from app.database.base import Base


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    __table_args__ = {"extend_existing": True}

    id         = Column(Integer, primary_key=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    token      = Column(String(128), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used_at    = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class RoleChangeRequest(Base):
    __tablename__ = "role_change_requests"
    __table_args__ = {"extend_existing": True}

    id             = Column(Integer, primary_key=True)
    requester_id   = Column(Integer, ForeignKey("users.id"), nullable=False)
    current_role   = Column(quoted_name("current_role", True), String(50), nullable=False)
    requested_role = Column(String(50), nullable=False)
    reason         = Column(Text, nullable=True)
    status         = Column(String(20), default="pending")
    approved_by    = Column(Integer, ForeignKey("users.id"), nullable=True)
    expiry_hours   = Column(Integer, default=24)
    activated_at   = Column(DateTime, nullable=True)
    expires_at     = Column(DateTime, nullable=True)
    actioned_at    = Column(DateTime, nullable=True)
    created_at     = Column(DateTime, default=datetime.utcnow)
