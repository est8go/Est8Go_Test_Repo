from pydantic import BaseModel
from typing import Optional


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    role: str
    is_superuser: bool
    tenant_id: Optional[int] = None  # None for platform users — valid and expected
