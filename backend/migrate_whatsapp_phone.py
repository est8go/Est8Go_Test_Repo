from app.models_registry import register_all_models
register_all_models()
from app.database.db import engine
from sqlalchemy import text

with engine.connect() as conn:
    try:
        conn.execute(text(
            "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS "
            "whatsapp_phone_number VARCHAR(20) NULL"
        ))
        conn.commit()
        print("[OK] Added whatsapp_phone_number to tenants")
    except Exception as e:
        print(f"[SKIP] {e}")
