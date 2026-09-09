from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# --- IMAGE SCHEMAS ---
class ListingImageOut(BaseModel):
    id: int
    url: str
    is_main: bool

    class Config:
        from_attributes = True


# --- THE BASE FORM (What the Realtor types) ---
class ListingBase(BaseModel):
    title: str = Field(..., example="4 Bedroom Duplex")
    description: Optional[str] = None
    directions: Optional[str] = None
    location: str = Field(..., example="Guzape, Abuja")
    price: int = Field(..., example=50000000)
    property_type: str = Field(..., example="house")


class ListingCreate(ListingBase):
    pass


# --- THE FULL OUTPUT (What the Bot, Dashboard and Investors see) ---
class ListingOut(ListingBase):
    id: int
    tenant_id: int

    # Status
    status: Optional[str] = "pending_review"
    source: Optional[str] = "internal"

    # Audit Fields (For Investor Transparency)
    created_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    verification_notes: Optional[str] = None

    # Trust Score
    trust_score:     Optional[int]  = 0
    trust_grade:     Optional[str]  = "ungraded"

    # GPS Verification
    latitude:        Optional[float]    = None
    longitude:       Optional[float]    = None
    gps_verified_at: Optional[datetime] = None

    # AI + Documents + Witnesses
    ai_verified_real: Optional[bool] = False
    document_score:   Optional[int]  = 0

    cof_uploaded:     Optional[bool] = False
    deed_uploaded:    Optional[bool] = False
    survey_uploaded:  Optional[bool] = False

    # Visual Layer (The Carousel)
    images: List[ListingImageOut] = []

    # Realtor Assignment
    assigned_realtor_id:    Optional[int] = None
    assigned_realtor_name:  Optional[str] = None
    assigned_realtor_phone: Optional[str] = None

    class Config:
        from_attributes = True


# Inside backend/app/listings/schemas.py


class ListingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    directions: Optional[str] = None
    location: Optional[str] = None
    price: Optional[int] = None
    property_type: Optional[str] = None
    status: Optional[str] = None


class AssignRealtorRequest(BaseModel):
    realtor_id: Optional[int] = None  # None = unassign
