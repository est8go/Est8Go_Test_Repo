"""
Migration: Add recovery speed settings to company_profiles.
Run once: python migrate_recovery_settings.py
"""
import os
from dotenv import load_dotenv
load_dotenv()

import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set")

stmts = [
    "ALTER TABLE company_profiles ADD COLUMN IF NOT EXISTS recovery_speed VARCHAR(20) NOT NULL DEFAULT 'standard'",
    "ALTER TABLE company_profiles ADD COLUMN IF NOT EXISTS send_window_start INTEGER NOT NULL DEFAULT 7",
    "ALTER TABLE company_profiles ADD COLUMN IF NOT EXISTS send_window_end INTEGER NOT NULL DEFAULT 21",
]

conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True
cur = conn.cursor()

for stmt in stmts:
    try:
        cur.execute(stmt)
        print(f"[OK] {stmt[:70]}...")
    except Exception as e:
        print(f"[ERR] {e}")

cur.close()
conn.close()
print("Done.")
