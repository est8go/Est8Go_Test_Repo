from pydantic import BaseModel
from typing import Optional

class CompanyProfileBase(BaseModel):
    company_name: str
    company_about: Optional[str] = None
    phone_whatsapp: Optional[str] = None
    email: Optional[str] = None
    office_address: Optional[str] = None
    areas_covered: Optional[str] = None
    
    assistant_name: str = "Assistant"
    assistant_role: str = "Consultant"
    tone: str = "Professional"
    emoji_mode: bool = True
    
    payment_rules: Optional[str] = None
    verification_policy: Optional[str] = None

class CompanyProfileOut(CompanyProfileBase):
    id: int
    tenant_id: int
    class Config:
        from_attributes = True