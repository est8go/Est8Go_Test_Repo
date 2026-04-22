from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship  # <--- Ensure this is imported
from app.database.db import Base


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    plan = Column(String(50), default="pilot")

    # 1. THE PROFILE LINK (One-to-One)
    # This connects the Tenant to their Mission, Vision, and AI Tone.
    profile = relationship("CompanyProfile", back_populates="tenant", uselist=False)

    # 2. THE USER LINK (One-to-Many)
    # This allows the Tenant to have many employees/admins.
    users = relationship("User", back_populates="tenant")

    # 3. THE LISTINGS LINK (One-to-Many)
    # This allows the Tenant to own many properties/houses.
    listings = relationship("Listing", back_populates="tenant")
