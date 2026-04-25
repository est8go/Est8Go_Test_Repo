import os
import json
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)


def extract_preferences(text: str, current_data: dict) -> dict:
    api_key = os.getenv("OPENAI_API_KEY")
    client = OpenAI(api_key=api_key)

    # THE MEMORY SOCKET: We pass the old data and tell it NOT to delete anything
    system_instruction = """
    You are a Nigerian Real Estate Data Extractor. 
    
    CRITICAL RULE: Do NOT erase any existing data in 'current_data' unless the user explicitly changes it. 
    If the user says "land" and the intent was already "invest", the output must keep "invest".
    
    Convert all numbers (5m -> 5000000).
    Extract: intent, property_type, location, budget.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_instruction},
                {
                    "role": "user",
                    "content": f"CURRENT MEMORY: {json.dumps(current_data)}\nUSER INPUT: '{text}'",
                },
            ],
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        logger.error(f"❌ AI Extraction Error: {e}")
        return current_data
