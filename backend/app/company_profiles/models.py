from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.tenants.models import Tenant


class CompanyProfile(Base):
    __tablename__ = "company_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Branded assistant identity (default)
    assistant_name: Mapped[str] = mapped_column(String(80), nullable=False, default="Aor")
    assistant_role: Mapped[str] = mapped_column(String(120), nullable=False, default="Real Estate Assistant")
    emoji_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="minimal")  # off|minimal|friendly
    tone: Mapped[str] = mapped_column(String(20), nullable=False, default="friendly")

    company_name: Mapped[str] = mapped_column(String(200), nullable=False, default="Bravies Homz")
    short_about: Mapped[str] = mapped_column(String(500), nullable=False, default="We help people buy, rent, and invest in property.")

    phone: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    whatsapp: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    email: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    office_address: Mapped[str] = mapped_column(String(300), nullable=False, default="")

    areas_covered: Mapped[str] = mapped_column(String(400), nullable=False, default="Abuja")
    payment_options: Mapped[str] = mapped_column(
    String(200),
    nullable=False,
    default="Outright and Installment - 3 months, 6 months and 12 months",
)

    inspection_policy: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="Inspection is usually scheduled with our team. Any logistics will be clarified before your visit.",
    )

    manager_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    handoff_message: Mapped[str] = mapped_column(String(240), nullable=False, default="Thanks. A team member will reach out shortly.")

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="profile")
    