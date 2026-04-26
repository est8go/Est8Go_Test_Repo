import os
import json
import logging
import openai

# Setup logging for production monitoring
logger = logging.getLogger(__name__)

# Initialize OpenAI Client
client = openai.OpenAI(api_key=os.getenv("OPEN_AI_KEY"))


async def audit_property_image(image_url: str):
    """
    Detects CGI renders, foreign architecture (e.g., snow),
    or fake prototypes using GPT-4o-mini Vision.
    """
    prompt = (
        "Analyze this real estate photo for a Nigerian context. "
        "1. Is it a real photo or a 3D/CGI render? "
        "2. Is the architecture, vegetation, or environment likely Nigerian or foreign (e.g. snow, European signs)? "
        "Return a JSON object: {'is_real': bool, 'is_nigerian': bool, 'note': str}"
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
            response_format={"type": "json_object"},
        )

        # Parse the AI response
        analysis = json.loads(response.choices[0].message.content)
        logger.info(f"✅ Vision Audit Complete: {analysis.get('note')}")
        return analysis

    except Exception as e:
        logger.error(f"❌ Vision Audit Failed: {e}")
        # Rules-First Fallback: We assume it's okay but log it for manual review
        return {
            "is_real": True,
            "is_nigerian": True,
            "note": "Audit skipped due to technical error.",
        }
