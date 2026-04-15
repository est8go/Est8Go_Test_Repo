from app.database.db import engine
from app.database.base import Base

# IMPORTANT: import models so SQLAlchemy registers the latest schema
from app.tenants.models import Tenant  # noqa: F401
from app.users.models import User  # noqa: F401
from app.conversations.models import Conversation, ConversationMessage  # noqa: F401


def reset_conversations_tables() -> None:
    # Drop ONLY the conversation tables (safe for dev)
    ConversationMessage.__table__.drop(bind=engine, checkfirst=True)
    Conversation.__table__.drop(bind=engine, checkfirst=True)

    # Recreate with latest model definitions
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    reset_conversations_tables()
    print("✅ Conversations tables reset (dropped + recreated).")