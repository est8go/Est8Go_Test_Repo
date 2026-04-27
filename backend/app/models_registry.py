import logging
from sqlalchemy.orm import configure_mappers

# 1. EXPLICIT MODEL IMPORTS
from app.tenants.models import Tenant
from app.company_profiles.models import CompanyProfile
from app.users.models import User
from app.listings.models import Listing
from app.conversations.models import Conversation, ConversationMessage
from app.messages.models import Message

logger = logging.getLogger(__name__)


def register_all_models():
    """
    Architectural Handshake:
    Explicitly registers all models to resolve cross-folder relationships.
    """
    try:
        # 🛡️ THE SILENCER: Touching each class to satisfy Pylance/Ruff.
        # This tells the IDE the imports are necessary.
        _models = [
            Tenant,
            CompanyProfile,
            User,
            Listing,
            Conversation,
            ConversationMessage,
            Message,
        ]

        # 🔥 THE HANDSHAKE
        # Force SQLAlchemy to link "Tenant" and "CompanyProfile" strings to these classes.
        configure_mappers()

        logger.info(
            f"✅ {len(_models)} Models successfully registered and relationships resolved."
        )
        return True

    except Exception as e:
        logger.error(f"❌ DATABASE HANDSHAKE FAILED: {e}", exc_info=True)
        # Fail-Fast: Don't allow a broken app to start
        raise RuntimeError(f"Model registration failed: {e}") from e
