# app/models_registry.py

# Import all models to register them with SQLAlchemy Base
import app.tenants.models
import app.company_profiles.models
import app.users.models
import app.listings.models
import app.conversations.models
import app.messages.models


def register_all_models():
    """
    Explicitly call this to ensure all models are loaded into memory.
    This also silences Pylance/Linter warnings.
    """
    models = [
        app.tenants.models,
        app.company_profiles.models,
        app.users.models,
        app.listings.models,
        app.conversations.models,
        app.messages.models,
    ]
    print(f"✅ {len(models)} Premium Models registered for est8go Service Limited.")
    return True
