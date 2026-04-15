from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

from app.database.base import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)

    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    # channel = where message came from (web, instagram, facebook, whatsapp)
    channel = Column(String(50), nullable=False, default="web")

    # external_user_id = user id from Meta/WhatsApp/website session id
    external_user_id = Column(String(120), nullable=False, index=True)

    direction = Column(String(10), nullable=False)  # "in" or "out"
    text = Column(String(2000), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    tenant = relationship("Tenant")