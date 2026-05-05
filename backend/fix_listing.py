from app.models_registry import register_all_models
from app.database.db import get_db
from app.listings.models import Listing

register_all_models()


db = next(get_db())

listing = db.query(Listing).filter(Listing.id == 3).first()

if not listing:
    print("❌ Listing not found")
else:
    listing.deed_uploaded = True
    listing.cof_uploaded = True
    listing.survey_uploaded = True
    listing.gps_photo_match = True
    listing.ai_verified_real = True
    listing.trust_score = 88
    listing.trust_grade = "emerald"
    db.commit()
    print(f"✅ Updated listing {listing.id}")
    print(f"   Trust Score: {listing.trust_score}")
    print(f"   Trust Grade: {listing.trust_grade}")
