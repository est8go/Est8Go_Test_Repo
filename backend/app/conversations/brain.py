# backend/app/conversations/brain.py
import os
import json
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)


def extract_preferences(text: str, current_data: dict) -> dict:
    api_key = os.getenv("OPENAI_API_KEY")
    client = OpenAI(api_key=api_key)

    # UPDATED: Explicit instruction to remain FLAT
    system_instruction = """
    You are a Nigerian Real Estate Data Extractor. 
    
    OUTPUT RULE: Return a FLAT JSON object. Do NOT nest the data inside keys like 'current_data'.
    
    CRITICAL RULE: Preserve existing values from the 'Current Memory' unless the user changes them.
    
    Extract these fields:
    - intent (buy/rent/invest)
    - property_type (land/house/apartment)
    - location (neighborhood or city)
    - budget (integer only)
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_instruction},
                {
                    "role": "user",
                    "content": f"Current Memory: {json.dumps(current_data)}\nInput: '{text}'",
                },
            ],
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        logger.error(f"❌ AI Extraction Error: {e}")
        return current_data
