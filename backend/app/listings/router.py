import os
import logging
from typing import Optional, List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, Form, File, UploadFile, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from supabase import create_client, Client

logger = logging.getLogger(__name__)

# Database & Auth
from app.database.db import get_db
from app.auth.deps import get_current_user, require_superuser
from app.users.models import User
from app.listings.models import Listing, ListingImage
from app.tenants.models import Tenant  # <--- SOCKET THIS LINE HERE

# Schemas
# These are now all used below to satisfy Ruff/Pylance
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

router = APIRouter(prefix="/listings", tags=["Listings"])


def get_tenant_id_from_user(
    current_user: User,
    x_tenant_id: Optional[int] = None,
) -> int:
    """
    Returns verified tenant_id.
    Superusers may pass X-Tenant-Id to scope to a specific tenant.
    Regular users always use their own tenant_id — no header override possible.
    """
    if current_user.role in ("superuser", "super_staff"):
        return x_tenant_id or current_user.tenant_id
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="No tenant associated with this account")
    return current_user.tenant_id


# Supabase Initialization
URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_KEY")
supabase_client: Optional[Client] = None
if URL and KEY:
    try:
        supabase_client = create_client(URL, KEY)
    except Exception:
        print("⚠️ Supabase Storage connection failed.")


# ---------------------------------------------------------
# 1. REALTOR PORTAL: PREMIUM ON-SITE UPLOAD
# ---------------------------------------------------------
@router.post("/realtor/upload", tags=["Realtor Portal"])
async def realtor_upload_property(
    db: Session = Depends(get_db),
    x_tenant_id: int = Header(..., alias="X-Tenant-Id"),
    title: str = Form(...),
    price: int = Form(...),
    location_name: str = Form(...),
    prop_type: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    images: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
):
    """THE TRUTH UPLOAD: Verifies site presence and saves images to the cloud."""
    try:
        if current_user.tenant_id != x_tenant_id:
            raise HTTPException(status_code=403, detail="Unauthorized Tenant Access")

        gps_score = verify_gps_proximity(location_name, latitude, longitude)

        new_listing = Listing(
            tenant_id=x_tenant_id,
            title=title,
            price=price,
            location=location_name,
            property_type=prop_type,
            latitude=latitude,
            longitude=longitude,
            status="verified" if gps_score >= 80 else "pending_review",
            source="realtor_portal",
        )
        new_listing.gps_verified_at = datetime.now(timezone.utc)
        db.add(new_listing)
        db.commit()
        db.refresh(new_listing)

        if supabase_client and images:
            for img in images:
                file_content = await img.read()
                file_path = (
                    f"listings/{new_listing.id}/{os.urandom(4).hex()}_{img.filename}"
                )
                supabase_client.storage.from_("property-images").upload(
                    path=file_path,
                    file=file_content,
                    file_options={"content-type": img.content_type},
                )
                url = supabase_client.storage.from_("property-images").get_public_url(
                    file_path
                )
                db.add(ListingImage(listing_id=new_listing.id, url=url))
            db.commit()

        # Recalculate and persist trust score after all data is saved
        gps_pts     = 30 if new_listing.latitude and new_listing.longitude else 0
        ai_pts      = 20 if getattr(new_listing, 'ai_verified_real', False) else 0
        doc_pts     = getattr(new_listing, 'document_score', 0) or 0
        witness_pts = min((getattr(new_listing, 'witness_count', 0) or 0) * 5, 10)
        total       = gps_pts + ai_pts + doc_pts + witness_pts

        new_listing.trust_score = total
        new_listing.trust_grade = (
            'emerald' if total >= 85 else
            'gold'    if total >= 70 else
            'silver'  if total >= 55 else
            'bronze'  if total > 0  else
            'ungraded'
        )
        db.commit()

        label = get_trust_label(total)

        feedback = (
            "To reach 85% (Emerald Green), please add a landmark and wait for AI audit."
        )
        if gps_score < 80:
            feedback = (
                "⚠️ GPS Mismatch: Ensure you are standing ON-SITE when uploading."
            )

        return {
            "status": "success",
            "listing_id": new_listing.id,
            "trust_score": total,
            "trust_grade": new_listing.trust_grade,
            "gps_verified_at": new_listing.gps_verified_at.isoformat(),
            "verification": {
                "score": f"{total}%",
                "label": label["text"],
                "color": label["color"],
                "coaching": feedback,
            },
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------
# 2. SUPER ADMIN: PLATFORM TRUTH MONITOR
# ---------------------------------------------------------
@router.get("/admin/trust-monitor", tags=["Super Admin"])
async def monitor_platform_trust(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superuser),
):

    # ... rest of function ...
    listings = db.query(Listing).all()
    return [
        {
            "id": i.id,
            "title": i.title,
            "status": i.status,  # 🔹 SOCKET: Must have this for the JS button logic
            "realtor": i.tenant.name if i.tenant else "Unknown",
            "location": i.location or "N/A",
            "trust_score": calculate_confidence_score(i),
            "status_color": get_trust_label(calculate_confidence_score(i))["color"],
            "status_text": get_trust_label(calculate_confidence_score(i))["text"],
            "gps_verified": True if i.latitude else False,
        }
        for i in listings
    ]


