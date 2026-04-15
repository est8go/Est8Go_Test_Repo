from app.database.db import SessionLocal
from app.ai_cache.models import AiCache

db = SessionLocal()
rows = db.query(AiCache).all()

print(f"Rows in AiCache: {len(rows)}")
for r in rows[-10:]:
    print(r.tenant_id, r.state, r.prompt_key, "=>", r.answer[:60])
db.close()