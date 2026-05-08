from app.models_registry import register_all_models
from app.conversations.intent_filter import (
    classify_intent,
    extract_budget_from_text,
    extract_location_from_text,
)

register_all_models()


tests = [
    ("Land Maitama", {}),
    ("I want land in Maitama", {}),
    ("My budget is 50m", {"location": "maitama", "property_type": "land"}),
]

for text, prefs in tests:
    result = classify_intent(text, prefs)
    budget = extract_budget_from_text(text)
    location = extract_location_from_text(text)
    print(f"\nText: '{text}'")
    print(f"  Intent:   {result.intent}")
    print(f"  Extracted:{result.extracted}")
    print(f"  Budget:   {budget}")
    print(f"  Location: {location}")
    print(f"  GPT:      {result.needs_gpt}")
