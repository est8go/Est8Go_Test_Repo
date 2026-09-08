import logging
import os
import re as _re
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

# Database & Models
from app.core.crypto import encrypt_secret
from app.core.validators import validate_meta_phone_number_id
from app.database.db import get_db
from app.listings.models import Listing, ListingDocument
from app.tenants.models import TenantChannel
from app.listings.schemas import ListingOut
from app.services.trust_engine import calculate_confidence_score, get_trust_label

logger = logging.getLogger(__name__)

# --- Supabase client (service-role) for PRIVATE document streaming ---
# Documents live in a private bucket; the ONLY read path is the guarded
# proxy route below, which streams bytes — never a storage URL.
_DOC_SUPABASE = None
try:
    from supabase import create_client as _create_client

    _SB_URL = os.getenv("SUPABASE_URL")
    _SB_KEY = os.getenv("SUPABASE_KEY")
    if _SB_URL and _SB_KEY:
        _DOC_SUPABASE = _create_client(_SB_URL, _SB_KEY)
except Exception:  # storage optional at import time
    _DOC_SUPABASE = None


def _doc_content_type(storage_path: str) -> str:
    """Best-effort content type from the object-path extension."""
    p = (storage_path or "").lower()
    if p.endswith(".pdf"):
        return "application/pdf"
    if p.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if p.endswith(".png"):
        return "image/png"
    if p.endswith(".webp"):
        return "image/webp"
    if p.endswith((".tif", ".tiff")):
        return "image/tiff"
    return "application/octet-stream"

# --- 1. ROBUST PATH HANDLING ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.filters["urlencode"] = lambda s: urllib.parse.quote(str(s), safe="")

# --- 2. UNIFIED ROUTER ---
router = APIRouter(prefix="/public", tags=["Public Pages"])

# --- 3. HELPERS ---


def _get_wa_number(listing, db: Session) -> str:
    """Returns E.164 WhatsApp number (e.g. 2348012345678) for wa.me links."""
    raw = ""
    try:
        if listing and listing.tenant_id:
            from app.tenants.models import Tenant

            tenant = db.query(Tenant).filter(Tenant.id == listing.tenant_id).first()
            raw = getattr(tenant, "whatsapp_phone_number", "") or ""
    except Exception:
        pass
    if not raw:
        raw = os.getenv("WHATSAPP_BUSINESS_NUMBER", "") or ""
    digits = _re.sub(r"\D", "", raw)
    if not digits:
        return ""
    if digits.startswith("234"):
        return digits
    if digits.startswith("0"):
        return "234" + digits[1:]
    if len(digits) == 10:
        return "234" + digits
    return digits


def _wa_url(wa_number: str, listing_id: int, title: str = "") -> str:
    """Builds a pre-filled wa.me URL with property reference."""
    text = f"Hi, I am interested in Est8Go property #{listing_id}"
    if title:
        text += f": {title}"
    return f"https://wa.me/{wa_number}?text={urllib.parse.quote(text)}"


# --- 3. ROUTES ---


# Render-time CSS-injection guard (defense-in-depth). brand_color is already
# hex-validated on write (C2), but we re-validate before it reaches a <style>
# block: only a strict #RRGGBB is emitted, otherwise the default indigo.
_BRAND_HEX_RE = _re.compile(r"^#[0-9A-Fa-f]{6}$")
_DEFAULT_ACCENT = "#4F46E5"


def _validated_accent(raw) -> str:
    """Re-validate a stored brand colour before it reaches a <style> block.
    Only a strict #RRGGBB is returned, otherwise the default indigo."""
    return raw if (raw and _BRAND_HEX_RE.match(raw)) else _DEFAULT_ACCENT


def _safe_accent(listing) -> str:
    raw = getattr(listing.tenant, "brand_color", None) if getattr(listing, "tenant", None) else None
    return _validated_accent(raw)


