import os
import json
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)


def extract_preferences(text: str, current_data: dict) -> dict:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "not_using_this_yet":
        logger.error("❌ OPENAI_API_KEY is missing or placeholder")
        return current_data

    client = OpenAI(api_key=api_key)

    # --- THE 'ACCURACY' SOCKET ---
    system_instruction = """
    You are a specialized Nigerian Real Estate Data Extractor.
    Your only job is to turn natural chat into clean data.
    
    RULES:
    - If you see "Kabusa", "Maitama", "Guzape", extract them as 'location'.
    - If you see "million", "billion", "k", "m", convert them to full numbers (e.g., 5m -> 5000000).
    - If the user provides a budget range (e.g., 5m-10m), extract the HIGHER number.
    
    RETURN JSON ONLY:
    {
      "intent": "buy" | "rent" | "invest" | null,
      "property_type": "land" | "mansion" | "apartment" | "duplex" | null,
      "location": string | null,
      "budget": number | null
    }
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_instruction},
                {
                    "role": "user",
                    "content": f"Existing Data: {json.dumps(current_data)}\nUser says: '{text}'",
                },
            ],
            response_format={"type": "json_object"},  # Forces clean JSON
        )

        return json.loads(response.choices[0].message.content)
    except Exception as e:
        logger.error(f"❌ OpenAI Extraction Error: {e}")
        return current_data
