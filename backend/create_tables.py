from app.database.db import engine
from app.database.base import Base

# IMPORTANT: import every model so Base.metadata sees them
from app.users.models import User
from app.tenants.models import Tenant
from app.company_profiles.models import CompanyProfile
from app.conversations.models import Conversation, ConversationMessage

# AiCache model (adjust import path if different)
from app.conversations.ai_fallback import AiCache


def main():
    Base.metadata.create_all(bind=engine)
    print("[OK] Tables created successfully.")


if __name__ == "__main__":
    main()