def _property_context(listing, db: Session) -> dict:
    score = calculate_confidence_score(listing)
    trust = get_trust_label(score)
    wa_number = _get_wa_number(listing, db)
    wa_link = _wa_url(wa_number, listing.id, listing.title or "")
    accent_color = _safe_accent(listing)

    # Real listing documents for the page. A view-link is offered ONLY when the
    # proxy would actually serve the file: visibility=="viewable" AND the
    # listing is verified — identical to the proxy's own gate, so a link can
    # never dead-end in a 404. Everything else is "Available on request".
    is_verified = listing.status == "verified"
    documents = [
        {
            "label": d.label or d.doc_type,
            "is_viewable": (d.visibility == "viewable" and is_verified),
            "view_url": f"/public/property/{listing.id}/document/{d.id}",
        }
        for d in (listing.documents or [])
    ]

    return {
        "listing": listing,
        "trust_score": score,
        "trust_icon": trust.get("icon", "🟢"),
        "trust_text": trust.get("text", "Verified"),
        "trust_color": trust.get("color", "green"),
        "wa_link": wa_link,
        "wa_number": wa_number,
        "base_url": os.getenv("BASE_URL", "https://api.est8go.com"),
        "tenant": listing.tenant,
        "documents": documents,
        "documents_count": len(documents),
        "accent_color": accent_color,
    }


def _fetch_listing(listing_id: int, db: Session):
    return (
        db.query(Listing)
        .options(
            joinedload(Listing.images),
            joinedload(Listing.tenant),
            joinedload(Listing.documents),
        )
        .filter(Listing.id == listing_id)
        .first()
    )


@router.get("/property/{listing_id}/classic", response_class=HTMLResponse)
async def get_property_page_classic(
    request: Request, listing_id: int, db: Session = Depends(get_db)
):
    try:
        listing = _fetch_listing(listing_id, db)
        if not listing:
            raise HTTPException(status_code=404, detail="Property not found")
        return templates.TemplateResponse(
            request=request,
            name="property_detail_classic.html",
            context=_property_context(listing, db),
        )
    except Exception as e:
        logger.error(f"❌ Property Classic Page Error: {e}")
        return HTMLResponse(
            content="Internal Server Error: Check Render Logs", status_code=500
        )


@router.get("/property/{listing_id}", response_class=HTMLResponse)
async def get_property_page(
    request: Request, listing_id: int, db: Session = Depends(get_db)
):
    try:
        listing = _fetch_listing(listing_id, db)
        if not listing:
            raise HTTPException(status_code=404, detail="Property not found")
        return templates.TemplateResponse(
            request=request,
            name="property_detail.html",
            context=_property_context(listing, db),
        )
    except Exception as e:
        logger.error(f"❌ Property Page Error: {e}")
        return HTMLResponse(
            content="Internal Server Error: Check Render Logs", status_code=500
        )


@router.get("/property/{listing_id}/document/{doc_id}")
async def serve_document(
    listing_id: int, doc_id: int, db: Session = Depends(get_db)
):
    """
    The ONLY read path for a private listing document.

    Streams the file bytes — NEVER a storage URL. Every guard failure
    returns a uniform 404 (not 403, no descriptive reason) so the
    endpoint never leaks which documents exist or why access was denied,
    matching the cross-tenant "404 not 403" isolation convention.
    """
    _DENY = HTTPException(status_code=404, detail="Not found")

    # 1. Document must exist AND belong to this listing.
    doc = (
        db.query(ListingDocument)
        .filter(
            ListingDocument.id == doc_id,
            ListingDocument.listing_id == listing_id,
        )
        .first()
    )
    if not doc:
        raise _DENY

    # 2. Visibility — NEVER serve an on_request (private) document.
    if doc.visibility != "viewable":
        raise _DENY

    # 3. Listing must exist, the doc must be the same tenant's, and the
    #    listing must be verified (don't expose pending/rejected docs).
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise _DENY
    if doc.tenant_id != listing.tenant_id:
        raise _DENY
    if listing.status != "verified":
        raise _DENY

    # 4. Stream from the PRIVATE bucket. Any storage failure → 404.
    if not _DOC_SUPABASE or not doc.storage_path:
        raise _DENY
    _bytes = None
    try:
        _bytes = (
            _DOC_SUPABASE.storage.from_("property-documents").download(
                doc.storage_path
            )
        )
    except Exception:
        _bytes = None
    if not _bytes:
        raise _DENY

    return Response(
        content=_bytes,
        media_type=_doc_content_type(doc.storage_path),
        headers={"Content-Disposition": "inline"},
    )


@router.get("/realtor-portal", response_class=HTMLResponse)
async def get_realtor_portal(request: Request, response: Response):
    try:
        resp = templates.TemplateResponse(
            request=request, name="business_dashboard.html"
        )
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp
    except Exception as e:
        logger.error(f"❌ Realtor Portal Error: {e}")
        return HTMLResponse(content=f"Template Error: {e}", status_code=500)


