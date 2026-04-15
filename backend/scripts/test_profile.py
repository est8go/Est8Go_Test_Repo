import app.models_registry  # noqa: F401
from app.database.db import SessionLocal
import app.tenants.models
import app.company_profiles.models
from app.company_profiles.models import CompanyProfile

db = SessionLocal()

p = db.query(CompanyProfile).filter(CompanyProfile.tenant_id == 1).first()

print("OK:", p.assistant_name, p.assistant_role, p.emoji_mode)

db.close()