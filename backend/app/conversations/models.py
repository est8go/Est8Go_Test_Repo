from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean
from sqlalchemy.sql import func
from app.database.base import Base


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = {"extend_existing": True}

    # --- CORE IDENTITY ---
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True)
    channel = Column(String(50))  # whatsapp, instagram, facebook
    external_user_id = Column(String(255), index=True)  # buyer's phone number or IG id
    display_name = Column(String(255), nullable=True)

    # --- STATE MACHINE ---
    state = Column(String(50), default="ACTIVE")
    data_json = Column(Text, default="{}")  # extracted prefs (budget, location)
    meta_json = Column(Text, default="{}")  # raw meta payload storage

    # --- BUYER INTELLIGENCE ---
    buyer_role = Column(
        String(20), default="buyer"
    )  # buyer, investor, developer, unknown
    lead_score = Column(Integer, default=0)  # 0-100 Python-calculated score
    funnel_stage = Column(String(30), default="awareness")  # awareness → closed
    session_count = Column(Integer, default=1)  # how many times they've returned
    last_active_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # --- BOT CONTROL (Human-in-the-Loop) ---
    is_bot_active = Column(Boolean, default=True)  # False = Realtor has taken over
    assigned_realtor_id = Column(Integer, nullable=True)  # which realtor took over

    # --- REMINDER SYSTEM ---
    reminder_count = Column(Integer, default=0)
    last_reminder_sent_at = Column(DateTime, nullable=True)

    # --- TIMESTAMPS ---
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), index=True)
    role = Column(String(50))  # 'user' or 'assistant'
    content = Column(Text)
    created_at = Column(DateTime(timezone=True), default=func.now())
