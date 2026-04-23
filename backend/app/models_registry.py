# app/models_registry.py
import logging
from sqlalchemy.orm import configure_mappers

# 1. THE CRITICAL ORDER: Tenants must come before the things that reference them
import app.tenants.models
import app.company_profiles.models
import app.users.models
import app.listings.models
import app.conversations.models
import app.messages.models

logger = logging.getLogger(__name__)


def register_all_models():
    """
    Detailed Registry: Ensures all models are loaded into memory,
    silences linter warnings, and wires cross-folder relationships.
    """
    try:
        # A. THE SILENCER: Touch each model to prevent 'not accessed' warnings
        models = [
            app.tenants.models,
            app.company_profiles.models,
            app.users.models,
            app.listings.models,
            app.conversations.models,
            app.messages.models,
        ]

        # B. THE HANDSHAKE: Force SQLAlchemy to resolve all 'Tenant' and 'User' names
        # This fixes the 'InvalidRequestError' and 'NoProperty' errors during login.
        configure_mappers()

        print(f"✅ {len(models)} Premium Models fully wired and registered for est8go.")
        return True

    except Exception as e:
        # Detailed error reporting for the Render logs
        logger.error(f"❌ DATABASE HANDSHAKE FAILED: {e}", exc_info=True)
        return False
