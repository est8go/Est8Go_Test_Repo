from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.database.base import Base


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = {"extend_existing": True}

    # Your existing fields
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    plan = Column(String(50), default="pilot")

    # NEW FIELDS: For the Bot Persona
    tone = Column(String(20), default="friendly")
    emoji = Column(String(5), default="🏠")

    # Your existing relationships (DO NOT CHANGE)
    profile = relationship(
        "CompanyProfile",
        back_populates="tenant",
        uselist=False,
        cascade="all, delete-orphan",
    )
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    listings = relationship(
        "Listing", back_populates="tenant", cascade="all, delete-orphan"
    )
    messages = relationship(
        "Message", back_populates="tenant", cascade="all, delete-orphan"
    )
