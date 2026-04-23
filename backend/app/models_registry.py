# app/models_registry.py
from sqlalchemy.orm import configure_mappers

# 1. Import all models
import app.tenants.models
import app.company_profiles.models
import app.users.models
import app.listings.models
import app.conversations.models
import app.messages.models


def register_all_models():
    """
    Ensures all models are loaded and relationships are verified.
    """
    try:
        # THE MAGIC LINE: This forces SQLAlchemy to build the 'tenant' property
        # on the Listing model immediately.
        configure_mappers()

        models = [
            app.tenants.models,
            app.company_profiles.models,
            app.users.models,
            app.listings.models,
            app.conversations.models,
            app.messages.models,
        ]
        print(f"🚀 {len(models)} Premium Models fully wired for est8go.")
        return True
    except Exception as e:
        print(f"❌ Mapper Configuration Error: {e}")
        return False
