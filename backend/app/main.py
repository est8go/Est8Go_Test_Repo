from dotenv import load_dotenv

load_dotenv()  # 1. Load keys first (MUST be at the top)

from fastapi import FastAPI  # noqa: E402
import app.models_registry  # noqa: E402

# 2. Register all models (This uses the registry so Pylance is happy)
app.models_registry.register_all_models()

# 3. Import Routers (We add noqa: E402 to satisfy the import-order rule)
from app.auth.router import router as auth_router  # noqa: E402
from app.users.router import router as users_router  # noqa: E402
from app.tenants.router import router as tenants_router  # noqa: E402
from app.company_profiles.router import router as profile_router  # noqa: E402
from app.listings.router import router as listings_router  # noqa: E402
from app.public.router import router as public_router  # noqa: E402
from app.channels.whatsapp.router import router as whatsapp_router  # noqa: E402

app = FastAPI(
    title="est8go Service Limited",
    description="The Global Multi-tenant Infrastructure for Real Estate, Pharmacy, and Hospital Trust.",
    version="1.0.0",
)

# 4. Connect (Include) all routers so they are 'Accessed'
# This removes the "not accessed" warnings from Pylance/Ruff
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(tenants_router)
app.include_router(profile_router)
app.include_router(listings_router)
app.include_router(public_router)
app.include_router(whatsapp_router)


@app.get("/")
def root():
    """Health check for est8go Service Limited."""
    return {
        "message": "est8go Service Limited API is Live",
        "status": "Healthy",
        "docs": "/docs",
    }
