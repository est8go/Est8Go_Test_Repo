from app.models_registry import register_all_models

register_all_models()

from app.conversations.intent_filter import (
    classify_intent,
    extract_budget_from_text,
    extract_location_from_text,
)

text = "looking for land in maitama budget 50m"

budget = extract_budget_from_text(text)
location = extract_location_from_text(text)
result = classify_intent(text, {})

print(f"Budget extracted:   {budget}")
print(f"Location extracted: {location}")
print(f"Intent:             {result.intent}")
print(f"Extracted dict:     {result.extracted}")