@router.get("/super-admin-portal", response_class=HTMLResponse)
async def get_admin_dashboard(request: Request):
    try:
        return templates.TemplateResponse(
            request=request, name="super_admin_dashboard.html"
        )
    except Exception as e:
        logger.error(f"❌ Admin Portal Error: {e}")
        return HTMLResponse(content=f"Template Error: {e}", status_code=500)


# 4. Search API for the Bot
@router.get("/listings/{tenant_id}", response_model=List[ListingOut])
def get_public_listings(tenant_id: int, db: Session = Depends(get_db)):
    return (
        db.query(Listing)
        .filter(Listing.tenant_id == tenant_id, Listing.status == "verified")
        .all()
    )


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def public_index(request: Request, db: Session = Depends(get_db)):
    from fastapi.responses import RedirectResponse
    from app.tenants.models import Tenant

    tenant = (
        db.query(Tenant)
        .filter(
            Tenant.is_active == True,
            Tenant.slug.isnot(None),
        )
        .order_by(Tenant.id.asc())
        .first()
    )
    if tenant and tenant.slug:
        return RedirectResponse(url=f"/public/{tenant.slug}", status_code=302)
    return HTMLResponse(content="<h2>Est8Go — Platform Loading</h2>", status_code=200)


@router.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("static/favicon.ico")


@router.get("/login", response_class=HTMLResponse)
async def get_login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")


# 🔹 SOCKET: Add this to backend/app/public/router.py


@router.get("/business", response_class=HTMLResponse)
async def get_business_dashboard(request: Request, response: Response):
    """
    Est8Go Business Command Center.
    Unified dashboard for Agency and Freelance Realtor tenants.
    Runs in parallel with /realtor-portal during migration.
    """
    try:
        resp = templates.TemplateResponse(
            request=request, name="business_dashboard.html"
        )
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp
    except Exception as e:
        logger.error(f"❌ Business Dashboard Error: {e}")
        return HTMLResponse(content=f"Template Error: {e}", status_code=500)


@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    return templates.TemplateResponse(request=request, name="forgot_password.html")


@router.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str = ""):
    return templates.TemplateResponse(
        request=request,
        name="reset_password.html",
        context={"token": token},
    )


@router.get("/credits/payment-success", response_class=HTMLResponse)
async def payment_success(request: Request, reference: str = ""):
    return templates.TemplateResponse(
        request=request,
        name="payment_success.html",
        context={"reference": reference},
    )


@router.get("/onboarding/{code}", response_class=HTMLResponse)
async def onboarding_page(request: Request, code: str):
    return templates.TemplateResponse(
        request=request,
        name="onboarding.html",
        context={"code": code},
    )


@router.get("/onboarding/{code}/validate")
async def validate_signup_link(code: str, db: Session = Depends(get_db)):
    from app.tenants.signup_models import TenantSignupLink

    link = (
        db.query(TenantSignupLink)
        .filter(
            TenantSignupLink.code == code,
            TenantSignupLink.is_active == True,
        )
        .first()
    )
    if not link:
        raise HTTPException(404, "Invalid or revoked link")
    if link.expires_at and link.expires_at < datetime.utcnow():
        raise HTTPException(410, "This invitation has expired")
    if link.uses_count >= link.max_uses:
        raise HTTPException(410, "This invitation has already been used")
    return {"valid": True, "plan": link.plan, "invited_email": link.invited_email}


