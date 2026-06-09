"""Migration: add coverage_cities column + auto-detect cities from existing listings."""
from app.models_registry import register_all_models
register_all_models()
from app.database.db import get_db
from sqlalchemy import text
import json

db = next(get_db())

# 1 — Add column
db.execute(text("""
    ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS coverage_cities JSONB DEFAULT '[]'
"""))
db.commit()
print("Column added")

# 2 — Auto-detect cities from existing listings
from app.tenants.models import Tenant
from app.listings.models import Listing

CITY_DETECTION = {
    "abuja": [
        "abuja", "fct", "maitama", "asokoro", "gwarinpa", "wuse",
        "garki", "jabi", "kubwa", "lugbe", "apo", "lifecamp",
        "guzape", "katampe", "nbora", "dawaki", "gwagwalada", "kuje",
        "bwari", "galadimawa",
    ],
    "lagos": [
        "lagos", "lekki", "ikeja", "victoria island", "ikoyi",
        "ajah", "surulere", "yaba", "gbagada", "maryland", "magodo",
        "chevron", "vgc", "sangotedo",
    ],
    "port harcourt": [
        "port harcourt", "ph", "gra ph", "rumuola", "trans amadi",
        "rumuokoro", "elekahia",
    ],
    "enugu": [
        "enugu", "independence layout", "gra enugu", "new haven",
        "asata", "achara",
    ],
    "ibadan": [
        "ibadan", "bodija", "jericho", "ring road", "agodi", "oluyole",
    ],
}

tenants = db.query(Tenant).filter(Tenant.is_active == True).all()

for tenant in tenants:
    if getattr(tenant, "tenant_type", "") == "platform":
        continue

    listings = db.query(Listing).filter(Listing.tenant_id == tenant.id).all()
    detected = set()
    for listing in listings:
        loc = (listing.location or "").lower()
        for city, keywords in CITY_DETECTION.items():
            if any(kw in loc for kw in keywords):
                detected.add(city)

    if detected:
        tenant.coverage_cities = list(detected)
        print(f"Tenant {tenant.id} ({tenant.business_name}): {list(detected)}")

db.commit()
print("Done — cities detected and saved")
