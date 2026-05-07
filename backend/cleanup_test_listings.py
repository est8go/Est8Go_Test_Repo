from app.models_registry import register_all_models
from app.database.db import get_db
from app.listings.models import Listing

register_all_models()


db = next(get_db())

# Delete test listings with placeholder data
bad = (
    db.query(Listing)
    .filter(Listing.title.in_(["string", "test", "Test", "STRING"]))
    .all()
)

if not bad:
    print("✅ No test listings found")
else:
    for l in bad:
        print(f"🗑️ Deleting: ID={l.id} | Title={l.title}")
        db.delete(l)
    db.commit()
    print(f"✅ Deleted {len(bad)} test listings")
