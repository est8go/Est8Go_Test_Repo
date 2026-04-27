from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

# Database & Models
from app.database.db import get_db
from app.listings.models import Listing
from app.listings.schemas import ListingOut
from app.services.trust_engine import calculate_confidence_score, get_trust_label

# --- 1. PREMIUM PATH HANDLING ---
# This finds 'backend/templates' from 'backend/app/public/router.py'
BASE_DIR = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# --- 2. UNIFIED ROUTER (One single source of truth) ---
router = APIRouter(prefix="/public", tags=["Public Pages"])

# --- 3. THE ROUTES ---


@router.get("/listings/{tenant_id}", response_model=List[ListingOut])
def get_public_listings(tenant_id: int, db: Session = Depends(get_db)):
    return (
        db.query(Listing)
        .filter(Listing.tenant_id == tenant_id, Listing.status == "verified")
        .all()
    )


@router.get("/property/{listing_id}", response_class=HTMLResponse)
async def get_property_page(
    request: Request, listing_id: int, db: Session = Depends(get_db)
):
    listing = (
        db.query(Listing)
        .options(joinedload(Listing.images))
        .filter(Listing.id == listing_id)
        .first()
    )
    if not listing:
        raise HTTPException(status_code=404, detail="Property not found")

    score = calculate_confidence_score(listing)
    trust = get_trust_label(score)

    return templates.TemplateResponse(
        name="property_detail.html",
        context={
            "request": request,
            "listing": listing,
            "trust_score": score,
            "trust_icon": trust.get("icon", "🟢"),
            "trust_text": trust.get("text", "Verified"),
            "trust_color": trust.get("color", "green"),
        },
    )


@router.get("/realtor-portal", response_class=HTMLResponse)
async def get_realtor_portal(request: Request):
    return templates.TemplateResponse(
        name="realtor_dashboard.html", context={"request": request}
    )


@router.get("/super-admin-portal", response_class=HTMLResponse)
async def get_admin_dashboard(request: Request):
    return templates.TemplateResponse(
        name="admin_dashboard.html", context={"request": request}
    )
