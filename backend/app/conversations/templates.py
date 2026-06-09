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


def get_next_question(
    current_data: dict,
    tenant_areas_by_budget: list = None,
) -> Optional[str]:
    """
    New funnel order:
    purpose → property_type → bedrooms (if residential) → budget → area (guided) → search
    """

    # STEP 1 — Purpose (handled by opener, skip if not set)
    if not current_data.get("purpose"):
        return None

    # STEP 2 — Property type
    if not current_data.get("property_type"):
        purpose = current_data.get("purpose", "")
        if purpose == "investment":
            return (
                "What type of property are you investing in? 🏢\n\n"
                "🌱 *Land* — buy and hold or develop\n"
                "🏠 *House* — rental income or capital gain\n"
                "🏢 *Apartment* — high yield rental in prime areas"
            )
        else:
            return (
                "What type of property are you looking for? 🏠\n\n"
                "🌱 *Land* — build your dream home\n"
                "🏠 *House* — move-in ready family home\n"
                "🏢 *Apartment* — modern city living"
            )

    # STEP 3 — Bedrooms (only for house/apartment + personal use)
    prop_type = current_data.get("property_type", "")
    purpose = current_data.get("purpose", "")

    if (
        prop_type in ("house", "apartment")
        and purpose == "personal"
        and not current_data.get("bedrooms")
        and not current_data.get("bedrooms_skipped")
    ):
        return (
            f"How many bedrooms do you need for your {prop_type}? 🛏️\n\n"
            f"1 bed · 2 bed · 3 bed · 4 bed · 5+ bed\n\n"
            f"(Or say *Any* if flexible)"
        )

    # STEP 4 — Budget (before location)
    if not current_data.get("budget_max") and not current_data.get("budget"):
        prop_type_title = prop_type.title()
        purpose_hint = ""
        if purpose == "investment":
            purpose_hint = (
                "\n\nMost verified investment properties start from ₦15M. "
                "Returns depend on location and trust grade."
            )
        return (
            f"What is your budget for this {prop_type_title}? 💰\n\n"
            f"(e.g. '30M', '20M to 80M', '₦45,000,000'){purpose_hint}"
        )

    # STEP 5 — Area guided by budget
    location_val = (current_data.get("location") or "").lower().strip()
    city_locked = (current_data.get("city_locked") or "").lower().strip()

    # Need a specific area if:
    # - No location set at all
    # - Location is a broad city name (too wide to search)
    # - Location was set to the locked city by city_locked injection (not a real area)
    needs_area = (
        not location_val
        or location_val in CITY_TERMS
        or (city_locked and location_val == city_locked)
    )

    if needs_area:
        budget = current_data.get("budget_max") or current_data.get("budget") or 0
        budget_fmt = f"₦{int(budget)/1_000_000:.0f}M" if budget else ""

        if tenant_areas_by_budget and len(tenant_areas_by_budget) > 0:
            areas_list = "\n".join([
                f"📍 *{a['area'].title()}* — from ₦{a['min_price']/1_000_000:.0f}M"
                for a in tenant_areas_by_budget[:4]
            ])
            return (
                f"For *{budget_fmt}* we have verified {prop_type.title()} listings in:\n\n"
                f"{areas_list}\n\n"
                f"Which area interests you? Or type a specific area you have in mind. 📍"
            )
        else:
            return (
                "Which area are you targeting? 📍\n\n"
                "Tell me the neighbourhood or estate and I'll search our verified listings."
            )

    # All collected — ready to search
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
