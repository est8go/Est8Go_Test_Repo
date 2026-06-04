import os
from dotenv import load_dotenv
load_dotenv()
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

SQL = """
ALTER TABLE tenants
  DROP CONSTRAINT IF EXISTS tenants_tenant_type_check;
UPDATE tenants
SET tenant_type = 'platform'
WHERE id = 12;
"""

with engine.connect() as conn:
    conn.execute(text(SQL))
    conn.commit()
    print("Done: tenant 12 is now platform type")
