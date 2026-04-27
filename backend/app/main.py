# 🔹 1. Imports (ALL at the top — fixes Ruff E402)
import os
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from fastapi import FastAPI

from app.models_registry import register_all_models

# Routers
from app.auth.router import router as auth_router
from app.users.router import router as users_router
from app.tenants.router import router as tenants_router
from app.company_profiles.router import router as profile_router
from app.listings.router import router as listings_router
from app.public.router import router as public_router
from app.channels.whatsapp.router import router as whatsapp_router

# This finds the 'templates' folder even when deployed on Render
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
templates_path = os.path.join(base_dir, "templates")
templates = Jinja2Templates(directory=templates_path)


# 🔹 2. Environment setup
load_dotenv()


# 🔥 3. CRITICAL: Register models BEFORE app starts
register_all_models()


# 🔹 4. Create FastAPI app
app = FastAPI(
    title="est8go Service Limited",
    description="The Global Multi-tenant Infrastructure for Real Estate, Pharmacy, and Hospital Trust.",
    version="1.0.0",
)


# 🔹 5. Include routers
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(tenants_router)
app.include_router(profile_router)
app.include_router(listings_router)
app.include_router(public_router)
app.include_router(whatsapp_router)


# 🔹 6. Health check
@app.get("/")
def root():
    return {
        "message": "est8go Service Limited API is Live",
        "status": "Healthy",
        "docs": "/docs",
    }
