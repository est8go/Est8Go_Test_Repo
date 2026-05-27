# app/conversations/templates.py
from __future__ import annotations
from typing import Optional

CITY_TERMS = {
    # Nigeria's major cities/states — too broad for property search
    "abuja", "fct", "lagos", "port harcourt", "ph",
    "ibadan", "kano", "enugu", "benin", "benin city",
    "warri", "owerri", "calabar", "uyo", "jos",
    "kaduna", "zaria", "sokoto", "ilorin", "asaba",
    "akure", "bauchi", "maiduguri", "yola", "gombe",
    "lafia", "lokoja", "makurdi", "abeokuta", "ado ekiti",
    "osogbo", "ile ife", "oyo", "sagamu", "mainland",
    "island",
}

CITY_AREA_EXAMPLES = {
    "abuja":         "Maitama, Asokoro, Gwarinpa, Wuse, Jabi, Garki, Lugbe, Kubwa",
    "fct":           "Maitama, Asokoro, Gwarinpa, Wuse, Jabi, Garki, Lugbe, Kubwa",
    "lagos":         "Lekki, Ikeja, Victoria Island, Ikoyi, Ajah, Surulere, Yaba, Magodo",
    "mainland":      "Surulere, Yaba, Gbagada, Ojodu, Maryland, Isolo, Festac",
    "island":        "Victoria Island, Ikoyi, Lekki, Ajah, Badagry",
    "port harcourt": "GRA, Trans Amadi, Rumuola, Rumuokoro, Elekahia, Diobu",
    "ph":            "GRA, Trans Amadi, Rumuola, Rumuokoro, Elekahia, Diobu",
    "ibadan":        "Bodija, Jericho, Ring Road, Agodi, Oluyole, Iyaganku",
    "kano":          "Nassarawa, Fagge, Tarauni, Gwale, Dala, Ungogo",
    "enugu":         "GRA, Independence Layout, New Haven, Asata, Achara Layout",
}

# ================================================================
# FILLER BYPASS
# ================================================================

# Tightened — only pure noise words, not property-related words
FILLER_WORDS = {
    "noted",
    "thanks",
    "thank you",
    "cool",
    "wow",
    "nice one",
    "amen",
    "wonderful",
    "seen",
}


def is_filler(text: str) -> bool:
    return text.strip().lower() in FILLER_WORDS


# ================================================================
# STATE MANAGER — Next Question Router
# ================================================================


def get_next_question(current_data: dict) -> Optional[str]:
    """
    Asks the next missing question in the sales funnel.

    Field priority (revised):
        1. property_type  — land / house / apartment
        2. location       — which area
        3. budget         — how much
        4. intent         — buy / rent / invest (lowest priority — inferred from context)

    Intent is now OPTIONAL — if property_type is land or house,
    we infer intent = "buy" automatically without asking.
    This stops the bot from looping on "buy/rent/invest?" forever.
    """

    # Auto-infer intent from property_type to avoid asking unnecessary question
    prop_type = (current_data.get("property_type") or "").lower()
    if prop_type and not current_data.get("intent"):
        if prop_type in ("land", "house", "apartment"):
            current_data["intent"] = "buy"
        elif prop_type == "commercial":
            current_data["intent"] = "invest"

    # Step 1: Need property type
    if not current_data.get("property_type"):
        return (
            "Are you looking for *Land*, a *House/Duplex*, or an *Apartment*? "
            "Also, which area are you targeting?"
        )

    # Step 2a: Location is city-level — need specific area
    location_val = (current_data.get("location") or "").lower().strip()
    if location_val and location_val in CITY_TERMS:
        examples = CITY_AREA_EXAMPLES.get(
            location_val,
            "please specify a neighbourhood or area"
        )
        return (
            f"Which part of {location_val.title()} are you "
            f"targeting? 📍\n\n"
            f"For example: {examples}\n\n"
            f"Specifying the area helps me find the most "
            f"relevant verified properties for you."
        )

    # Step 2: Need location
    if not current_data.get("location"):
        prop = current_data.get("property_type", "property").title()
        return (
            f"Great — {prop} noted! 📍\n"
            f"Which area or location are you targeting? "
            f"(e.g., Maitama, Asokoro, Lekki, Victoria Island)"
        )

    # Step 3: Need budget
    if not current_data.get("budget"):
        loc = current_data.get("location", "that area").title()
        return (
            f"Perfect — I'm scanning *{loc}* now. 🔍\n"
            f"What budget range are you working with? "
            f"(e.g., '50m', '20m to 80m', '₦45,000,000')"
        )

    # Step 4: Only ask intent if truly needed (rent vs buy matters for filtering)
    if not current_data.get("intent"):
        return "Are you looking to *buy* or *rent* this property?"

    # All fields filled — trigger search
    return None


# ================================================================
# UI FORMATTING
# ================================================================


def format_listings_text(listings: list) -> str:
    if not listings:
        return ""
    response = ["Here are some top properties that match your criteria:\n"]
    for i, listing in enumerate(listings, 1):
        response.append(
            f"{i}. {listing.title}\n"
            f"📍 {listing.location}\n"
            f"💰 ₦{listing.price:,}\n"
            f"🏠 {listing.property_type}\n"
        )
    return "\n".join(response)


def calculate_typing_ms(text: str) -> int:
    return min(2500, max(800, len(text) * 15))
