from sqlalchemy import Column, Integer, String, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.database.db import Base


class CompanyProfile(Base):
    __tablename__ = "company_profiles"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), unique=True)

    # Personality
    company_name = Column(String(255), nullable=False)
    assistant_name = Column(String(100), default="Assistant")
    assistant_role = Column(String(100), default="Consultant")
    tone = Column(String(50), default="Professional")
    emoji_mode = Column(Boolean, default=True)

    # Info
    short_about = Column(String(255))
    company_about = Column(Text)
    office_address = Column(Text)
    phone = Column(String(50))
    whatsapp = Column(String(50))
    email = Column(String(100))
    working_hours = Column(String(100))
    payment_options = Column(Text)
    payment_rules = Column(Text)
    verification_policy = Column(Text)

    tenant = relationship("Tenant", back_populates="profile")
