import os
from typing import Optional, List
from fastapi import APIRouter, Depends, Header, Form, File, UploadFile, HTTPException
from sqlalchemy.orm import Session
from supabase import create_client, Client

# Database & Auth
from app.database.db import get_db
from app.auth.deps import get_current_user
from app.users.models import User
from app.listings.models import Listing, ListingImage

# Schemas (Now all used to satisfy Ruff/Pylance)
from app.listings.schemas import (
    ListingCreate,
    ListingUpdate,
    ListingOut,
    ListingImageOut,
)

# Trust Moat Logic
from app.services.trust_engine import (
    verify_gps_proximity,
    calculate_confidence_score,
    get_trust_label,
)

# Unified Router Prefix
router = APIRouter(prefix="/listings", tags=["Listings"])

# --- SUPABASE CONFIG ---
URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_KEY")
supabase_client: Optional[Client] = None
if URL and KEY:
    try:
        supabase_client = create_client(URL, KEY)
    except Exception:
        print("⚠️ Supabase Client initialization failed.")


# ---------------------------------------------------------
# 1. SUPER ADMIN: PLATFORM TRUTH MONITOR
# ---------------------------------------------------------
@router.get("/admin/trust-monitor", tags=["Super Admin"])
async def monitor_platform_trust(
    db: Session = Depends(get_db),
    x_tenant_id: str = Header(None),
    # Security: Only authenticated Users can monitor
    current_user: User = Depends(get_current_user),
):
    if x_tenant_id != "1" or not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Super Admin access only.")

    listings = db.query(Listing).all()
    report = []

    for item in listings:
        score = calculate_confidence_score(item)
        label = get_trust_label(score)
        report.append(
            {
                "id": item.id,
                "title": item.title,
                "realtor": item.tenant.name if item.tenant else "Unknown",
                "trust_score": score,
                "status_color": label["color"],
                "gps_verified": True if (getattr(item, "latitude", None)) else False,
            }
        )
    return report


# ---------------------------------------------------------
# 2. REALTOR PORTAL: PREMIUM ON-SITE UPLOAD
# ---------------------------------------------------------
@router.post("/realtor/upload", tags=["Realtor Portal"])
async def realtor_upload_property(
    db: Session = Depends(get_db),
    x_tenant_id: int = Header(..., alias="X-Tenant-Id"),
    title: str = Form(...),
    price: int = Form(...),  # BIGINT compatible
    location_name: str = Form(...),
    prop_type: str = Form(...),
    latitude: float = Form(...),  # Matched to Audit
    longitude: float = Form(...),  # Matched to Audit
    images: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
):
    try:
        # 1. SECURITY
        if current_user.tenant_id != x_tenant_id:
            raise HTTPException(status_code=403, detail="Unauthorized")

        # 2. TRUTH CHECK (Stage A logic)
        gps_score = verify_gps_proximity(location_name, latitude, longitude)

        # 3. CREATE LISTING (Using exact Audit column names)
        new_listing = Listing(
            tenant_id=x_tenant_id,
            title=title,
            price=price,
            location=location_name,
            property_type=prop_type,
            latitude=latitude,  # Fixed
            longitude=longitude,  # Fixed
            status="verified" if gps_score >= 80 else "pending_review",
            source="realtor_portal",
        )
        db.add(new_listing)
        db.commit()
        db.refresh(new_listing)

        # 4. CLOUD IMAGE STORAGE (Supabase)
        if supabase_client:
            for img in images:
                file_content = await img.read()
                # Surgical path: listings/ID/filename
                file_path = (
                    f"listings/{new_listing.id}/{os.urandom(4).hex()}_{img.filename}"
                )

                supabase_client.storage.from_("property-images").upload(
                    path=file_path,
                    file=file_content,
                    file_options={"content-type": img.content_type},
                )
                public_url = supabase_client.storage.from_(
                    "property-images"
                ).get_public_url(file_path)

                # Link to 'LISTING_IMAGES' table from Audit
                db.add(ListingImage(listing_id=new_listing.id, url=public_url))

            db.commit()

        return {
            "status": "success",
            "listing_id": new_listing.id,
            "gps_accuracy": gps_score,
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=ListingOut)
def create_listing_api(
    payload: ListingCreate,  # <--- FIXED: ListingCreate is now accessed
    db: Session = Depends(get_db),
    x_tenant_id: int = Header(..., alias="X-Tenant-Id"),
):
    """Standard JSON API for programmatic listing creation."""
    new_listing = Listing(tenant_id=x_tenant_id, **payload.model_dump())
    db.add(new_listing)
    db.commit()
    db.refresh(new_listing)
    return new_listing


@router.get("/{listing_id}/images", response_model=List[ListingImageOut])
def get_listing_images(listing_id: int, db: Session = Depends(get_db)):
    """FIXED: ListingImageOut is now accessed."""
    return db.query(ListingImage).filter(ListingImage.listing_id == listing_id).all()


@router.patch("/{listing_id}", response_model=ListingOut)
def update_listing(
    listing_id: int,
    payload: ListingUpdate,
    db: Session = Depends(get_db),
    x_tenant_id: int = Header(..., alias="X-Tenant-Id"),
):
    listing = (
        db.query(Listing)
        .filter(Listing.id == listing_id, Listing.tenant_id == x_tenant_id)
        .first()
    )
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(listing, key, value)

    db.commit()
    db.refresh(listing)
    return listing