@router.post("/onboarding/{code}/submit")
async def submit_onboarding(
    code: str,
    request: Request,
    db: Session = Depends(get_db),
):
    from app.tenants.signup_models import TenantSignupLink
    from app.tenants.models import Tenant
    from app.users.models import User
    from app.core.security import get_password_hash
    from app.services.email_service import send_onboarding_complete

    link = (
        db.query(TenantSignupLink)
        .filter(
            TenantSignupLink.code == code,
            TenantSignupLink.is_active == True,
        )
        .first()
    )
    if not link or link.uses_count >= link.max_uses:
        raise HTTPException(410, "Invalid or expired invitation")
    if link.expires_at and link.expires_at < datetime.utcnow():
        raise HTTPException(410, "Invitation expired")

    body = await request.json()

    biz_name_raw = body.get("business_name", "")
    auto_slug = (
        _re.sub(r"[^a-z0-9]+", "-", biz_name_raw.lower()).strip("-")
        if biz_name_raw
        else None
    )
    tenant = Tenant(
        name=biz_name_raw,
        business_name=biz_name_raw,
        slug=auto_slug,
        tenant_type=body.get("business_type", "agency"),
        areas_covered=body.get("areas_covered", ""),
        tone=body.get("tone", "friendly"),
        plan=link.plan,
        is_active=True,
    )
    db.add(tenant)
    db.flush()

    existing = db.query(User).filter(User.email == body.get("email")).first()
    if existing:
        raise HTTPException(400, "Email already registered")

    user = User(
        email=body.get("email"),
        hashed_password=get_password_hash(body.get("password", "")),
        first_name=body.get("full_name", ""),
        tenant_id=tenant.id,
        role="admin",
        is_active=True,
        is_platform_user=False,
    )
    db.add(user)

    link.uses_count += 1
    link.used_at = datetime.utcnow()
    if link.uses_count >= link.max_uses:
        link.is_active = False

    db.commit()

    # Handle WhatsApp setup option
    setup_option = body.get("whatsapp_setup_option", "A")
    wa_phone = body.get("whatsapp_phone_number")
    wa_id = body.get("whatsapp_phone_number_id")
    wa_token = body.get("whatsapp_token")
    wa_waba = body.get("whatsapp_waba_id")

    if setup_option == "B" and wa_id:
        # Option B = self-managed. The agency supplies its own Meta
        # phone_number_id, WABA id and access token.
        #
        # Previously wa_token was read and silently dropped, and no
        # tenant_channels row was created — so a self-service tenant
        # could never send from its own number and fell through to the
        # platform's global token. Both are fixed here.
        try:
            wa_id = str(wa_id).strip()
            _ok, _err = validate_meta_phone_number_id(wa_id)
            if not _ok:
                raise HTTPException(status_code=400, detail=_err)

            # Reject a number already claimed by another tenant before
            # writing anything — platform_id is a unique routing key.
            _clash = (
                db.query(TenantChannel)
                .filter(
                    TenantChannel.platform_id == wa_id,
                    TenantChannel.tenant_id != tenant.id,
                )
                .first()
            )
            if _clash:
                raise HTTPException(
                    status_code=400,
                    detail="That WhatsApp Phone Number ID is already registered.",
                )

            tenant.whatsapp_phone_number_id = wa_id

            # Encrypt before storage. encrypt_secret returns None when
            # ENCRYPTION_KEY is unset — store None rather than a
            # plaintext token, and say so loudly.
            _enc_token = None
            if wa_token:
                _enc_token = encrypt_secret(str(wa_token).strip())
                if _enc_token is None:
                    logger.error(
                        "❌ ONBOARDING: ENCRYPTION_KEY unavailable — refusing "
                        "to store the access token in plaintext. Tenant "
                        f"{tenant.id} channel created WITHOUT a token."
                    )

            _chan = (
                db.query(TenantChannel)
                .filter(
                    TenantChannel.tenant_id == tenant.id,
                    TenantChannel.platform == "whatsapp",
                )
                .first()
            )
            if _chan:
                _chan.platform_id = wa_id
                _chan.waba_id = (str(wa_waba).strip() or None) if wa_waba else None
                if _enc_token:
                    _chan.access_token_encrypted = _enc_token
                _chan.is_active = True
            else:
                _chan = TenantChannel(
                    tenant_id=tenant.id,
                    platform="whatsapp",
                    platform_id=wa_id,
                    waba_id=(str(wa_waba).strip() or None) if wa_waba else None,
                    access_token_encrypted=_enc_token,
                    is_active=True,
                    label="WhatsApp",
                )
                db.add(_chan)

            db.commit()
            logger.info(
                f"✅ ONBOARDING: tenant {tenant.id} WhatsApp channel stored "
                f"(pid={wa_id}, waba={'set' if wa_waba else 'none'}, "
                f"token={'encrypted' if _enc_token else 'MISSING'})"
            )
        except HTTPException:
            db.rollback()
            raise
        except Exception as _wbe:
            db.rollback()
            logger.error(f"WhatsApp channel storage failed: {_wbe}", exc_info=True)

    if setup_option == "A" and wa_phone:
        try:
            if hasattr(tenant, "whatsapp_phone_number"):
                tenant.whatsapp_phone_number = wa_phone
                db.commit()
        except Exception as _wpe:
            logger.warning(f"WhatsApp phone number storage failed: {_wpe}")
        try:
            import os as _os
            from app.services.email_service import _send, _base_template

            biz_name = body.get("business_name", "New Tenant")
            _body_html = f"""
              <p style="font-size:14px;color:#475569;font-family:Arial,sans-serif">
                A new tenant needs WhatsApp setup.
              </p>
              <p style="font-size:14px;color:#475569;font-family:Arial,sans-serif">
                <strong>Business:</strong> {biz_name}<br/>
                <strong>WhatsApp Number:</strong> {wa_phone}<br/>
                <strong>Credits:</strong> 50 credits will be deducted on activation
              </p>
              <p style="font-size:14px;color:#475569;font-family:Arial,sans-serif">
                Log in to Super Admin to manage this request.
              </p>
              <a href="{_os.getenv('BASE_URL', '')}/public/super-admin-portal"
                 style="display:inline-block;background:#4338CA;color:white;
                        text-decoration:none;padding:14px 28px;border-radius:12px;
                        font-weight:700;font-size:14px">
                View in Dashboard
              </a>"""
            _send(
                "est8go@gmail.com",
                f"WhatsApp setup needed: {biz_name}",
                _base_template("New WhatsApp Setup Request", _body_html),
            )
            logger.info(
                f"WhatsApp setup email sent to est8go@gmail.com "
                f"for tenant: {tenant.business_name}"
            )
        except Exception as _wae:
            logger.error(f"WhatsApp setup email FAILED: {str(_wae)}")

    # Award welcome credits (10 bonus, 90-day expiry)
    try:
        from app.credits.service import award_credits

        credit_result = award_credits(
            tenant_id=tenant.id,
            credits=10,
            credit_type="bonus",
            reason="welcome",
            expiry_days=90,
            db=db,
        )
        logger.info(
            f"Welcome credits awarded: tenant={tenant.id} " f"result={credit_result}"
        )
    except Exception as e:
        logger.error(f"Welcome credits FAILED: tenant={tenant.id} " f"error={str(e)}")

    try:
        superusers = (
            db.query(User)
            .filter(
                User.role == "superuser",
                User.is_active == True,
                User.is_platform_user == True,
            )
            .all()
        )
        for su in superusers:
            send_onboarding_complete(
                su.email,
                tenant.business_name or "New Tenant",
                body.get("email", ""),
                link.plan,
            )
    except Exception as e:
        logger.error(f"Onboarding complete email failed: {e}")

    return {"success": True, "message": "Account created successfully"}


