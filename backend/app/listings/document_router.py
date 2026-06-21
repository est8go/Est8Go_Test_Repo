"""
EST8GO DOCUMENT UPLOAD ROUTER
================================
Realtor Portal endpoints for:
    1. Property creation with GPS verification
    2. Document uploads (C of O, Deed, Survey, etc.)
    3. AI Vision audit trigger
    4. Trust score recalculation
    5. GPS capture on-site

Add this router to your main.py:
    from app.listings.document_router import router as document_router
    app.include_router(document_router)
"""

import os
import hashlib
import logging
from datetime import datetime, timedelta
from typing import List, Optional

logger = logging.getLogger(__name__)

from fastapi import (
    APIRouter,
    Depends,
    Header,
    Form,
    File,
    UploadFile,
    HTTPException,
    BackgroundTasks,
)
from sqlalchemy.orm import Session
from supabase import create_client, Client
from pydantic import BaseModel

from app.database.db import get_db
from app.auth.deps import get_current_user
from app.users.models import User, PLATFORM_ROLES
from app.listings.models import Listing, ListingImage, ListingDocument
from app.services.trust_engine import (
    verify_gps_proximity,
    calculate_confidence_score,
    get_trust_label,
)
from app.services.document_trust_engine import (
    DOCUMENT_SCORES,
    calculate_document_score,
)
from app.services.ai_vision_service import audit_and_update_listing

router = APIRouter(prefix="/listings", tags=["Realtor Portal"])

# Supabase client
URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_KEY")
supabase_client: Optional[Client] = None
if URL and KEY:
    try:
        supabase_client = create_client(URL, KEY)
    except Exception:
        print("⚠️ Supabase Storage unavailable")


# ================================================================
# HELPERS
# ================================================================


def upload_to_supabase(
    file_content: bytes,
    file_path: str,
    content_type: str,
    bucket: str = "property-images",
) -> str:
    """Uploads file to Supabase Storage and returns public URL."""
    if not supabase_client:
        raise HTTPException(status_code=503, detail="Storage service unavailable")
    supabase_client.storage.from_(bucket).upload(
        path=file_path,
        file=file_content,
        file_options={"content-type": content_type},
    )
    return supabase_client.storage.from_(bucket).get_public_url(file_path)


def hash_document(content: bytes) -> str:
    """Generates SHA-256 hash for document tamper detection."""
    return hashlib.sha256(content).hexdigest()


def get_listing_or_404(listing_id: int, tenant_id: int, db: Session) -> Listing:
    """Fetches listing with tenant isolation."""
    listing = (
        db.query(Listing)
        .filter(Listing.id == listing_id, Listing.tenant_id == tenant_id)
        .first()
    )
    if not listing:
        raise HTTPException(
            status_code=404, detail="Listing not found or access denied"
        )
    return listing


def _is_platform(user: User) -> bool:
    """Platform users (superuser/super_staff) are cross-tenant by design."""
    return bool(getattr(user, "is_platform_user", False)) or (
        getattr(user, "effective_role", None) in PLATFORM_ROLES
    )


def _effective_tenant_id(user: User, x_tenant_id: int) -> int:
    """Resolve the tenant to scope by.

    Tenant users: ALWAYS their own ``current_user.tenant_id`` — never the raw
    header (defense-in-depth; the header is also enforced by get_current_user).
    Platform users have no tenant_id of their own, so they scope by the
    X-Tenant-Id header (cross-tenant access is intentional for them).
    """
    if _is_platform(user):
        return x_tenant_id
    return user.tenant_id


# ================================================================
# 1. GPS CAPTURE ON-SITE
# ================================================================


