from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from typing import List

# Database & Models
from app.database.db import get_db
from app.listings.models import Listing

# FIX: Import ListingOut so the public search function works
from app.listings.schemas import ListingOut

# Trust Moat Logic
from app.services.trust_engine import calculate_confidence_score, get_trust_label

router = APIRouter(prefix="/public", tags=["Public"])
templates = Jinja2Templates(directory="templates")


# --- 1. THE BOT'S SEARCH ENGINE ---
@router.get("/listings/{tenant_id}", response_model=List[ListingOut])
def get_public_listings(tenant_id: int, db: Session = Depends(get_db)):
    """
    Used by the WhatsApp/IG Bot to find matched properties.
    CORE PRINCIPLE: Only returns 'verified' listings.
    """
    return (
        db.query(Listing)
        .filter(Listing.tenant_id == tenant_id, Listing.status == "verified")
        .all()
    )


# --- 2. THE INVESTOR'S SHOWROOM ---
@router.get("/property/{listing_id}", response_class=HTMLResponse)
async def get_property_page(
    request: Request, listing_id: int, db: Session = Depends(get_db)
):
    """
    The Swiper.js page with the dynamic Confidence Score.
    """
    # Uses joinedload to ensure images are ready for the carousel
    listing = (
        db.query(Listing)
        .options(joinedload(Listing.images))
        .filter(Listing.id == listing_id)
        .first()
    )

    if not listing:
        raise HTTPException(status_code=404, detail="Property not found")

    # Calculate real-time trust signals
    score = calculate_confidence_score(listing)
    trust = get_trust_label(score)

    return templates.TemplateResponse(
        "property_detail.html",
        {
            "request": request,
            "listing": listing,
            "trust_score": score,
            "trust_icon": trust["icon"],
            "trust_text": trust["text"],
            "trust_color": trust["color"],
        },
    )
