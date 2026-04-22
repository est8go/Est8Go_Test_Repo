from pydantic import BaseModel
from typing import Optional


class CompanyProfileBase(BaseModel):
    company_name: str
    assistant_name: str = "Assistant"
    assistant_role: str = "Consultant"
    tone: str = "Professional"
    emoji_mode: bool = True
    short_about: Optional[str] = None
    company_about: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    email: Optional[str] = None
    office_address: Optional[str] = None
    working_hours: Optional[str] = None
    payment_options: Optional[str] = None
    payment_rules: Optional[str] = None
    verification_policy: Optional[str] = None


class CompanyProfileUpdate(CompanyProfileBase):
    company_name: Optional[str] = None


class CompanyProfileOut(CompanyProfileBase):
    id: int
    tenant_id: int

    class Config:
        from_attributes = True
