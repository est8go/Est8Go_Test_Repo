from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class CompanyProfileOut(BaseModel):
    tenant_id: int
    company_name: str = ""
    short_about: str = ""
    phone: str = ""
    whatsapp: str = ""
    email: str = ""
    office_address: str = ""
    areas_covered: str = ""
    payment_options: str = ""
    inspection_policy: str = ""
    manager_name: str = ""
    handoff_message: str = ""

    class Config:
        from_attributes = True


class CompanyProfileUpdate(BaseModel):
    company_name: Optional[str] = Field(default=None, max_length=200)
    short_about: Optional[str] = Field(default=None, max_length=600)

    phone: Optional[str] = Field(default=None, max_length=80)
    whatsapp: Optional[str] = Field(default=None, max_length=80)
    email: Optional[str] = Field(default=None, max_length=200)
    office_address: Optional[str] = Field(default=None, max_length=300)

    areas_covered: Optional[str] = Field(default=None, max_length=600)
    payment_options: Optional[str] = Field(default=None, max_length=300)
    inspection_policy: Optional[str] = Field(default=None, max_length=900)

    manager_name: Optional[str] = Field(default=None, max_length=200)
    handoff_message: Optional[str] = Field(default=None, max_length=300)


class PublicCompanyProfileOut(BaseModel):
    # Safe fields only (no manager name by default)
    tenant_id: int
    company_name: str = ""
    short_about: str = ""
    phone: str = ""
    whatsapp: str = ""
    email: str = ""
    office_address: str = ""
    areas_covered: str = ""
    payment_options: str = ""
    inspection_policy: str = ""
    handoff_message: str = ""

    class Config:
        from_attributes = True