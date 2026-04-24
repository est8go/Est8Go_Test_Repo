from sqlalchemy import Column, Integer, String, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.database.db import Base

class CompanyProfile(Base):
    __tablename__ = "company_profiles"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), unique=True)
    
    # Clean Identity
    company_name = Column(String(255), nullable=False)
    company_about = Column(Text) # Combined Bio, Mission, Vision
    
    # AI Persona
    assistant_name = Column(String(100), default="Assistant")
    assistant_role = Column(String(100), default="Consultant")
    tone = Column(String(50), default="Professional")
    emoji_mode = Column(Boolean, default=True)
    
    # Clean Contacts
    phone_whatsapp = Column(String(50)) # Combined Phone & WhatsApp
    email = Column(String(100))
    office_address = Column(Text)
    areas_covered = Column(Text)
    
    # Rules
    payment_rules = Column(Text)
    verification_policy = Column(Text)

    tenant = relationship("Tenant", back_populates="profile")