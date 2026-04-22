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

    system_instruction = """
    You are an expert Nigerian Real Estate Consultant. 
    Professional vocabulary: 'BQ', 'Self-contain', 'Duplex', 'C of O', 'R of O', 'Survey'.
    
    TASK: Extract property preferences from the user's text.
    - If user provides multiple details (e.g., "50m duplex in Guzape"), extract ALL.
    - If user wants to 'start again' or 'new search', set "reset_requested": true.
    
    RETURN JSON ONLY:
    {
      "intent": "buy" | "rent" | "invest" | null,
      "property_type": "mansion" | "duplex" | "land" | "apartment" | null,
      "location": "district name" | null,
      "budget": number | null,
      "reset_requested": boolean
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
