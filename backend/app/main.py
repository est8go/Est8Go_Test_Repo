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
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
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

# ── 5. SECURITY MIDDLEWARE ────────────────────────────────────
from app.auth.deps import audit_platform_actions  # noqa: E402

# ── 6. INITIALISE APP ─────────────────────────────────────────
app = FastAPI(
    title="Est8Go Service Limited",
    description="The Global Multi-Tenant Infrastructure for Real Estate Trust.",
    version="3.0.0",
)

# ── 7. CORS ───────────────────────────────────────────────────
# Tighten allowed_origins before going to production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"],
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


# ── 10. STATIC FILES ──────────────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")

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
