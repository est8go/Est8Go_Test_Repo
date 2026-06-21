import os
import re

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session

from app.database.db import SessionLocal
from app.services.tenant_service import (
    create_tenant_service,
    list_tenants_service,
)
from app.tenants.models import Tenant
from app.auth.deps import require_superuser, get_current_user
from app.users.models import User
from app.listings.document_router import upload_to_supabase

router = APIRouter(prefix="/tenants", tags=["Tenants"])

# Write-time CSS-injection guard: ONLY a strict #RRGGBB hex may ever reach the
# DB. The property page injects brand_color into a CSS custom property, so a
# value like "red;}body{...}" must be rejected here, before it is stored.
_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

# Logos are non-sensitive (public bucket is fine), but SVG is deliberately
# EXCLUDED: an SVG can embed <script>/onload and would be stored XSS when
# served inline. Raster formats only.
_ALLOWED_LOGO_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}
_MAX_LOGO_BYTES = 2 * 1024 * 1024  # 2 MB is ample for a logo


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/")
def create_tenant(name: str, db: Session = Depends(get_db)):
    return create_tenant_service(name, db)


@router.get("/")
def list_tenants(db: Session = Depends(get_db)):
    return list_tenants_service(db)


class CoverageCitiesPayload(BaseModel):
    cities: List[str] = []


@router.patch("/{tenant_id}/coverage-cities")
def update_coverage_cities(
    tenant_id: int,
    payload: CoverageCitiesPayload,
    db: Session = Depends(get_db),
    current_user=Depends(require_superuser),
):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    tenant.coverage_cities = payload.cities
    db.commit()
    return {"tenant_id": tenant_id, "coverage_cities": payload.cities}


# ================================================================
# AGENCY CO-BRANDING (Workstream C2) — tenant edits only ITS OWN brand
# ================================================================


class BrandColorPayload(BaseModel):
    # Optional/empty clears the colour (NULL) -> page falls back to default.
    brand_color: Optional[str] = None


@router.get("/me/branding")
def get_my_branding(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the agency's current logo + accent colour (for the dashboard
    Brand section to pre-fill). Tenant derived from the authenticated user."""
    tenant = db.get(Tenant, current_user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return {
        "tenant_id": tenant.id,
        "logo_url": tenant.logo_url,
        "brand_color": tenant.brand_color,
    }


@router.patch("/me/branding")
def update_my_branding(
    payload: BrandColorPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set (or clear) the agency accent colour.

    The tenant is derived from the authenticated user, NEVER from client
    input. The colour is the write-time CSS-injection guard: only a strict
    #RRGGBB hex is accepted; an empty value clears it; anything else is 400.
    """
    tenant = db.get(Tenant, current_user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    raw = (payload.brand_color or "").strip()
    if raw == "":
        tenant.brand_color = None            # explicit clear -> default styling
    elif _HEX_RE.match(raw):
        tenant.brand_color = raw             # only #RRGGBB ever reaches the DB
    else:
        raise HTTPException(
            status_code=400,
            detail="brand_color must be a hex colour like #4F46E5",
        )

    db.commit()
    return {"tenant_id": tenant.id, "brand_color": tenant.brand_color}


@router.post("/me/logo")
async def upload_my_logo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload the agency logo to the PUBLIC images bucket.

    The storage path is scoped to current_user.tenant_id (never client input),
    so an agency can only ever upload its OWN logo. Content-type is validated
    as a raster image; SVG is rejected (SVG-borne XSS).
    """
    ctype = (file.content_type or "").lower()
    if ctype not in _ALLOWED_LOGO_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Logo must be a PNG, JPG or WEBP image.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file.")
    if len(content) > _MAX_LOGO_BYTES:
        raise HTTPException(status_code=400, detail="Logo must be 2 MB or smaller.")

    tenant = db.get(Tenant, current_user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Extension derived from the validated content-type (not the client
    # filename) to keep the storage path clean and injection-free.
    ext = _ALLOWED_LOGO_TYPES[ctype]
    file_path = f"logos/{current_user.tenant_id}/{os.urandom(4).hex()}{ext}"
    try:
        url = upload_to_supabase(content, file_path, ctype, bucket="property-images")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Logo upload failed: {str(e)}")

    tenant.logo_url = url
    db.commit()
    return {"tenant_id": tenant.id, "logo_url": url}