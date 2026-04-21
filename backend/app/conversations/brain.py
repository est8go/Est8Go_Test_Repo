import os
import json
import logging
from google import genai  # <--- The NEW way to import


logger = logging.getLogger(__name__)


def extract_preferences(text: str, current_data: dict) -> dict:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.error("❌ GOOGLE_API_KEY missing")
        return current_data

    # Setup the NEW Client
    client = genai.Client(api_key=api_key)

    system_instruction = """
    You are an expert Nigerian Real Estate Consultant. 
    Professional vocabulary: 'BQ', 'Self-contain', 'Duplex', 'C of O', 'R of O', 'Survey'.
    Extract property preferences (Location, Budget, Property Type).
    If user wants to 'start fresh', set "reset_requested": true.
    """

    prompt = f"{system_instruction}\n\nExisting Data: {json.dumps(current_data)}\nUser: '{text}'"

    try:
        # The NEW way to generate content
        response = client.models.generate_content(
            model="gemini-2.0-flash", contents=prompt
        )

        cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned_text)
    except Exception as e:
        logger.error(f"❌ AI Error: {e}")
        return current_data
