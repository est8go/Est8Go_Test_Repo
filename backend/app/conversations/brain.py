# app/conversations/brain.py
# (This file is now purely responsible for NLU (Natural Language Understanding). It runs silently in the background.)

from __future__ import annotations
import json
import logging
from typing import Optional

from pydantic import BaseModel, Field
from openai import OpenAI

logger = logging.getLogger(__name__)
client = OpenAI()


# ---------------------------------------------------------
# STRUCTURED OUTPUT SCHEMA
# ---------------------------------------------------------
class UserPreferences(BaseModel):
    intent: Optional[str] = Field(description="buy, rent, or invest", default=None)
    property_type: Optional[str] = Field(
        description="land, house, apartment, duplex, etc.", default=None
    )
    budget: Optional[int] = Field(
        description="Strict integer budget. Convert '20m' to 20000000, '5k' to 5000",
        default=None,
    )
    location: Optional[str] = Field(
        description="Target city, state, or neighborhood", default=None
    )


# ---------------------------------------------------------
# NLU EXTRACTION
# ---------------------------------------------------------
def extract_preferences(user_text: str, current_data: dict) -> dict:
    """SILENT BACKGROUND LLM: Parses natural language into JSON without talking to the user."""
    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"Extract real estate preferences. Current known data: {json.dumps(current_data)}. Do not overwrite existing data unless the user explicitly changed their mind.",
                },
                {"role": "user", "content": user_text},
            ],
            response_format=UserPreferences,
        )

        extracted = completion.choices[0].message.parsed

        # Merge new extracted data with current data (ignore nulls)
        for key, value in extracted.dict(exclude_none=True).items():
            current_data[key] = value

        return current_data

    except Exception as e:
        logger.error(f"LLM Extraction failed: {e}")
        return current_data