@router.post("/{listing_id}/capture-gps", tags=["Realtor Portal"])
async def capture_gps_on_site(
    listing_id: int,
    latitude: float = Form(...),
    longitude: float = Form(...),
    x_tenant_id: int = Header(..., alias="X-Tenant-Id"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    THE TRUTH BUTTON:
    Realtor must be physically on-site to call this endpoint.
    Records GPS coordinates, verifies against claimed location,
    and sets the 60-day verification window.
    """
    listing = get_listing_or_404(listing_id, x_tenant_id, db)

    # Verify GPS proximity against claimed location
    proximity_score = verify_gps_proximity(listing.location, latitude, longitude)
    location_match = proximity_score >= 80

    # Record GPS capture
    listing.latitude = latitude
    listing.longitude = longitude
    listing.gps_verified_at = datetime.utcnow()
    listing.gps_expires_at = datetime.utcnow() + timedelta(days=60)
    listing.gps_location_match = location_match

    # Update status
    if location_match:
        listing.status = "verified"
    else:
        listing.status = "pending_review"

    # Recalculate trust score
    new_score = calculate_confidence_score(listing)
    label = get_trust_label(new_score)
    listing.trust_score = new_score
    listing.trust_grade = label["grade"]

    db.commit()

    # Build coaching feedback
    if location_match:
        coaching = (
            f"✅ GPS verified! You are confirmed on-site at *{listing.location}*. "
            f"Your listing is now active. Upload documents to increase your trust score."
        )
    else:
        coaching = (
            f"⚠️ GPS Mismatch: Your coordinates are {proximity_score}% accurate. "
            f"Ensure you are standing ON the property, not nearby. "
            f"Try again from the exact site location."
        )

    return {
        "status": "verified" if location_match else "mismatch",
        "proximity_score": proximity_score,
        "location_match": location_match,
        "gps_expires_at": listing.gps_expires_at.isoformat(),
        "trust_score": new_score,
        "trust_label": label["text"],
        "trust_color": label["color"],
        "coaching": coaching,
    }


# ================================================================
# 2. DOCUMENT UPLOAD
# ================================================================


@router.post("/{listing_id}/upload-document", tags=["Realtor Portal"])
async def upload_listing_document(
    listing_id: int,
    document_type: str = Form(
        ...,
        description=(
            "Document type key. Options: c_of_o, r_of_o, governors_consent, "
            "gazette, excision, approved_layout, deed_of_assignment, "
            "deed_of_conveyance, contract_of_sale, survey_plan, site_plan, "
            "building_plan_approval, tax_clearance, purchase_receipts, "
            "power_of_attorney, probate"
        ),
    ),
    document: UploadFile = File(...),
    x_tenant_id: int = Header(..., alias="X-Tenant-Id"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    DOCUMENT TRUTH UPLOAD:
    Accepts Nigerian real estate documents, hashes them for
    tamper detection, uploads to Supabase, and updates trust score.
    """
    # Validate document type
    if document_type not in DOCUMENT_SCORES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid document type: '{document_type}'. "
                f"Valid types: {list(DOCUMENT_SCORES.keys())}"
            ),
        )

    listing = get_listing_or_404(listing_id, x_tenant_id, db)

    # Read and hash document
    content = await document.read()
    doc_hash = hash_document(content)
    doc_info = DOCUMENT_SCORES[document_type]

    # Upload to the PRIVATE property-documents bucket. We deliberately do NOT
    # call get_public_url for documents — they are served ONLY via the
    # access-controlled proxy route (A2.2), never a public URL. We keep the
    # object path (storage_path), which is exactly what the proxy's
    # download(doc.storage_path) reads back.
    if not supabase_client:
        raise HTTPException(status_code=503, detail="Storage service unavailable")
    storage_path = (
        f"documents/{listing_id}/"
        f"{document_type}_{os.urandom(4).hex()}_{document.filename}"
    )
    try:
        supabase_client.storage.from_("property-documents").upload(
            path=storage_path,
            file=content,
            file_options={
                "content-type": document.content_type or "application/pdf"
            },
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Document upload failed: {str(e)}")

    # Update listing document flags
    flag_map = {
        "c_of_o": "cof_uploaded",
        "r_of_o": "cof_uploaded",  # same flag — both are Tier 1
        "deed_of_assignment": "deed_uploaded",
        "deed_of_conveyance": "deed_uploaded",
        "survey_plan": "survey_uploaded",
    }
    flag = flag_map.get(document_type)
    if flag:
        setattr(listing, flag, True)

    # Persist the document record — this row is now the SOURCE OF TRUTH.
    # tenant_id comes from the validated listing (never user input).
    # visibility is safe-by-default ("on_request") — private until the agency
    # opts a document into "viewable" via A4. storage_path is the object path
    # the proxy route downloads.
    new_doc = ListingDocument(
        listing_id=listing.id,
        tenant_id=listing.tenant_id,
        doc_type=document_type,
        label=doc_info["label"],
        tier=doc_info["tier"],
        score_value=doc_info["score"],
        storage_path=storage_path,
        file_url=None,            # NEVER a public URL for a document
        file_hash=doc_hash,
        visibility="on_request",  # safe-by-default
        uploaded_by_id=current_user.id,
        uploaded_by_email=current_user.email,
        uploaded_at=datetime.utcnow(),
    )
    db.add(new_doc)

    # Documents now exist for this listing — flip none -> on_request on the
    # first upload. Never downgrade an already-"viewable" listing.
    if (getattr(listing, "documents_status", None) or "none") == "none":
        listing.documents_status = "on_request"

    # Collect all uploaded doc keys
    uploaded_keys = _get_uploaded_doc_keys(listing)
    if document_type not in uploaded_keys:
        uploaded_keys.append(document_type)

    # Recalculate document score
    doc_result = calculate_document_score(uploaded_keys)

    # Update document score on listing
    listing.document_score = doc_result.final_score

    # Recalculate full trust score
    new_score = calculate_confidence_score(listing)
    label = get_trust_label(new_score)
    listing.trust_score = new_score
    listing.trust_grade = label["grade"]

    db.commit()

    try:
        from app.credits.service import deduct_credits
        deduct_credits(
            tenant_id = listing.tenant_id,
            action    = "DOCUMENT_UPLOAD",
            tier      = "ACCESS",
            reference = f"doc_{listing_id}",
            db        = db,
        )
    except Exception as e:
        logger.warning(f"Credit deduction failed for doc: {e}")

    return {
        "status": "uploaded",
        "document_type": document_type,
        "document_label": doc_info["label"],
        "document_tier": f"Tier {doc_info['tier']}",
        "points_awarded": doc_info["score"],
        "document_hash": doc_hash[:16] + "...",  # partial hash for display
        "document_id": new_doc.id,  # use the guarded proxy route to view
        "document_score": doc_result.final_score,
        "trust_score": new_score,
        "trust_label": label["text"],
        "trust_color": label["color"],
        "trust_grade": label["grade"],
        "upgrade_path": doc_result.upgrade_path,
        "emerald_ready": label["grade"] == "emerald",
        "missing_for_emerald": [
            DOCUMENT_SCORES[k]["label"] for k in doc_result.missing_emerald_docs
        ],
    }


# ================================================================
# 2b. DOCUMENT MANAGEMENT (A4) — list + per-doc visibility control
# ================================================================
# Safe-by-default: documents are uploaded as "on_request" (private). An
# agency must explicitly opt a document into "viewable" before the public
# proxy route will serve it. documents_status is DERIVED from per-doc
# visibility (single source of truth) so the listing headline can never
# claim "viewable" while every document is still private.


_VISIBILITY_VALUES = {"viewable", "on_request"}


class VisibilityUpdate(BaseModel):
    visibility: str


def _doc_metadata(doc: ListingDocument, is_verified: bool) -> dict:
    """Browser-safe document metadata. NEVER includes storage_path/file_url —
    the file is reachable only through the access-controlled proxy route."""
    return {
        "id": doc.id,
        "doc_type": doc.doc_type,
        "label": doc.label,
        "tier": doc.tier,
        "visibility": doc.visibility,
        "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
        # is_viewable tells the UI when a view-link would ACTUALLY resolve:
        # the proxy requires BOTH visibility=="viewable" AND a verified listing.
        "is_viewable": (doc.visibility == "viewable" and is_verified),
    }


def _derive_documents_status(listing: Listing, db: Session) -> str:
    """Recompute the listing headline from per-doc visibility.
    any viewable -> "viewable"; else any doc -> "on_request"; else "none"."""
    docs = (
        db.query(ListingDocument)
        .filter(
            ListingDocument.listing_id == listing.id,
            ListingDocument.tenant_id == listing.tenant_id,
        )
        .all()
    )
    if any(d.visibility == "viewable" for d in docs):
        status = "viewable"
    elif docs:
        status = "on_request"
    else:
        status = "none"
    listing.documents_status = status
    return status


@router.get("/{listing_id}/documents", tags=["Realtor Portal"])
async def list_listing_documents(
    listing_id: int,
    x_tenant_id: int = Header(..., alias="X-Tenant-Id"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List a listing's documents (metadata only) for the agency dashboard.

    Tenant-scoped: a tenant user can only ever see its OWN listings' docs.
    Never returns storage_path/file_url.
    """
    tenant_id = _effective_tenant_id(current_user, x_tenant_id)
    listing = get_listing_or_404(listing_id, tenant_id, db)

    # Defense-in-depth: re-verify ownership for tenant users (404, never 403).
    if not _is_platform(current_user) and listing.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Listing not found or access denied")

    is_verified = listing.status == "verified"
    docs = (
        db.query(ListingDocument)
        .filter(
            ListingDocument.listing_id == listing.id,
            ListingDocument.tenant_id == listing.tenant_id,
        )
        .order_by(ListingDocument.uploaded_at.asc())
        .all()
    )

    return {
        "listing_id": listing.id,
        "documents_status": getattr(listing, "documents_status", None) or "none",
        "documents": [_doc_metadata(d, is_verified) for d in docs],
    }


@router.patch(
    "/{listing_id}/documents/{doc_id}/visibility", tags=["Realtor Portal"]
)
async def set_document_visibility(
    listing_id: int,
    doc_id: int,
    payload: VisibilityUpdate,
    x_tenant_id: int = Header(..., alias="X-Tenant-Id"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Flip a single document between "viewable" and "on_request".

    The doc is fetched scoped by id AND listing_id AND tenant — never doc_id
    alone — so tenant A can never toggle tenant B's doc via its own URL.
    """
    # Strict enum validation — reject anything else.
    if payload.visibility not in _VISIBILITY_VALUES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid visibility. Allowed: {sorted(_VISIBILITY_VALUES)}",
        )

    tenant_id = _effective_tenant_id(current_user, x_tenant_id)
    listing = get_listing_or_404(listing_id, tenant_id, db)

    if not _is_platform(current_user) and listing.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Listing not found or access denied")

    # Scope by id + listing_id + tenant. 404 (not 403) on any mismatch.
    doc = (
        db.query(ListingDocument)
        .filter(
            ListingDocument.id == doc_id,
            ListingDocument.listing_id == listing.id,
            ListingDocument.tenant_id == listing.tenant_id,
        )
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")

    doc.visibility = payload.visibility

    # Re-derive the listing headline from per-doc visibility (autoflush makes
    # the just-set value visible to the query inside the helper).
    new_status = _derive_documents_status(listing, db)

    db.commit()
    db.refresh(doc)
    db.refresh(listing)

    is_verified = listing.status == "verified"
    return {
        "listing_id": listing.id,
        "documents_status": new_status,
        "document": _doc_metadata(doc, is_verified),
    }


# ================================================================
# 3. PHOTO UPLOAD WITH AI VISION TRIGGER
# ================================================================


@router.post("/{listing_id}/upload-photos", tags=["Realtor Portal"])
async def upload_listing_photos(
    listing_id: int,
    background_tasks: BackgroundTasks,
    images: List[UploadFile] = File(...),
    x_tenant_id: int = Header(..., alias="X-Tenant-Id"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    PHOTO TRUTH UPLOAD:
    Uploads property photos to Supabase and triggers AI Vision
    audit in the background. Trust score updates automatically
    when audit completes.
    """
    listing = get_listing_or_404(listing_id, x_tenant_id, db)

    uploaded_urls = []

    for img in images:
        content = await img.read()
        file_path = f"listings/{listing_id}/" f"{os.urandom(4).hex()}_{img.filename}"
        try:
            url = upload_to_supabase(
                content, file_path, img.content_type or "image/jpeg"
            )
            db.add(ListingImage(listing_id=listing_id, url=url))
            uploaded_urls.append(url)
        except Exception as e:
            raise HTTPException(
                status_code=503, detail=f"Photo upload failed: {str(e)}"
            )

    db.commit()

    # Trigger AI Vision audit in background
    # Does not block the response — Realtor gets instant feedback
    background_tasks.add_task(audit_and_update_listing, listing, db)

    return {
        "status": "uploaded",
        "photos_added": len(uploaded_urls),
        "urls": uploaded_urls,
        "audit_status": "AI Vision audit running in background...",
        "message": (
            f"✅ {len(uploaded_urls)} photos uploaded for *{listing.title}*. "
            f"AI audit is running — your trust score will update shortly."
        ),
    }


# ================================================================
# 4. TRUST SCORE DASHBOARD (Realtor View)
# ================================================================


@router.get("/{listing_id}/trust-dashboard", tags=["Realtor Portal"])
async def get_trust_dashboard(
    listing_id: int,
    x_tenant_id: int = Header(..., alias="X-Tenant-Id"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    TRUST SCORE WIZARD:
    Shows Realtor exactly what their listing scores on each pillar
    and what actions will raise it to Emerald.
    """
    listing = get_listing_or_404(listing_id, x_tenant_id, db)

    uploaded_keys = _get_uploaded_doc_keys(listing)
    doc_result = calculate_document_score(uploaded_keys)
    trust_score = calculate_confidence_score(listing)
    label = get_trust_label(trust_score)

    # GPS status
    gps_verified = bool(listing.gps_verified_at)
    gps_expired = False
    if listing.gps_expires_at:
        gps_expired = datetime.utcnow() > listing.gps_expires_at

    # Build pillar breakdown
    pillars = {
        "gps": {
            "label": "GPS On-Site Verification",
            "max": 30,
            "earned": _gps_score(listing),
            "verified": gps_verified,
            "expired": gps_expired,
            "action": (
                "✅ GPS verified and active"
                if gps_verified and not gps_expired
                else (
                    "⚠️ Re-verify GPS — press 'Capture Site GPS' on-site"
                    if gps_expired
                    else "❌ Visit the property and press 'Capture Site GPS'"
                )
            ),
        },
        "ai_vision": {
            "label": "AI Vision Audit",
            "max": 20,
            "earned": 20 if listing.ai_verified_real else 0,
            "verified": listing.ai_verified_real,
            "action": (
                "✅ Photos passed AI audit"
                if listing.ai_verified_real
                else "❌ Upload property photos to trigger AI audit"
            ),
        },
        "documents": {
            "label": "Document Verification",
            "max": 40,
            "earned": int((doc_result.final_score / 100) * 40),
            "doc_score": doc_result.final_score,
            "uploaded": [
                DOCUMENT_SCORES[k]["label"]
                for k in uploaded_keys
                if k in DOCUMENT_SCORES
            ],
            "missing_for_emerald": [
                DOCUMENT_SCORES[k]["label"] for k in doc_result.missing_emerald_docs
            ],
            "bonuses": doc_result.bonuses_applied,
            "action": doc_result.upgrade_path,
        },
        "witnesses": {
            "label": "Buyer Visit Confirmations",
            "max": 10,
            "earned": min((listing.witness_count or 0) * 2, 10),
            "count": listing.witness_count or 0,
            "action": (
                "✅ Strong witness signals"
                if (listing.witness_count or 0) >= 5
                else f"Schedule site visits to earn witness confirmations "
                f"({listing.witness_count or 0}/5 so far)"
            ),
        },
    }

    pts_to_emerald = max(0, 85 - trust_score)

    return {
        "listing_id": listing_id,
        "title": listing.title,
        "trust_score": trust_score,
        "trust_label": label["text"],
        "trust_color": label["color"],
        "trust_grade": label["grade"],
        "emerald_ready": label["grade"] == "emerald",
        "pts_to_emerald": pts_to_emerald,
        "pillars": pillars,
        "upgrade_path": doc_result.upgrade_path,
        "gps_expires_at": (
            listing.gps_expires_at.isoformat() if listing.gps_expires_at else None
        ),
    }


# ================================================================
# 5. WITNESS CONFIRMATION (Buyer Visit Signal)
# ================================================================


@router.post("/{listing_id}/confirm-visit", tags=["Public"])
async def confirm_buyer_visit(
    listing_id: int,
    buyer_phone: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    WITNESS SIGNAL:
    Called after a buyer physically visits a property.
    Increments witness count and updates trust score.
    No authentication required — public endpoint.
    """
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    # Increment witness count
    listing.witness_count = (listing.witness_count or 0) + 1

    # Recalculate trust score
    new_score = calculate_confidence_score(listing)
    label = get_trust_label(new_score)
    listing.trust_score = new_score
    listing.trust_grade = label["grade"]

    db.commit()

    return {
        "status": "confirmed",
        "witness_count": listing.witness_count,
        "trust_score": new_score,
        "trust_label": label["text"],
        "message": (
            f"✅ Visit confirmed for *{listing.title}*. "
            f"Trust score updated to {new_score}/100."
        ),
    }


# ================================================================
# HELPERS
# ================================================================


def _get_uploaded_doc_keys(listing: Listing) -> list:
    """Returns list of document keys based on listing upload flags."""
    keys = []
    if getattr(listing, "cof_uploaded", False):
        keys.append("c_of_o")
    if getattr(listing, "deed_uploaded", False):
        keys.append("deed_of_assignment")
    if getattr(listing, "survey_uploaded", False):
        keys.append("survey_plan")
    return keys


def _gps_score(listing: Listing) -> int:
    """Calculates current GPS pillar score."""
    if not listing.gps_verified_at:
        return 0
    if listing.gps_expires_at and datetime.utcnow() > listing.gps_expires_at:
        return 10  # expired

    score = 15  # coordinates captured
    if getattr(listing, "gps_location_match", False):
        score += 10
    if getattr(listing, "gps_photo_match", False):
        score += 5
    return score
