from sqlalchemy import Column, Integer, String, Boolean
from app.database.db import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)

    # We store the scrambled password here
    hashed_password = Column(String(255), nullable=False)

    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    is_superuser = Column(Boolean, default=False)
    phone_number = Column(String(20), nullable=True)
