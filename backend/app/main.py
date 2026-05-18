# ================================================================
# EST8GO — MAIN APPLICATION ENTRY POINT
# ================================================================

# 1. Load environment variables FIRST — before anything else
from dotenv import load_dotenv

load_dotenv()

# 2. Register all models BEFORE routers are imported
from app.models_registry import register_all_models  # noqa: E402

register_all_models()

# 3. FastAPI core
from fastapi import FastAPI  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

# 4. Import all routers (one place, no duplicates)
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

# 5. Initialize the platform
app = FastAPI(
    title="Est8Go Service Limited",
    description="The Global Multi-tenant Infrastructure for Real Estate Trust.",
    version="2.0.0",
)

# 6. Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# 7. Include all routers
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


# 8. Health check
@app.api_route("/", methods=["GET", "HEAD"])
def root():
    """Health check for Est8Go Service Limited."""
    return {
        "message": "Est8Go Service Limited API is Live",
        "status": "Healthy",
        "version": "2.0.0",
        "docs": "/docs",
    }
