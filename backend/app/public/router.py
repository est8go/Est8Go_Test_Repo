from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from typing import List
from pathlib import Path

# Database & Models
from app.database.db import get_db
from app.listings.models import Listing

# FIX: Import ListingOut so the public search function works
from app.listings.schemas import ListingOut

# Trust Moat Logic
from app.services.trust_engine import calculate_confidence_score, get_trust_label

router = APIRouter(prefix="/public", tags=["Public"])
templates = Jinja2Templates(directory="templates")

# Professional Path Handling
BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(Path(BASE_DIR, "templates")))

router = APIRouter(tags=["Public Pages"])


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
    PREMIUM SHOWROOM: Uses the modern 'Keyword' style to prevent
    the 'tuple as dict key' crash.
    """
    # 1. Fetch house + images
    listing = (
        db.query(Listing)
        .options(joinedload(Listing.images))
        .filter(Listing.id == listing_id)
        .first()
    )

    if not listing:
        raise HTTPException(status_code=404, detail="Property not found")

    # 2. Calculate Moat Logic
    score = calculate_confidence_score(listing)
    trust = get_trust_label(score)

    # 3. THE BULLETPROOF RETURN
    # We pass 'request=request' and 'context={...}' as named arguments.
    # This is the modern standard and fixes the 500 error.
    return templates.TemplateResponse(
        request=request,
        name="property_detail.html",
        context={
            "listing": listing,
            "trust_score": score,
            "trust_icon": trust.get("icon", "🟢"),
            "trust_text": trust.get("text", "Verified"),
            "trust_color": trust.get("color", "green"),
        },
    )


@router.get("/realtor-portal")
async def get_realtor_portal(request: Request):
    """
    Renders the Realtor Lead Dashboard.
    """
    return templates.TemplateResponse(
        name="realtor_dashboard.html", context={"request": request}
    )


@router.get("/super-admin-portal")
async def get_admin_dashboard(request: Request):
    """
    Renders the Super Admin Truth Monitor.
    """
    return templates.TemplateResponse(
        name="admin_dashboard.html", context={"request": request}
    )
