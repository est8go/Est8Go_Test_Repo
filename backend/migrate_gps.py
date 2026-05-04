from sqlalchemy import text
from app.database.db import engine

with engine.begin() as conn:
    conn.execute(
        text(
            "ALTER TABLE listings ADD COLUMN IF NOT EXISTS "
            "gps_location_match BOOLEAN DEFAULT FALSE"
        )
    )
    conn.execute(
        text(
            "ALTER TABLE listings ADD COLUMN IF NOT EXISTS "
            "gps_photo_match BOOLEAN DEFAULT FALSE"
        )
    )
    print("✅ GPS columns added")
