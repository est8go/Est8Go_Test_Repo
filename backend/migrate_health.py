"""
Creates health_checks table.
platform_issues already exists on Supabase (created manually with RLS).
"""
from dotenv import load_dotenv
load_dotenv()

from app.models_registry import register_all_models
register_all_models()
from app.database.db import engine
from sqlalchemy import text

stmts = [
    """
    CREATE TABLE IF NOT EXISTS health_checks (
        id               SERIAL PRIMARY KEY,
        system           VARCHAR(50)  NOT NULL,
        status           VARCHAR(20)  NOT NULL,
        detail           TEXT,
        response_time_ms INTEGER,
        checked_at       TIMESTAMP    NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_health_system     ON health_checks(system)",
    "CREATE INDEX IF NOT EXISTS idx_health_checked_at ON health_checks(checked_at)",
]

with engine.connect() as conn:
    for stmt in stmts:
        try:
            conn.execute(text(stmt))
            conn.commit()
            print(f"[OK] {stmt.strip().splitlines()[0][:60]}")
        except Exception as e:
            print(f"[SKIP] {e}")
