"""Adds data-retention columns to tenants and users tables."""
from dotenv import load_dotenv
load_dotenv()

from app.models_registry import register_all_models
register_all_models()
from app.database.db import engine
from sqlalchemy import text

stmts = [
    "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS suspended_at TIMESTAMP NULL",
    "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS anonymised_at TIMESTAMP NULL",
    "ALTER TABLE users   ADD COLUMN IF NOT EXISTS deleted_at   TIMESTAMP NULL",
    "ALTER TABLE users   ADD COLUMN IF NOT EXISTS anonymised_at TIMESTAMP NULL",
]

with engine.connect() as conn:
    for stmt in stmts:
        try:
            conn.execute(text(stmt))
            conn.commit()
            print(f"[OK] {stmt}")
        except Exception as e:
            print(f"[SKIP] {e}")
