import os
import logging
from typing import Optional, List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, Form, File, UploadFile, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import or_
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
    AssignRealtorRequest,
)

# Trust Moat Logic
from app.services.trust_engine import (
    verify_gps_proximity,
    calculate_confidence_score,
    get_trust_label,
)

router = APIRouter(prefix="/listings", tags=["Listings"])


# ──────────────────────────────────────────────────────────────────
# SINGLE SOURCE OF TRUTH: trust score formula
# GPS:30 | AI:20 | Docs:40 | Witness:10 — matches trust tab display
# ──────────────────────────────────────────────────────────────────
def calculate_listing_trust(listing) -> tuple:
    gps_score = 30 if (
        getattr(listing, 'latitude', None)
        and getattr(listing, 'longitude', None)
        and getattr(listing, 'gps_verified_at', None)
    ) else 0

    ai_score = 20 if getattr(listing, 'ai_verified_real', False) else 0

    doc_score = min(getattr(listing, 'document_score', 0) or 0, 40)

    witness_score = min(
        (getattr(listing, 'witness_count', 0) or 0) * 5, 10
    )

    total = gps_score + ai_score + doc_score + witness_score

    grade = (
        'emerald' if total >= 85 else
        'gold'    if total >= 70 else
        'silver'  if total >= 55 else
        'bronze'  if total > 0  else
        'ungraded'
    )
    return total, grade


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
    directions: Optional[str] = Form(None),
    images: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
):
    """THE TRUTH UPLOAD: Verifies site presence and saves images to the cloud."""
    try:
        if current_user.tenant_id != x_tenant_id:
            raise HTTPException(status_code=403, detail="Unauthorized Tenant Access")

        gps_score = verify_gps_proximity(location_name, latitude, longitude)

        # All new listings start as pending_review — Super Admin verifies
        new_listing = Listing(
            tenant_id=x_tenant_id,
            title=title,
            price=price,
            location=location_name,
            property_type=prop_type,
            latitude=latitude,
            longitude=longitude,
            directions=directions,
            status="pending_review",
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

        # Calculate and persist trust score using the single source of truth
        total, grade = calculate_listing_trust(new_listing)
        new_listing.trust_score = total
        new_listing.trust_grade = grade
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


@router.get("/")
def get_my_listings(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    search: str = Query(None),
    property_type: str = Query(None),
    sort_by: str = Query("trust_score"),
    sort_dir: str = Query("desc"),
    x_tenant_id: Optional[int] = Header(None, alias="X-Tenant-Id"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns paginated verified listings with stats for the authenticated tenant."""
    tenant_id = get_tenant_id_from_user(current_user, x_tenant_id)

    # Base query — verified listings only
    base_q = db.query(Listing).filter(
        Listing.tenant_id == tenant_id,
        Listing.status == "verified",
    )

    # Search
    if search:
        term = f"%{search}%"
        base_q = base_q.filter(
            or_(Listing.title.ilike(term), Listing.location.ilike(term))
        )

    # Property type filter
    if property_type:
        base_q = base_q.filter(Listing.property_type == property_type)

    # Sorting — whitelist to prevent injection
    _SORT_FIELDS = {"trust_score", "price", "created_at"}
    sort_field = sort_by if sort_by in _SORT_FIELDS else "trust_score"
    sort_col = getattr(Listing, sort_field, Listing.trust_score)
    base_q = base_q.order_by(
        sort_col.asc() if sort_dir == "asc" else sort_col.desc()
    )

    # Count before pagination
    total = base_q.count()

    # Paginate
    offset = (page - 1) * limit
    rows = base_q.offset(offset).limit(limit).all()

    # Aggregate stats — always over all verified listings (ignores search/type)
    all_q = db.query(Listing).filter(
        Listing.tenant_id == tenant_id,
        Listing.status == "verified",
    )
    total_all  = all_q.count()
    gps_count  = all_q.filter(Listing.gps_verified_at.isnot(None)).count()
    docs_count = all_q.filter(Listing.document_score > 0).count()
    unassigned = all_q.filter(Listing.assigned_realtor_id.is_(None)).count()

    # Enrich with realtor info
    result = []
    for listing in rows:
        out = ListingOut.model_validate(listing)
        if listing.assigned_realtor_id:
            realtor = db.query(User).filter(
                User.id == listing.assigned_realtor_id
            ).first()
            if realtor:
                out.assigned_realtor_name = (
                    realtor.first_name or realtor.email.split("@")[0]
                )
                out.assigned_realtor_phone = realtor.phone_number
        result.append(out)

    pages = max(1, (total + limit - 1) // limit)

    return {
        "listings": result,
        "total": total,
        "page": page,
        "pages": pages,
        "limit": limit,
        "stats": {
            "total_all":      total_all,
            "gps_verified":   gps_count,
            "with_documents": docs_count,
            "unassigned":     unassigned,
        },
    }


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


@router.patch("/{listing_id}/assign")
def assign_realtor_to_listing(
    listing_id: int,
    payload: AssignRealtorRequest,
    x_tenant_id: Optional[int] = Header(None, alias="X-Tenant-Id"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Assign or unassign a realtor to a listing.
    Tenant admin only. Realtor must belong to same tenant.
    """
    if current_user.role not in ("admin", "superuser", "super_staff"):
        raise HTTPException(403, "Admin access required to assign listings.")

    tenant_id = get_tenant_id_from_user(current_user, x_tenant_id)

    listing = db.query(Listing).filter(
        Listing.id == listing_id,
        Listing.tenant_id == tenant_id,
    ).first()
    if not listing:
        raise HTTPException(404, "Listing not found.")

    if payload.realtor_id is not None:
        realtor = db.query(User).filter(
            User.id == payload.realtor_id,
            User.tenant_id == tenant_id,
            User.is_active == True,
            User.role.in_(["realtor", "admin", "staff"]),
        ).first()
        if not realtor:
            raise HTTPException(404, "Realtor not found in your team.")
        listing.assigned_realtor_id = payload.realtor_id
    else:
        listing.assigned_realtor_id = None

    db.commit()
    db.refresh(listing)

    realtor_name = None
    if listing.assigned_realtor_id:
        r = db.query(User).filter(User.id == listing.assigned_realtor_id).first()
        realtor_name = (r.first_name or r.email) if r else None

    return {
        "success": True,
        "listing_id": listing_id,
        "assigned_realtor_id": listing.assigned_realtor_id,
        "assigned_realtor_name": realtor_name,
        "message": (
            f"Listing assigned to {realtor_name}"
            if realtor_name else "Listing unassigned"
        ),
    }


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
