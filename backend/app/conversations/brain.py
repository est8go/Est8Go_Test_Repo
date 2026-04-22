import os
import json
import logging
import google.generativeai as genai  # Back to the stable version

logger = logging.getLogger(__name__)


def extract_preferences(text: str, current_data: dict) -> dict:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return current_data

    # 1. Configure the Stable Library
    genai.configure(api_key=api_key)

    # 2. Use the stable 1.5 Flash (Production Ready)
    model = genai.GenerativeModel("gemini-1.5-flash")

    system_instruction = """
    You are an expert Nigerian Real Estate Consultant. 
    Vocabulary: 'BQ', 'Self-contain', 'Duplex', 'C of O', 'R of O', 'Survey'.
    Extract: intent (buy/rent), property_type, location, budget.
    If user wants to 'start again', set "reset_requested": true.
    """

    prompt = f"{system_instruction}\n\nExisting Data: {json.dumps(current_data)}\nUser: '{text}'"

    try:
        response = model.generate_content(prompt)
        # Clean and parse JSON
        cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned_text)
    except Exception as e:
        logger.error(f"❌ AI Extraction Error: {e}")
        return current_data
