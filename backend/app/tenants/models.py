from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.database.db import Base


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    plan = Column(String(50), default="pilot")

    # String-based relationships are more stable for multi-folder projects
    profile = relationship("CompanyProfile", back_populates="tenant", uselist=False)
    users = relationship("User", back_populates="tenant")
    listings = relationship("Listing", back_populates="tenant")
