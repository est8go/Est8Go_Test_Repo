# app/models_registry.py

# We import these to register them with SQLAlchemy's Base.metadata
import app.tenants.models  # noqa: F401
import app.users.models  # noqa: F401
import app.listings.models  # noqa: F401
import app.messages.models  # noqa: F401
import app.conversations.models  # noqa: F401

print("✅ All models registered in memory.")
