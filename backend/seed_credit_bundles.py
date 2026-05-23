from app.models_registry import register_all_models
register_all_models()
from app.database.db import get_db
from app.credits.models import CreditBundle

db = next(get_db())

bundles = [
    {"name": "Starter", "credits": 50,   "bonus_credits": 0,   "price_ngn": 2500,  "display_order": 1},
    {"name": "Growth",  "credits": 200,  "bonus_credits": 20,  "price_ngn": 8000,  "display_order": 2},
    {"name": "Pro",     "credits": 600,  "bonus_credits": 60,  "price_ngn": 20000, "display_order": 3},
    {"name": "Scale",   "credits": 1500, "bonus_credits": 200, "price_ngn": 42000, "display_order": 4},
]

for b in bundles:
    existing = db.query(CreditBundle).filter(CreditBundle.name == b["name"]).first()
    if not existing:
        db.add(CreditBundle(**b))
        print(f"[OK] Added bundle: {b['name']} - {b['credits']} credits - N{b['price_ngn']:,}")
    else:
        print(f"[SKIP] Bundle exists: {b['name']}")

db.commit()
print("\n[OK] Credit bundles seeded")
