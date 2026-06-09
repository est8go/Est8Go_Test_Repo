"""
EST8GO SERVICE LIMITED
=======================
The Global Multi-Tenant Infrastructure for Real Estate Trust.
Version: 3.0.0 — Fort Knox Security Edition
"""

# ── 1. ENV FIRST — always before any app imports ──────────────
from dotenv import load_dotenv

load_dotenv()

# ── 2. REGISTER ALL MODELS ────────────────────────────────────
from app.models_registry import register_all_models  # noqa: E402

register_all_models()

# ── 3. FASTAPI CORE ───────────────────────────────────────────
import os  # noqa: E402
from datetime import datetime  # noqa: E402
from fastapi import Depends, FastAPI, Request  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi.responses import JSONResponse, PlainTextResponse, Response  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from starlette.middleware.trustedhost import TrustedHostMiddleware  # noqa: E402

# ── 4. ALL ROUTERS ────────────────────────────────────────────
from app.auth.router import router as auth_router  # noqa: E402
from app.users.router import router as users_router  # noqa: E402
from app.tenants.router import router as tenants_router  # noqa: E402
from app.company_profiles.router import router as profile_router  # noqa: E402
from app.listings.router import router as listings_router  # noqa: E402
from app.listings.document_router import router as document_router  # noqa: E402
from app.conversations.router import router as conversations_router  # noqa: E402
from app.conversations.pipeline_router import router as pipeline_router  # noqa: E402
from app.channels.whatsapp.router import router as whatsapp_router  # noqa: E402
from app.services.reel_router import router as reel_router  # noqa: E402
from app.public.router import router as public_router  # noqa: E402
from app.admin.router import router as admin_router  # noqa: E402
from app.admin.conversations_router import router as admin_conversations_router  # noqa: E402
from app.admin.role_requests_router import router as role_requests_router  # noqa: E402
from app.admin.signup_links_router import router as signup_links_router  # noqa: E402
from app.referrals.router import router as referrals_router  # noqa: E402
from app.credits.router import router as credits_router  # noqa: E402
from app.credits.seat_router import router as seat_router  # noqa: E402
from app.admin.health_router import router as health_router  # noqa: E402
from app.admin.issues_router import router as issues_router  # noqa: E402
from app.database.db import get_db  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

# ── 5. SECURITY MIDDLEWARE ────────────────────────────────────
from app.auth.deps import audit_platform_actions  # noqa: E402

# ── 6. INITIALISE APP ─────────────────────────────────────────
app = FastAPI(
    title="Est8Go Service Limited",
    description="The Global Multi-Tenant Infrastructure for Real Estate Trust.",
    version="3.0.0",
)

# ── 7. TRUSTED HOST (must be before CORS) ─────────────────────
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"],
)

# ── 7b. CORS ──────────────────────────────────────────────────
# Tighten allowed_origins before going to production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 8. AUTO-AUDIT MIDDLEWARE ──────────────────────────────────
# Automatically logs every mutating API call by platform users
app.middleware("http")(audit_platform_actions)


# ── 8b. SECURITY HEADERS ──────────────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# ── 9. GLOBAL EXCEPTION HANDLER ──────────────────────────────
# Never leak stack traces to the client
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import logging

    logging.getLogger("est8go").error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Our team has been notified."},
    )


# ── 11. INCLUDE ALL ROUTERS ───────────────────────────────────
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(tenants_router)
app.include_router(profile_router)
app.include_router(listings_router)
app.include_router(document_router)
app.include_router(conversations_router)
app.include_router(pipeline_router)
app.include_router(whatsapp_router)
app.include_router(reel_router)
app.include_router(public_router)
app.include_router(admin_router)
app.include_router(admin_conversations_router)
app.include_router(role_requests_router)
app.include_router(signup_links_router)
app.include_router(referrals_router)
app.include_router(credits_router)
app.include_router(seat_router)
app.include_router(health_router)
app.include_router(issues_router)


# ── 12. HEALTH CHECK ──────────────────────────────────────────
@app.api_route("/", methods=["GET", "HEAD"])
def root():
    return {
        "platform": "Est8Go Service Limited",
        "status": "Operational",
        "version": "3.0.0",
        "security": "Fort Knox Edition",
    }


# ── 13. SEO / CRAWL FILES ─────────────────────────────────────
_STATIC_DIR = os.path.join(os.path.dirname(__file__), "../static")


@app.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
def robots_txt():
    try:
        with open(os.path.join(_STATIC_DIR, "robots.txt")) as f:
            return f.read()
    except Exception:
        return (
            "User-agent: *\nAllow: /public/\n"
            "Sitemap: https://api.est8go.com/sitemap.xml\n"
        )


@app.get("/sitemap.xml", include_in_schema=False)
def sitemap_xml(db: Session = Depends(get_db)):
    return _sitemap_xml_inner(db)


def _sitemap_xml_inner(db):
    from app.tenants.models import Tenant
    from app.listings.models import Listing as _Listing

    base_url = os.getenv("BASE_URL", "https://api.est8go.com")
    today = datetime.utcnow().strftime("%Y-%m-%d")
    urls = []

    for url, priority, freq in [
        ("https://est8go.com", "1.0", "weekly"),
        (f"{base_url}/public/embed", "0.8", "monthly"),
    ]:
        urls.append(
            f"  <url>\n    <loc>{url}</loc>\n    <lastmod>{today}</lastmod>\n"
            f"    <changefreq>{freq}</changefreq>\n    <priority>{priority}</priority>\n  </url>"
        )

    tenants = db.query(Tenant).filter(
        Tenant.is_active == True,
        Tenant.slug != None,
        Tenant.tenant_type != "platform",
    ).all()
    for tenant in tenants:
        if tenant.slug:
            urls.append(
                f"  <url>\n    <loc>{base_url}/public/{tenant.slug}</loc>\n"
                f"    <lastmod>{today}</lastmod>\n    <changefreq>daily</changefreq>\n"
                f"    <priority>0.9</priority>\n  </url>"
            )

    listings = db.query(_Listing).filter(
        _Listing.status == "verified",
        _Listing.trust_score > 0,
    ).all()
    for lst in listings:
        lastmod = lst.created_at.strftime("%Y-%m-%d") if lst.created_at else today
        urls.append(
            f"  <url>\n    <loc>{base_url}/public/property/{lst.id}</loc>\n"
            f"    <lastmod>{lastmod}</lastmod>\n    <changefreq>weekly</changefreq>\n"
            f"    <priority>0.8</priority>\n  </url>"
        )

    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
        '        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n'
        + "\n".join(urls)
        + "\n</urlset>"
    )
    return Response(content=sitemap, media_type="application/xml")


@app.get("/llms.txt", response_class=PlainTextResponse, include_in_schema=False)
def llms_txt():
    try:
        with open(os.path.join(_STATIC_DIR, "llms.txt")) as f:
            return f.read()
    except Exception:
        return (
            "# Est8Go\nNigeria's property trust verification platform.\nhttps://est8go.com\n"
        )


# ── 14. STATIC FILES (must be last — mount shadows later routes) ──
app.mount("/static", StaticFiles(directory="static"), name="static")
