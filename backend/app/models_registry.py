# backend/app/models_registry.py
import logging
from sqlalchemy.orm import configure_mappers

# KEEPING YOUR MODULE IMPORTS (Safe from Circular Errors)
import app.tenants.models
import app.company_profiles.models
import app.users.models
import app.listings.models
import app.conversations.models
import app.messages.models

logger = logging.getLogger(__name__)


def register_all_models():
    """
    PREMIUM REGISTRY: Maintains est8go architecture while fixing
    cross-module relationship resolution.
    """
    try:
        # A. THE SILENCER (Your original logic to stop Pylance warnings)
        modules = [
            app.tenants.models,
            app.company_profiles.models,
            app.users.models,
            app.listings.models,
            app.conversations.models,
            app.messages.models,
        ]

        # B. THE SURGICAL FIX: TOUCH THE CLASSES
        # We explicitly access the Classes inside your modules so
        # SQLAlchemy knows they exist during the mapper handshake.
        _ = [
            app.tenants.models.Tenant,
            app.company_profiles.models.CompanyProfile,
            app.users.models.User,
            app.listings.models.Listing,
            app.conversations.models.Conversation,
            app.messages.models.Message,
        ]

        # C. THE HANDSHAKE
        configure_mappers()

        logger.info(f"✅ {len(modules)} Premium Models fully wired and registered.")
        print(f"✅ {len(modules)} Premium Models fully wired and registered.")
        return True

    except Exception as e:
        logger.error(f"❌ DATABASE HANDSHAKE FAILED: {e}", exc_info=True)
        return False