@router.get("/matches", response_class=HTMLResponse)
async def get_matches_page(request: Request, ids: str, db: Session = Depends(get_db)):
    """
    World-Class Hybrid Gallery: Opens when a user clicks the Bot link.
    URL format: /public/matches?ids=1,2,5
    """
    try:
        # Convert comma-separated string "1,2,5" to list [1, 2, 5]
        id_list = [int(i) for i in ids.split(",") if i.strip()]

        # Fetch verified properties from the list
        listings = (
            db.query(Listing)
            .options(joinedload(Listing.images))
            .filter(Listing.id.in_(id_list))
            .all()
        )

        # Get wa_number from first listing's tenant
        wa_number = _get_wa_number(listings[0], db) if listings else ""

        return templates.TemplateResponse(
            request=request,
            name="matches_gallery.html",
            context={"listings": listings, "wa_number": wa_number},
        )
    except Exception as e:
        logger.error(f"Gallery Error: {e}")
        return HTMLResponse("Gallery temporarily unavailable", status_code=500)


@router.get("/embed", response_class=HTMLResponse)
async def embed_demo_page(request: Request):
    """Developer documentation page for the Est8Go embed widget."""
    return templates.TemplateResponse(
        request=request,
        name="embed_demo.html",
        context={"base_url": os.getenv("BASE_URL", "https://est8go-api.onrender.com")},
    )


