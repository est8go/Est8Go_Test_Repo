from app.models_registry import register_all_models
register_all_models()
from app.database.db import get_db
from sqlalchemy import text

db = next(get_db())

db.execute(text('''
    ALTER TABLE tenant_channels
    ADD COLUMN IF NOT EXISTS waba_id VARCHAR(100)
'''))
db.execute(text('''
    ALTER TABLE tenant_channels
    ADD COLUMN IF NOT EXISTS access_token_encrypted TEXT
'''))
db.execute(text('''
    ALTER TABLE tenant_channels
    ADD COLUMN IF NOT EXISTS token_expires_at TIMESTAMP
'''))
db.commit()
print("TenantChannel credential columns added")
