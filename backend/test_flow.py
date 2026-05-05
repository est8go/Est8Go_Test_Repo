from app.models_registry import register_all_models
from app.conversations.intent_filter import classify_intent

register_all_models()


tests = [
    "let me think about it",
    "yes",
    "i'll think about it",
    "sure",
]

for text in tests:
    result = classify_intent(text, {"budget": 50000000, "location": "maitama"})
    print(f"Text: '{text}'")
    print(f"  Intent:   {result.intent}")
    print(f"  Response: {result.response_key}")
    print(f"  GPT:      {result.needs_gpt}")
    print()
