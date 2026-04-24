from pydantic import BaseModel
from typing import Optional


class CompanyProfileBase(BaseModel):
    """
    PREMIUM RELAXED SCHEMA: All fields are optional to ensure
    companies have zero friction during their profile setup.
    """

    company_name: Optional[str] = None
    company_about: Optional[str] = None
    phone_whatsapp: Optional[str] = None
    email: Optional[str] = None
    office_address: Optional[str] = None
    areas_covered: Optional[str] = None

    # Smart Defaults for the AI Persona
    assistant_name: str = "Assistant"
    assistant_role: str = "Consultant"
    tone: str = "Professional"
    emoji_mode: bool = True

    payment_rules: Optional[str] = None
    verification_policy: Optional[str] = None


class CompanyProfileUpdate(CompanyProfileBase):
    """Used for PATCH requests in Swagger."""

    pass


class CompanyProfileOut(CompanyProfileBase):
    """Used for GET responses in Swagger."""

    id: int
    tenant_id: int

    class Config:
        from_attributes = True
