from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.company_profiles.models import CompanyProfile


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)

    # subscription plan: free | pro
    plan: Mapped[str] = mapped_column(String(20), nullable=False, default="free")

    profile: Mapped["CompanyProfile"] = relationship(
        "CompanyProfile",
        back_populates="tenant",
        uselist=False,
        cascade="all, delete-orphan",
    )