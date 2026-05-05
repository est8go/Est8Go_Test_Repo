from app.models_registry import register_all_models

register_all_models()

from app.database.db import get_db
from app.services.tenant_resolver import register_tenant_channel

db = next(get_db())

channel = register_tenant_channel(
    db=db,
    tenant_id=1,
    platform="whatsapp",
    platform_id="1138633615995344",
    label="Test Line",
)

print(
    f"✅ Channel registered: {channel.platform} | {channel.platform_id} | Tenant {channel.tenant_id}"
)
