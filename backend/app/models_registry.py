import logging
from sqlalchemy.orm import configure_mappers

# 1. EXPLICIT MODEL IMPORTS
from app.tenants.models import Tenant
from app.company_profiles.models import CompanyProfile
from app.users.models import User
from app.listings.models import Listing, ListingDocument
from app.conversations.models import Conversation, ConversationMessage
from app.messages.models import Message
from app.database.audit import AuditLog  # EST8GO AUDIT TRAIL

# 2. AUTH MODELS
from app.auth.models import PasswordResetToken, RoleChangeRequest

# 3. TENANT SIGNUP + REFERRAL MODELS
from app.tenants.signup_models import TenantSignupLink, ReferralCode, ReferralConversion

# 4. CREDIT ECONOMY MODELS
from app.credits.models import (
    CreditWallet, CreditLedger, CreditExpiry,
    CreditBundle, CreditTransaction, MmefTracking, SeatEntitlement,
)

# 5. HEALTH MONITOR + ISSUES TRACKER MODELS
from app.services.health_service import HealthCheck, PlatformIssue

# 6. LISTING REPORTS (buyer fraud reports from platform care)
from app.reports.models import ListingReport

# 7. FOLLOW-UP TASK QUEUE (dashboard-first lead follow-up + escalation)
from app.operations.models import FollowUpTask, FollowUpDigestLog

logger = logging.getLogger(__name__)


def register_all_models():
    """
    Architectural Handshake:
    Explicitly registers all models to resolve cross-folder relationships.
    Also creates any new tables that don't exist yet (safe — does not drop existing).
    """
    try:
        # Touching each class satisfies Pylance/Ruff and ensures registration
        _models = [
            Tenant,
            CompanyProfile,
            User,
            Listing,
            ListingDocument,
            Conversation,
            ConversationMessage,
            Message,
            AuditLog,
            PasswordResetToken,
            RoleChangeRequest,
            TenantSignupLink,
            ReferralCode,
            ReferralConversion,
            CreditWallet,
            CreditLedger,
            CreditExpiry,
            CreditBundle,
            CreditTransaction,
            MmefTracking,
            SeatEntitlement,
            HealthCheck,
            PlatformIssue,
            ListingReport,
            FollowUpTask,
            FollowUpDigestLog,
        ]

        # Force SQLAlchemy to link all string references to their classes
        configure_mappers()

        # Create any new tables (idempotent — skips tables that already exist)
        from app.database.base import Base
        from app.database.db import engine
        Base.metadata.create_all(bind=engine)

        logger.info(
            f"✅ {len(_models)} Models successfully registered and relationships resolved."
        )
        return True

    except Exception as e:
        logger.error(f"❌ DATABASE HANDSHAKE FAILED: {e}", exc_info=True)
        raise RuntimeError(f"Model registration failed: {e}") from e
