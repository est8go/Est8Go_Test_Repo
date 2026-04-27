import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Header

from sqlalchemy.orm import Session
from supabase import create_client, Client

from app.database.db import get_db
from app.auth.deps import get_current_user
from app.users.models import User
from app.listings.models import Listing, ListingImage
from app.listings.schemas import (
    ListingCreate,
    ListingUpdate,
    ListingOut,
    ListingImageOut,
)

# CRITICAL: We ensure there are NO global dependencies here that might block you
router = APIRouter(prefix="/tenants/me/listings", tags=["Listings"])

# --- SUPABASE CONFIG ---
URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_KEY")
supabase_client: Optional[Client] = None
if URL and KEY:
    try:
        supabase_client = create_client(URL, KEY)
    except Exception:
        pass


# --- 1. CREATE LISTING (Now with manual Tenant ID field) ---
@router.post("/", response_model=ListingOut)
def create_listing(
    payload: ListingCreate,
    x_tenant_id: int = Header(
        ..., alias="X-Tenant-Id"
    ),  # <--- This forces the box in Swagger
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        new_listing = Listing(
            tenant_id=x_tenant_id,  # Uses exactly what you type in the box
            **payload.model_dump(),
        )
        db.add(new_listing)
        db.commit()
        db.refresh(new_listing)
        return new_listing
    except Exception as e:
        db.rollback()
        print(f"❌ DATABASE ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- 2. GET MY LISTINGS (Now with manual Tenant ID field) ---
@router.get("/", response_model=List[ListingOut])
def get_my_listings(
    x_tenant_id: int = Header(
        ..., alias="X-Tenant-Id"
    ),  # <--- This forces the box in Swagger
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Listing).filter(Listing.tenant_id == x_tenant_id).all()


# --- 3. UPLOAD IMAGES (Now with manual Tenant ID field) ---
# Backup Version (Guaranteed to show the button)
@router.post("/{listing_id}/upload-single-image", response_model=ListingImageOut)
async def upload_single_photo(
    listing_id: int,
    x_tenant_id: int = Header(..., alias="X-Tenant-Id"),
    file: UploadFile = File(...),  # Single file always shows the button
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Same upload logic as above, but for one file
    file_content = await file.read()
    file_path = f"{listing_id}/{os.urandom(4).hex()}.jpg"
    supabase_client.storage.from_("property-images").upload(
        path=file_path, file=file_content
    )
    url = supabase_client.storage.from_("property-images").get_public_url(file_path)

    new_img = ListingImage(listing_id=listing_id, url=url)
    db.add(new_img)
    db.commit()
    db.refresh(new_img)
    return new_img


# --- 4. UPDATE LISTING ---
@router.patch("/{listing_id}", response_model=ListingOut)
def update_listing(
    listing_id: int,
    payload: ListingUpdate,
    x_tenant_id: int = Header(..., alias="X-Tenant-Id"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 1. Find the property
    listing = (
        db.query(Listing)
        .filter(Listing.id == listing_id, Listing.tenant_id == x_tenant_id)
        .first()
    )

    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    # 2. Extract the data being sent from Swagger
    update_data = payload.model_dump(exclude_unset=True)

    # 3. Apply the changes
    for key, value in update_data.items():
        setattr(listing, key, value)

    # 4. SMART SECURITY RULE (The Fix):
    # Only reset to 'unverified' if the user is NOT sending a specific status.
    # This allows you to verify the property without the code overriding you.
    if "status" not in update_data:
        listing.status = "unverified"

    db.commit()
    db.refresh(listing)
    return listing


# --- ADD THIS TO THE BOTTOM OF backend/app/listings/router.py ---


@router.get("/admin/trust-monitor", tags=["Super Admin"])
async def monitor_platform_trust(
    db: Session = Depends(get_db),
    x_tenant_id: str = Header(None),  # Using str to match your header style
):
    """
    Super Admin Endpoint: Returns a 'Truth Report' for all listings.
    Only accessible if X-Tenant-Id is '1' (est8go).
    """
    if x_tenant_id != "1":
        return {"error": "Unauthorized. Super Admin only."}

    from app.services.trust_engine import calculate_confidence_score, get_trust_label

    listings = db.query(Listing).all()
    report = []

    for item in listings:
        score = calculate_confidence_score(item)
        label = get_trust_label(score)

        report.append(
            {
                "id": item.id,
                "title": item.title,
                "tenant_name": item.tenant.name if item.tenant else "Unknown",
                "location": item.location,
                "trust_score": score,
                "status_color": label["color"],
                "status_text": label["text"],
                "gps_provided": (
                    True
                    if (getattr(item, "latitude", None) or getattr(item, "lat", None))
                    else False
                ),
            }
        )

    return report
