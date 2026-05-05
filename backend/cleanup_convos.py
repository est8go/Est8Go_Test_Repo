from app.models_registry import register_all_models
from app.database.db import get_db
from app.conversations.models import Conversation
from sqlalchemy import func
from sqlalchemy import text

register_all_models()

db = next(get_db())

# Find all phone numbers with multiple conversations

result = db.execute(text("""
    SELECT external_user_id, tenant_id, COUNT(*) as cnt
    FROM conversations
    GROUP BY external_user_id, tenant_id
    HAVING COUNT(*) > 1
""")).fetchall()

deleted = 0
for row in result:
    phone = row[0]
    tenant = row[1]

    # Keep the one with most data, delete the rest
    convos = (
        db.query(Conversation)
        .filter_by(external_user_id=phone, tenant_id=tenant)
        .order_by(Conversation.lead_score.desc(), Conversation.updated_at.desc())
        .all()
    )

    # Keep first (highest score + most recent), delete rest
    for c in convos[1:]:
        db.delete(c)
        deleted += 1

db.commit()
print(f"✅ Cleaned up {deleted} duplicate conversations")
