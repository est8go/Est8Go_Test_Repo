# app/conversations/templates.py
# (This file now exclusively holds your Python strings, routing questions, and UI formatting).


from __future__ import annotations
from typing import List, Optional

# ---------------------------------------------------------
# FILLER BYPASS
# ---------------------------------------------------------
FILLER_WORDS = {
    "ok",
    "okay",
    "alright",
    "thanks",
    "thank you",
    "cool",
    "great",
    "yes",
    "yep",
    "noted",
}


def is_filler(text: str) -> bool:
    return text.strip().lower() in FILLER_WORDS


# ---------------------------------------------------------
# STATE MANAGER (Next Question Router)
# ---------------------------------------------------------
def get_next_question(current_data: dict) -> Optional[str]:
    """Evaluates JSON natively and asks the next logical missing question."""
    if not current_data.get("intent"):
        return "Quick one—are you looking to buy, rent, or invest?"

    if not current_data.get("property_type"):
        if current_data.get("intent", "").lower() == "rent":
            return (
                "Nice. Are you looking to rent a House/Apartment or a Commercial space?"
            )
        return "Great choice. Are you considering Land or a Built property (House/Apartment)?"

    if not current_data.get("budget"):
        return (
            "What budget range are you comfortable with?\n"
            "You can reply like: '5m–10m', '20m', or 'not sure'."
        )

    if not current_data.get("location"):
        return "Any preferred area or location? (e.g., Asokoro, Lekki, Wuse 2). If none, just say 'any good area'."

    return None  # All fields are filled!


# ---------------------------------------------------------
# UI FORMATTING
# ---------------------------------------------------------
def format_listings_text(listings: list) -> str:
    """Hardcoded string templates for displaying properties."""
    if not listings:
        return ""

    response = ["Here are some top properties that match your criteria:\n"]
    for i, listing in enumerate(listings, 1):
        response.append(
            f"{i}. {listing.title}\n"
            f"📍 {listing.location}\n"
            f"💰 ₦{listing.price:,}\n"
            f"🏠 {listing.property_type}\n"
            f"🖼 {listing.image_url if listing.image_url else 'Image available on request'}\n"
        )
    return "\n".join(response)


def calculate_typing_ms(text: str) -> int:
    return min(2500, max(800, len(text) * 15))
