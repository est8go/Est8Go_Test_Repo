from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.db import Base


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)

    # The Foreign Key to the Tenant
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    # Metadata
    channel = Column(String(50))  # whatsapp, instagram, etc
    sender_id = Column(String(255))
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # THE BRIDGE: String-based reference to Tenant
    tenant = relationship("Tenant", back_populates="messages")
