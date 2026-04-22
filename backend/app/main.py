from dotenv import load_dotenv

load_dotenv()  # This MUST stay here to load your keys first

from fastapi import FastAPI  # noqa: E402
import app.models_registry  # noqa: F401, E402

# Import Routers
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

# Connect the Routers
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(tenants_router)
app.include_router(profile_router)
app.include_router(listings_router)
app.include_router(public_router)
app.include_router(whatsapp_router)


@app.get("/")
def root():
    return {"message": "est8go Service Limited API is Live", "docs": "/docs"}
