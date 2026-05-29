import logging
import os
import re as _re
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

# Database & Models
from app.database.db import get_db
from app.listings.models import Listing
from app.listings.schemas import ListingOut
from app.services.trust_engine import calculate_confidence_score, get_trust_label

logger = logging.getLogger(__name__)

# --- 1. ROBUST PATH HANDLING ---
# This looks for the 'templates' folder inside the 'backend' root
BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

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
        text += f" — {title}"
    return f"https://wa.me/{wa_number}?text={urllib.parse.quote(text)}"


# --- 3. ROUTES ---


def _property_context(listing, db: Session) -> dict:
    score = calculate_confidence_score(listing)
    trust = get_trust_label(score)
    wa_number = _get_wa_number(listing, db)
    wa_link = _wa_url(wa_number, listing.id, listing.title or "")
    return {
        "listing": listing,
        "trust_score": score,
        "trust_icon": trust.get("icon", "🟢"),
        "trust_text": trust.get("text", "Verified"),
        "trust_color": trust.get("color", "green"),
        "wa_link": wa_link,
        "wa_number": wa_number,
    }


def _fetch_listing(listing_id: int, db: Session):
    return (
        db.query(Listing)
        .options(joinedload(Listing.images), joinedload(Listing.tenant))
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
        return HTMLResponse(content="Internal Server Error: Check Render Logs", status_code=500)


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

    link = db.query(TenantSignupLink).filter(
        TenantSignupLink.code      == code,
        TenantSignupLink.is_active == True,
    ).first()
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

    link = db.query(TenantSignupLink).filter(
        TenantSignupLink.code      == code,
        TenantSignupLink.is_active == True,
    ).first()
    if not link or link.uses_count >= link.max_uses:
        raise HTTPException(410, "Invalid or expired invitation")
    if link.expires_at and link.expires_at < datetime.utcnow():
        raise HTTPException(410, "Invitation expired")

    body = await request.json()

    tenant = Tenant(
        name          = body.get("business_name", ""),
        business_name = body.get("business_name", ""),
        tenant_type   = body.get("business_type", "agency"),
        areas_covered = body.get("areas_covered", ""),
        tone          = body.get("tone", "friendly"),
        plan          = link.plan,
        is_active     = True,
    )
    db.add(tenant)
    db.flush()

    existing = db.query(User).filter(User.email == body.get("email")).first()
    if existing:
        raise HTTPException(400, "Email already registered")

    user = User(
        email            = body.get("email"),
        hashed_password  = get_password_hash(body.get("password", "")),
        first_name       = body.get("full_name", ""),
        tenant_id        = tenant.id,
        role             = "admin",
        is_active        = True,
        is_platform_user = False,
    )
    db.add(user)

    link.uses_count += 1
    link.used_at     = datetime.utcnow()
    if link.uses_count >= link.max_uses:
        link.is_active = False

    db.commit()

    # Handle WhatsApp setup option
    setup_option = body.get("whatsapp_setup_option", "A")
    wa_phone     = body.get("whatsapp_phone_number")
    wa_id        = body.get("whatsapp_phone_number_id")
    wa_token     = body.get("whatsapp_token")

    if setup_option == "B" and wa_id:
        try:
            tenant.whatsapp_phone_number_id = wa_id
            db.commit()
        except Exception as _wbe:
            logger.warning(f"WhatsApp phone_number_id storage failed: {_wbe}")

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
            biz_name  = body.get("business_name", "New Tenant")
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
            tenant_id   = tenant.id,
            credits     = 10,
            credit_type = "bonus",
            reason      = "welcome",
            expiry_days = 90,
            db          = db,
        )
        logger.info(
            f"Welcome credits awarded: tenant={tenant.id} "
            f"result={credit_result}"
        )
    except Exception as e:
        logger.error(
            f"Welcome credits FAILED: tenant={tenant.id} "
            f"error={str(e)}"
        )

    try:
        superusers = db.query(User).filter(
            User.role == "superuser",
            User.is_active == True,
            User.is_platform_user == True,
        ).all()
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
