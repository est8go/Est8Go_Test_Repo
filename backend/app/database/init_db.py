from app.database.db import engine
from app.database.base import Base

# Import models so SQLAlchemy registers them
from app.tenants.models import Tenant  # noqa: F401
from app.users.models import User  # noqa: F401
from app.messages.models import Message  # noqa: F401

# Conversations
from app.conversations.models import Conversation, ConversationMessage  # noqa: F401

# AI cache
from app.ai_cache.models import AiCache  # noqa: F401


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    print("✅ Database initialized (tables created).")