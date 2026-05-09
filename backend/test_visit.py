from app.models_registry import register_all_models

register_all_models()

from app.conversations.intent_filter import classify_intent

tests = [
    (
        "Yes I would like to schedule a visit",
        {
            "location": "maitama",
            "budget": 50000000,
            "property_type": "land",
            "last_viewed_id": 3,
        },
    ),
    ("Yes", {"location": "maitama", "budget": 50000000}),
    ("I want to visit", {}),
    ("Schedule a visit", {}),
]

for text, prefs in tests:
    result = classify_intent(text, prefs)
    print(f"Text: '{text}'")
    print(f"  Intent:   {result.intent}")
    print(f"  Extracted:{result.extracted}")
    print(f"  Response: {result.response_key}")
    print()
