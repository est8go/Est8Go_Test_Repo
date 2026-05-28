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
    "ibadan":        "Bodija, Jericho, Ring Road, Agodi, Oluyole, Iyaganku, Mokola",
    "kano":          "Nassarawa, Fagge, Tarauni, Gwale, Dala, Ungogo",
    "enugu":         "GRA, Independence Layout, New Haven, Asata, Achara Layout, Coal Camp",
    "benin":         "GRA, Ugbowo, Ekosodin, Uselu, Esigie, New Benin, Akpakpava",
    "benin city":    "GRA, Ugbowo, Ekosodin, Uselu, Esigie, New Benin, Akpakpava",
    "warri":         "Effurun, GRA, Ekpan, Ugborikoko, Okumagba, Pessu, Igbudu",
    "owerri":        "New Owerri, Ikenegbu, Aladinma, Oforola, Nekede, Uratta",
    "calabar":       "GRA, State Housing, CRUTECH, Big Qua, Lemna, Diamond Hill",
    "uyo":           "GRA, Ewet Housing, Wellington Bassey, Shelter Afrique, Itam",
    "jos":           "GRA, Rayfield, Tudun Wada, Nassarawa, Angwan Rogo, Bukuru",
    "kaduna":        "GRA, Barnawa, Ungwan Rimi, Malali, Rigasa, Kawo, Tudun Wada",
    "ilorin":        "GRA, Oke Ose, Fate, Tanke, Adewole, Unity, Ipata",
    "abeokuta":      "Ibara, Oke Mosan, Panseke, Kemta, Asero, Sapon",
    "asaba":         "GRA, Okpanam, Cable Point, Infant Jesus, Akwuzu",
    "makurdi":       "High Level, Low Level, North Bank, Wurukum, Modern Market, Idye, Ankpa Quarters, Wadata, Logo1, Logo2, Cocacola",
}

LOCATION_ALIASES = {
    # Abuja
    "gwarimpa":          "gwarinpa",
    "gwariampa":         "gwarinpa",
    "maitamma":          "maitama",
    "wuse2":             "wuse",
    "wuse 2":            "wuse",
    "wi":                "wuse",
    # Lagos
    "lekki 1":           "lekki",
    "lekki phase 1":     "lekki",
    "lekki phase1":      "lekki",
    "v.i":               "victoria island",
    "vi":                "victoria island",
    "v/i":               "victoria island",
    "ikeja gra":         "ikeja",
    # Port Harcourt
    "p.h":               "port harcourt",
    # General
    "trans amadi":       "trans amadi",
    "gra":               "gra",
    "maryland":          "maryland",
    "ikoyi":             "ikoyi",
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


def normalise_location(loc: str) -> str:
    if not loc:
        return loc
    loc_lower = loc.lower().strip()
    return LOCATION_ALIASES.get(loc_lower, loc_lower)


# ================================================================
# STATE MANAGER — Next Question Router
# ================================================================


def get_next_question(current_data: dict) -> Optional[str]:
    """
    Strict funnel order: property_type → city → area → budget → search.
    Picks up from any point — works with partial or full messages.
    """

    # STEP 1 — Property type missing
    if not current_data.get("property_type"):
        return (
            "What type of property are you looking for? 🏠\n\n"
            "Land — plots for development\n"
            "House — detached, semi-detached or duplex\n"
            "Apartment — flats and studio units"
        )

    # STEP 2 — Location missing entirely
    if not current_data.get("location"):
        prop_type = current_data.get("property_type", "property").title()
        return (
            f"Which city are you searching in for your {prop_type}? 🏙️\n\n"
            f"We cover Abuja, Lagos, Port Harcourt, "
            f"Ibadan, Enugu and more."
        )

    # STEP 3 — Location is city-level (needs specific area)
    location_val = (current_data.get("location") or "").lower().strip()
    if location_val in CITY_TERMS:
        examples = CITY_AREA_EXAMPLES.get(
            location_val,
            "please specify a neighbourhood or area"
        )
        city_display = location_val.title()
        return (
            f"Which area of *{city_display}* are you targeting? 📍\n\n"
            f"For example: {examples}\n\n"
            f"This helps me find the most relevant "
            f"verified properties for you."
        )

    # STEP 4 — Budget missing
    if not current_data.get("budget_max") and not current_data.get("budget"):
        prop_type = current_data.get("property_type", "property").title()
        location = current_data.get("location", "").title()
        return (
            f"What is your budget for the *{prop_type}* "
            f"in *{location}*? 💰\n\n"
            f"(e.g. '50m', '20m to 80m', '₦45,000,000')"
        )

    # STEP 5 — All collected, ready to search
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
