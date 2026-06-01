"""
Migration: Add assigned_realtor_id to listings table
Run once: python migrate_realtor_assignment.py
"""
import os
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

SQL = """
ALTER TABLE listings
ADD COLUMN IF NOT EXISTS assigned_realtor_id INTEGER
REFERENCES users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_listing_realtor
ON listings(assigned_realtor_id);
"""

with engine.connect() as conn:
    conn.execute(text(SQL))
    conn.commit()
    print("OK: assigned_realtor_id column and index created successfully.")
