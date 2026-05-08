# test_funnel.py
from app.models_registry import register_all_models
from app.conversations.templates import get_next_question

register_all_models()


tests = [
    {},
    {"property_type": "land"},
    {"property_type": "land", "location": "maitama"},
    {"property_type": "land", "location": "maitama", "budget": 50000000},
    {
        "property_type": "land",
        "location": "maitama",
        "budget": 50000000,
        "intent": "buy",
    },
]

for data in tests:
    q = get_next_question(dict(data))
    print(f"Data: {data}")
    print(f"  Next Q: {q}")
    print()
