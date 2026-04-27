from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.sql import func
from app.database.base import Base


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True)
    channel = Column(String(50))  # e.g., 'whatsapp', 'web'
    external_user_id = Column(String(255), index=True)  # e.g., phone number
    display_name = Column(String(255), nullable=True)

    # State routing & LLM Data Extraction
    state = Column(String(50), default="ACTIVE")
    data_json = Column(Text, default="{}")
    meta_json = Column(Text, default="{}")

    # ✅ FIX: Changed 'server_default' to 'default' so Python generates the timestamp
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )
    last_reminder_sent_at = Column(DateTime, nullable=True)
    reminder_count = Column(Integer, default=0)


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), index=True)
    role = Column(String(50))  # 'user' or 'assistant'
    content = Column(Text)

    # ✅ FIX: Changed here too
    created_at = Column(DateTime(timezone=True), default=func.now())
