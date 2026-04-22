from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.database.db import Base


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    plan = Column(String(50), default="pilot")

    # Robust Relationships using string names to avoid circular imports
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
