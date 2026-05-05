import json
from app.models_registry import register_all_models
from app.database.db import get_db
from app.conversations.models import Conversation

register_all_models()


db = next(get_db())

convos = (
    db.query(Conversation)
    .filter(Conversation.external_user_id.contains("9422222"))
    .all()
)

for c in convos:
    print(f"ID: {c.id}")
    print(f"State: {c.state}")
    print(f"Funnel: {c.funnel_stage}")
    print(f"Score: {c.lead_score}")
    print(f"Bot Active: {c.is_bot_active}")
    print(f"Data: {c.data_json}")
    print("---")
