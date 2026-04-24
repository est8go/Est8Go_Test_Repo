from sqlalchemy import Column, Integer, String, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.database.db import Base


class CompanyProfile(Base):
    __tablename__ = "company_profiles"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), unique=True)

    # All columns set to nullable=False to enforce your 'No Half-Info' rule
    company_name = Column(String(255), nullable=False)
    company_about = Column(Text, nullable=False)
    phone_whatsapp = Column(String(100), nullable=False)
    email = Column(String(100), nullable=False)
    office_address = Column(Text, nullable=False)
    areas_covered = Column(Text, nullable=False)

    assistant_name = Column(String(100), nullable=False, default="Assistant")
    assistant_role = Column(String(100), nullable=False, default="Consultant")
    tone = Column(String(100), nullable=False, default="Professional")
    emoji_mode = Column(Boolean, nullable=False, default=True)

    payment_rules = Column(Text, nullable=False)
    verification_policy = Column(Text, nullable=False)

    tenant = relationship("Tenant", back_populates="profile")
