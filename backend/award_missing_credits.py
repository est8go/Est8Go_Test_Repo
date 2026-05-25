from app.models_registry import register_all_models
register_all_models()
from app.database.db import get_db
from app.credits.service import award_credits

db = next(get_db())

for tenant_id in [8, 9]:
    try:
        result = award_credits(
            tenant_id   = tenant_id,
            credits     = 10,
            credit_type = "bonus",
            reason      = "welcome",
            expiry_days = 90,
            db          = db,
        )
        print(f"[OK] Tenant {tenant_id}: {result}")
    except Exception as e:
        print(f"[FAIL] Tenant {tenant_id}: {e}")
