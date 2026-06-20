"""
Migration: add listing_documents table + listings.documents_status

Run from the backend folder:
    PYTHONPATH=. python migrations/add_listing_documents.py

Idempotent — safe to run multiple times:
  - CREATE TABLE IF NOT EXISTS
  - CREATE INDEX IF NOT EXISTS
  - ADD COLUMN IF NOT EXISTS
No existing data is touched beyond adding documents_status (default 'none').
"""

from app.models_registry import register_all_models
register_all_models()
from app.database.db import get_db
from sqlalchemy import text

db = next(get_db())

# 1. Create the listing_documents table
db.execute(text('''
    CREATE TABLE IF NOT EXISTS listing_documents (
        id                SERIAL PRIMARY KEY,
        listing_id        INTEGER NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
        tenant_id         INTEGER NOT NULL REFERENCES tenants(id),
        doc_type          VARCHAR(50)  NOT NULL,
        label             VARCHAR(255) NOT NULL,
        tier              INTEGER,
        score_value       INTEGER,
        storage_path      VARCHAR(500) NOT NULL,
        file_url          VARCHAR(500),
        file_hash         VARCHAR(64),
        visibility        VARCHAR(20)  NOT NULL DEFAULT 'on_request',
        uploaded_by_id    INTEGER REFERENCES users(id),
        uploaded_by_email VARCHAR(255),
        uploaded_at       TIMESTAMP DEFAULT NOW()
    )
'''))

# 2. Indexes for tenant-scoped + per-listing lookups
db.execute(text('''
    CREATE INDEX IF NOT EXISTS idx_listing_documents_listing_id
        ON listing_documents (listing_id)
'''))
db.execute(text('''
    CREATE INDEX IF NOT EXISTS idx_listing_documents_tenant_id
        ON listing_documents (tenant_id)
'''))

# 3. Agency-controlled headline state on listings
db.execute(text('''
    ALTER TABLE listings
    ADD COLUMN IF NOT EXISTS documents_status VARCHAR(20) DEFAULT 'none'
'''))

db.commit()
print("listing_documents table + listings.documents_status added")
