"""
EST8GO PUBLIC ROUTER v3.1
==========================
Serves all frontend portals.
Every portal is protected by auth_guard.js on the frontend
and validated server-side by tenant isolation in auth_deps.py.
"""

import logging
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.database.db import get_db
from app.listings.models import Listing
from app.listings.schemas import ListingOut
from app.services.trust_engine import calculate_confidence_score, get_trust_label

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter(prefix="/public", tags=["Public Pages"])


# ================================================================
# LOGIN PAGE — public, no auth required
# ================================================================


@router.get("/login", response_class=HTMLResponse)
async def get_login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")


# ================================================================
# REALTOR PORTAL
# Protected by auth_guard.js (frontend) + tenant isolation (backend)
# Tenant context is resolved server-side via /users/me after load
# ================================================================


@router.get("/realtor-portal", response_class=HTMLResponse)
async def get_realtor_portal(request: Request):
    try:
        return templates.TemplateResponse(
            request=request,
            name="realtor_dashboard.html",
        )
    except Exception as e:
        logger.error(f"Realtor Portal Error: {e}")
        return HTMLResponse(content=f"Template Error: {e}", status_code=500)


# ================================================================
# SUPER ADMIN PORTAL
# Protected by auth_guard.js with data-require-superuser="true"
# Only superuser and super_staff can access
# ================================================================


@router.get("/super-admin-portal", response_class=HTMLResponse)
async def get_admin_dashboard(request: Request):
    try:
        return templates.TemplateResponse(
            request=request,
            name="super_admin_dashboard.html",  # ← was admin_dashboard.html
        )
    except Exception as e:
        logger.error(f"Admin Portal Error: {e}")
        return HTMLResponse(content=f"Template Error: {e}", status_code=500)


# ================================================================
# PROPERTY DETAIL PAGE — public listing view
# ================================================================


@router.get("/property/{listing_id}", response_class=HTMLResponse)
async def get_property_page(
    request: Request,
    listing_id: int,
    db: Session = Depends(get_db),
):
    try:
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
    except Exception as e:
        logger.error(f"Property Page Error: {e}")
        return HTMLResponse(content="Internal Server Error", status_code=500)


# ================================================================
# MATCHES GALLERY — opened by bot link
# URL format: /public/matches?ids=1,2,5
# ================================================================


@router.get("/matches", response_class=HTMLResponse)
async def get_matches_page(
    request: Request,
    ids: str,
    db: Session = Depends(get_db),
):
    try:
        id_list = [int(i) for i in ids.split(",") if i.strip()]
        listings = (
            db.query(Listing)
            .options(joinedload(Listing.images))
            .filter(Listing.id.in_(id_list))
            .all()
        )
        return templates.TemplateResponse(
            request=request,
            name="matches_gallery.html",
            context={"listings": listings},
        )
    except Exception as e:
        logger.error(f"Gallery Error: {e}")
        return HTMLResponse("Gallery temporarily unavailable", status_code=500)


# ================================================================
# PUBLIC LISTINGS API — used by WhatsApp bot
# ================================================================


@router.get("/listings/{tenant_id}", response_model=List[ListingOut])
def get_public_listings(
    tenant_id: int,
    db: Session = Depends(get_db),
):
    return (
        db.query(Listing)
        .filter(
            Listing.tenant_id == tenant_id,
            Listing.status == "verified",
        )
        .all()
    )


# ================================================================
# FAVICON
# ================================================================


@router.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("static/favicon.ico")


@router.get("/business")
async def business_dashboard(request: Request):
    return templates.TemplateResponse("business_dashboard.html", {"request": request})
