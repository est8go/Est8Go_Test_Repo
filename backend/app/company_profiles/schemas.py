from pydantic import BaseModel, Field

# (Optional is removed because everything is now MANDATORY)


class CompanyProfileBase(BaseModel):
    """
    STRICT DATA CONTRACT: Every company must provide full details
    to ensure AI consultants have a complete knowledge base.
    """

    company_name: str = Field(..., min_length=3, max_length=100)

    # THE CAP: Max 1000 characters to keep the bot's 'About' section punchy
    company_about: str = Field(
        ..., max_length=1000, description="Full bio and mission statement"
    )

    phone_whatsapp: str = Field(
        ..., min_length=10, description="Primary WhatsApp contact"
    )
    email: str = Field(..., description="Official company email")
    office_address: str = Field(..., description="Physical HQ address")
    areas_covered: str = Field(
        ..., description="Districts covered (e.g. Maitama, Guzape)"
    )

    # AI Persona Requirements
    assistant_name: str = Field(..., description="The name assigned to the bot")
    assistant_role: str = Field(
        ..., description="The job title of the bot (e.g. Senior Property Expert)"
    )
    tone: str = Field(..., description="Professional, Friendly, or Formal")
    emoji_mode: bool = Field(default=True)

    payment_rules: str = Field(..., description="Instructions for booking and payments")
    verification_policy: str = Field(
        ..., description="How the firm verifies its listings"
    )


class CompanyProfileUpdate(CompanyProfileBase):
    """Ensures even updates maintain the 'No Half-Info' rule."""

    pass


class CompanyProfileOut(CompanyProfileBase):
    id: int
    tenant_id: int

    class Config:
        from_attributes = True
