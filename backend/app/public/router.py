from sqlalchemy.orm import Session, joinedload  # <--- Add joinedload to your imports
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import List

# These connect this file to your Database and Models
from app.database.db import get_db
from app.listings.models import Listing
from app.listings.schemas import ListingOut

router = APIRouter(prefix="/public", tags=["Public"])

# This looks for the 'templates' folder we created
templates = Jinja2Templates(directory="templates")


# 1. THE BOT'S ENDPOINT (Returns JSON data for WhatsApp/Instagram)
@router.get("/listings/{tenant_id}", response_model=List[ListingOut])
def get_public_listings(tenant_id: int, db: Session = Depends(get_db)):
    """
    CORE PRINCIPLE: Trust-first.
    Only returns listings that have been VERIFIED.
    """
    return (
        db.query(Listing)
        .filter(Listing.tenant_id == tenant_id, Listing.status == "verified")
        .all()
    )


# 2. THE INVESTOR'S ENDPOINT (The 'View More' Page with Swiper.js)
@router.get("/property/{listing_id}", response_class=HTMLResponse)
async def get_property_page(
    request: Request, listing_id: int, db: Session = Depends(get_db)
):
    # The 'options(joinedload(...))' is the secret fix for the 500 error
    listing = (
        db.query(Listing)
        .options(joinedload(Listing.images))
        .filter(Listing.id == listing_id)
        .first()
    )

    if not listing:
        raise HTTPException(status_code=404, detail="Property not found")

    return templates.TemplateResponse(
        request, "property_detail.html", {"request": request, "listing": listing}
    )
