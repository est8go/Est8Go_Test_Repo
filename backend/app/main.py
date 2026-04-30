from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# 1. Load keys first (MUST be the absolute first action)
load_dotenv()

# 2. Register all models (Before routers are imported)
from app.models_registry import register_all_models  # noqa: E402

register_all_models()

# 3. Standard Imports (Using noqa: E402 to allow imports after code)
from fastapi import FastAPI  # noqa: E402

# 4. Import Routers
from app.conversations.router import router as conversations_router  # noqa: E402
from app.auth.router import router as auth_router  # noqa: E402
from app.users.router import router as users_router  # noqa: E402
from app.tenants.router import router as tenants_router  # noqa: E402
from app.company_profiles.router import router as profile_router  # noqa: E402
from app.listings.router import router as listings_router  # noqa: E402
from app.public.router import router as public_router  # noqa: E402
from app.channels.whatsapp.router import router as whatsapp_router  # noqa: E402

# 5. Initialize the Platform
app = FastAPI(
    title="est8go Service Limited",
    description="The Global Multi-tenant Infrastructure for Real Estate Trust.",
    version="1.0.0",
)
app.mount("/static", StaticFiles(directory="static"), name="static")

# 6. Include Routers in the App
app.include_router(conversations_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(tenants_router)
app.include_router(profile_router)
app.include_router(listings_router)
app.include_router(public_router)
app.include_router(whatsapp_router)


@app.api_route("/", methods=["GET", "HEAD"])
def root():
    """Health check for est8go Service Limited."""
    return {
        "message": "est8go Service Limited API is Live",
        "status": "Healthy",
        "docs": "/docs",
    }
