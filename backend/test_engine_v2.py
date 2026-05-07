from app.models_registry import register_all_models
from app.conversations.intent_filter import (
    classify_intent,
    extract_budget_from_text,
    extract_location_from_text,
)

register_all_models()


tests = [
    # Original failing tests
    ("Land Maitama", {}),
    ("I'm interested in a land around Maitama axis", {}),
    ("My budget range is 5m to 1b", {"location": "maitama", "property_type": "land"}),
    ("Dry land", {}),
    ("I want a land", {}),
    ("5m to 1b", {}),
    ("50m", {}),
    # Property type tests
    ("I want a 3 bedroom apartment in Lekki", {}),
    ("Looking for a duplex in Asokoro", {}),
    ("Finished house in Maitama", {}),
    ("I need a 2 bedroom flat", {}),
    ("Commercial property in Wuse 2", {}),
    ("I want a finished apartment", {}),
    ("3 bedroom in Gwarinpa budget 45m", {}),
    ("house in VI 100m", {}),
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