@router.get("/api/{tenant_slug}/listings")
async def public_listings_api(
    tenant_slug: str,
    limit: int = Query(6, ge=1, le=24),
    prop_type: str = Query(None, alias="type"),
    location: str = None,
    db: Session = Depends(get_db),
):
    """
    Public JSON API for the Est8Go embed widget.
    CORS is handled by the app-level CORSMiddleware (allow_origins=*).
    """
    from app.tenants.models import Tenant as _Tenant

    tenant = db.query(_Tenant).filter(_Tenant.slug == tenant_slug).first()
    if not tenant:
        tenant = (
            db.query(_Tenant)
            .filter(_Tenant.business_name.ilike(f"%{tenant_slug.replace('-', ' ')}%"))
            .first()
        )
    if not tenant:
        raise HTTPException(status_code=404, detail="Agency not found")

    query = (
        db.query(Listing)
        .options(joinedload(Listing.images))
        .filter(Listing.tenant_id == tenant.id, Listing.trust_score > 0)
    )
    if prop_type:
        query = query.filter(Listing.property_type == prop_type)
    if location:
        query = query.filter(Listing.location.ilike(f"%{location}%"))

    listings = query.order_by(Listing.trust_score.desc()).limit(limit).all()

    raw_wa = getattr(tenant, "whatsapp_phone_number", None) or os.getenv(
        "WHATSAPP_BUSINESS_NUMBER", ""
    )
    digits = _re.sub(r"\D", "", raw_wa)
    if digits.startswith("0"):
        digits = "234" + digits[1:]
    elif len(digits) == 10:
        digits = "234" + digits

    base_url = os.getenv("BASE_URL", "https://est8go-api.onrender.com")

    data = [
        {
            "id": lst.id,
            "title": lst.title,
            "location": lst.location,
            "property_type": lst.property_type,
            "price": lst.price,
            "trust_score": lst.trust_score or 0,
            "trust_grade": lst.trust_grade or "ungraded",
            "gps_verified": bool(lst.gps_verified_at),
            "image_url": lst.images[0].url if lst.images else None,
            "wa_number": digits,
            "property_url": f"{base_url}/public/property/{lst.id}",
        }
        for lst in listings
    ]
    return JSONResponse(content=data)


@router.get("/{tenant_slug}", response_class=HTMLResponse)
async def tenant_public_vault(
    tenant_slug: str,
    request: Request,
    property_type: str = None,
    location: str = None,
    db: Session = Depends(get_db),
):
    """
    Public property vault page for a tenant agency.
    Accessible at /public/{tenant_slug} e.g. /public/bravieshomz
    """
    try:
        from app.tenants.models import Tenant
        from app.company_profiles.models import CompanyProfile

        tenant = db.query(Tenant).filter(Tenant.slug == tenant_slug).first()
        if not tenant:
            tenant = (
                db.query(Tenant)
                .filter(
                    Tenant.business_name.ilike(f"%{tenant_slug.replace('-', ' ')}%")
                )
                .first()
            )
        if not tenant:
            raise HTTPException(status_code=404, detail="Agency not found")

        profile = (
            db.query(CompanyProfile)
            .filter(CompanyProfile.tenant_id == tenant.id)
            .first()
        )

        query = (
            db.query(Listing)
            .options(joinedload(Listing.images))
            .filter(Listing.tenant_id == tenant.id, Listing.trust_score > 0)
        )
        if property_type:
            query = query.filter(Listing.property_type == property_type)
        if location:
            query = query.filter(Listing.location.ilike(f"%{location}%"))

        listings = query.order_by(Listing.trust_score.desc()).all()

        all_listings = db.query(Listing).filter(Listing.tenant_id == tenant.id).all()
        locations = sorted(set(l.location.title() for l in all_listings if l.location))
        types = sorted(set(l.property_type for l in all_listings if l.property_type))

        raw_wa = getattr(tenant, "whatsapp_phone_number", None) or os.getenv(
            "WHATSAPP_BUSINESS_NUMBER", ""
        )
        digits = _re.sub(r"\D", "", raw_wa)
        if digits.startswith("0"):
            digits = "234" + digits[1:]
        elif len(digits) == 10:
            digits = "234" + digits

        return templates.TemplateResponse(
            request=request,
            name="tenant_vault.html",
            context={
                "tenant": tenant,
                "profile": profile,
                "listings": listings,
                "locations": locations,
                "types": types,
                "wa_number": digits,
                "base_url": os.getenv("BASE_URL", "https://est8go-api.onrender.com"),
                "selected_type": property_type,
                "selected_location": location,
                # Render-time CSS-injection guard (same as the property page).
                "accent_color": _validated_accent(getattr(tenant, "brand_color", None)),
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Tenant Vault Error [{tenant_slug}]: {e}")
        return HTMLResponse(
            content="Internal Server Error: Check Render Logs", status_code=500
        )