# ---------------------------------------------------------
# 3. PROGRAMMATIC CRUD (Satisfies ListingOut and ListingImageOut usage)
# ---------------------------------------------------------


@router.get("/", response_model=List[ListingOut])
def get_my_listings(
    x_tenant_id: Optional[int] = Header(None, alias="X-Tenant-Id"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns all listings for the authenticated tenant."""
    tenant_id = get_tenant_id_from_user(current_user, x_tenant_id)
    return db.query(Listing).filter(Listing.tenant_id == tenant_id).all()


@router.post("/", response_model=ListingOut)
def create_programmatic_listing(
    payload: ListingCreate,
    x_tenant_id: Optional[int] = Header(None, alias="X-Tenant-Id"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Programmatic API for listing creation."""
    tenant_id = get_tenant_id_from_user(current_user, x_tenant_id)
    new_listing = Listing(tenant_id=tenant_id, **payload.model_dump())
    db.add(new_listing)
    db.commit()
    db.refresh(new_listing)
    return new_listing


@router.get("/{listing_id}/images", response_model=List[ListingImageOut])
def get_property_images(
    listing_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if current_user.role not in ("superuser", "super_staff"):
        if listing.tenant_id != current_user.tenant_id:
            raise HTTPException(status_code=403, detail="Access denied")
    return db.query(ListingImage).filter(ListingImage.listing_id == listing_id).all()


@router.patch("/{listing_id}", response_model=ListingOut)
def update_listing(
    listing_id: int,
    payload: ListingUpdate,
    x_tenant_id: Optional[int] = Header(None, alias="X-Tenant-Id"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Updates property details while maintaining multi-tenant isolation."""
    tenant_id = get_tenant_id_from_user(current_user, x_tenant_id)
    listing = (
        db.query(Listing)
        .filter(Listing.id == listing_id, Listing.tenant_id == tenant_id)
        .first()
    )
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(listing, key, value)

    db.commit()
    db.refresh(listing)
    return listing


@router.get("/admin/system-stats", tags=["Super Admin"])
async def get_system_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superuser),
):

    return {
        "total_listings": db.query(Listing).count(),
        "total_tenants": db.query(Tenant).count(),
        "total_users": db.query(User).count(),
        "pending_verifications": db.query(Listing)
        .filter(Listing.status == "pending_review")
        .count(),
    }


@router.get("/admin/tenants-list", tags=["Super Admin"])
async def get_all_tenants(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superuser),
):

    return db.query(Tenant).all()


@router.patch("/admin/verify/{listing_id}", tags=["Super Admin"])
async def verify_listing_manually(
    listing_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superuser),
):
    """
    Super Admin Switch: Manually promotes a listing to 'verified' status.
    """

    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    # The Logic: Promote to Verified
    listing.status = "verified"
    db.commit()

    return {"status": "success", "message": f"Property #{listing_id} is now Verified."}


# 🔹 SOCKET: Add to the bottom of listings/router.py


@router.delete("/admin/delete/{listing_id}", tags=["Super Admin"])
async def delete_listing_manually(
    listing_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superuser),
):
    """
    Super Admin Command: Permanently removes a listing (e.g., if Sold or Fake).
    """

    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    db.delete(listing)
    db.commit()

    return {"status": "success", "message": f"Listing #{listing_id} deleted."}


# ---------------------------------------------------------
# 6. TRUST CERTIFICATE — PDF download (costs 20 credits)
# ---------------------------------------------------------

@router.get("/{listing_id}/trust-certificate")
async def generate_trust_certificate_pdf(
    listing_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generates and returns a PDF trust certificate.
    Costs 20 Est8 Credits.
    """
    tenant_id = current_user.tenant_id
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No tenant associated")

    listing = db.query(Listing).filter(
        Listing.id == listing_id,
        Listing.tenant_id == tenant_id,
    ).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    from app.credits.service import get_balance, deduct_credits

    balance = get_balance(tenant_id, db)
    if balance["available"] < 20:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Not enough credits. "
                f"Trust Certificate costs 20 credits. "
                f"You have {balance['available']} available."
            ),
        )

    from app.company_profiles.models import CompanyProfile

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    profile = db.query(CompanyProfile).filter(
        CompanyProfile.tenant_id == tenant_id
    ).first()

    try:
        from app.services.trust_certificate_service import (
            generate_trust_certificate as gen_cert,
        )
        pdf_bytes = gen_cert(listing, tenant, profile)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Certificate generation failed: {e}")
        raise HTTPException(status_code=500, detail="Certificate generation failed")

    # Deduct credits AFTER successful generation
    try:
        deduct_credits(
            tenant_id=tenant_id,
            action="TRUST_CERTIFICATE",
            tier=current_user.role or "ACCESS",
            reference=f"cert_{listing_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            db=db,
        )
    except Exception as e:
        logger.warning(f"Credit deduction failed for cert: {e}")

    filename = f"est8go_trust_cert_{listing_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
