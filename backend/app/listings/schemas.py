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
    location: str = Field(..., example="Guzape, Abuja")
    price: int = Field(..., example=50000000)
    property_type: str = Field(..., example="house")


class ListingCreate(ListingBase):
    pass


# --- THE FULL OUTPUT (What the Bot and Investors see) ---
class ListingOut(ListingBase):
    id: int
    tenant_id: int

    # Trust Layer Fields
    status: str = "unverified"
    source: str = "internal"

    # Audit Fields (For Investor Transparency)
    created_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    verification_notes: Optional[str] = None

    # Visual Layer (The Carousel)
    images: List[ListingImageOut] = []

    class Config:
        from_attributes = True


# Inside backend/app/listings/schemas.py


class ListingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    price: Optional[int] = None
    property_type: Optional[str] = None
    # ADD THIS LINE: This allows the Admin to change the status
    status: Optional[str] = None
