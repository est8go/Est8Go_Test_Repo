"""
EST8GO INTENT PRE-FILTER (v2.0)
================================
Rules-First Layer (80/20 Mandate):
Handles 80%+ of incoming messages using pure Python.
Only truly ambiguous messages escalate to GPT.

Fixes in v2.0:
    - "interested" removed from AGREEMENT_WORDS (was triggering on property queries)
    - Property type extraction added (land, house, apartment, etc.)
    - Budget range parser ("5m to 1b" → takes upper bound)
    - Location always merged into extracted dict
    - Filler words tightened (no longer swallowing "ok" when prefs incomplete)
    - "I want a land" / "Dry land" now extracts property_type correctly
    - search_ready intent when budget + location both present
    - GPT only called for truly ambiguous messages
"""

import re
from dataclasses import dataclass
from typing import Optional

# ================================================================
# INTENT RESULT
# ================================================================


@dataclass
class IntentResult:
    intent: str
    confidence: str
    extracted: dict
    response_key: str
    needs_gpt: bool


# ================================================================
# KEYWORD MAPS
# ================================================================

GREETING_WORDS = {
    "hi",
    "hello",
    "hey",
    "start",
    "greetings",
    "good morning",
    "good afternoon",
    "good evening",
    "howdy",
    "hiya",
    "sup",
    "yo",
    "oga",
}

# CRITICAL: "interested" and "visit" removed — they appear in property queries
AGREEMENT_WORDS = {
    "yes",
    "yeah",
    "yep",
    "yh",
    "connect",
    "proceed",
    "go ahead",
    "let's go",
    "lets go",
    "i'm in",
    "im in",
    "schedule",
    "inspection",
    "i want it",
    "book",
    "confirm",
    "deal",
    "accept",
    "sure thing",
    "absolutely",
    "definitely",
}

RESTART_WORDS = {
    "new search",
    "restart",
    "start again",
    "start over",
    "reset",
    "clear",
    "fresh start",
    "begin again",
    "new search 🔍",
    "new search🔍",
}

# Only pure filler — never swallow messages that contain property info
FILLER_WORDS = {
    "noted",
    "thanks",
    "thank you",
    "alright",
    "cool",
    "got it",
    "seen",
    "amen",
    "wow",
    "wonderful",
    "nice one",
}

MEDIA_REQUEST_WORDS = {
    "video",
    "send video",
    "pictures",
    "photos",
    "pics",
    "send pictures",
    "show me",
    "images",
    "gallery",
    "footage",
    "clip",
    "reel",
    "tour",
    "virtual tour",
    "whatsapp video",
    "send me video",
}

AVAILABILITY_WORDS = {
    "still available",
    "is it available",
    "available",
    "still there",
    "sold",
    "taken",
    "gone",
    "is this still",
    "still up",
}

PRICE_TRIGGER_WORDS = {
    "price",
    "how much",
    "cost",
    "budget",
    "naira",
    "negotiate",
    "last price",
    "best price",
    "discount",
    "reduce",
    "payment plan",
    "installment",
    "mortgage",
    "flexible",
    "afford",
    "range",
    "between",
}

# Nigerian locations — comprehensive
LOCATION_WORDS = [
    # Abuja
    "maitama",
    "asokoro",
    "gwarinpa",
    "kabusa",
    "katampe",
    "jabi",
    "wuse",
    "wuse 2",
    "garki",
    "kubwa",
    "lugbe",
    "galadimawa",
    "apo",
    "lifecamp",
    "bwari",
    "kuje",
    "lokogoma",
    "nbora",
    "dawaki",
    "dutse",
    "guzape",
    "abuja",
    "fct",
    # Lagos
    "lekki",
    "victoria island",
    "ikoyi",
    "ajah",
    "surulere",
    "yaba",
    "ikeja",
    "magodo",
    "ojodu",
    "gbagada",
    "maryland",
    "lagos",
    "mainland",
    "island",
    "chevron",
    "vgc",
    "sangotedo",
    "badore",
    "epe",
    # Other cities
    "ph",
    "port harcourt",
    "gra ph",
    "rumuola",
    "ibadan",
    "kano",
    "enugu",
    "benin",
    "warri",
    "owerri",
    "calabar",
    "uyo",
    "abuja",
    "jos",
    "kaduna",
    "zaria",
    "sokoto",
    "ilorin",
    # Generic location words
    "axis",
    "area",
    "estate",
    "zone",
    "district",
    "around",
    "near",
    "close to",
    "beside",
]

# Property type keywords
PROPERTY_TYPE_MAP = {
    "land": ["land", "plot", "dry land", "land plot", "open land", "plots"],
    "house": [
        "house",
        "duplex",
        "mansion",
        "bungalow",
        "terrace",
        "townhouse",
        "semi-detached",
        "fully detached",
        "detached",
    ],
    "apartment": [
        "apartment",
        "flat",
        "studio",
        "penthouse",
        "condo",
        "1 bedroom",
        "2 bedroom",
        "3 bedroom",
        "4 bedroom",
        "1br",
        "2br",
        "3br",
        "4br",
        "1bed",
        "2bed",
        "3bed",
        "bedroom",
    ],
    "commercial": [
        "commercial",
        "office",
        "shop",
        "warehouse",
        "plaza",
        "mall",
        "retail",
        "showroom",
    ],
}

# 12 Nigerian RE objections
OBJECTION_MAP = {
    "get back to you": "objection_stalling",
    "i'll think": "objection_stalling",
    "let me think": "objection_stalling",
    "i will think": "objection_stalling",
    "think about it": "objection_stalling",
    "send me the video": "objection_media",
    "send video": "objection_media",
    "whatsapp video": "objection_media",
    "is this still": "objection_availability",
    "still available": "objection_availability",
    "last price": "objection_price",
    "can owner reduce": "objection_price",
    "can you reduce": "objection_price",
    "too expensive": "objection_price",
    "not my budget": "objection_budget_mismatch",
    "above my budget": "objection_budget_mismatch",
    "my wife": "objection_third_party",
    "my husband": "objection_third_party",
    "my partner": "objection_third_party",
    "show me others": "objection_more_options",
    "any other": "objection_more_options",
    "other options": "objection_more_options",
    "not interested": "objection_cold",
    "forget it": "objection_cold",
    "abeg": "objection_nigerian_casual",
}


# ================================================================
# EXTRACTORS
# ================================================================


def extract_budget_from_text(text: str) -> Optional[int]:
    """
    Extracts budget from Nigerian RE messages.
    Handles:
        - "50m", "50 million" → 50,000,000
        - "5m to 1b" → takes UPPER bound 1,000,000,000
        - "5m - 50m"  → takes UPPER bound 50,000,000
        - "₦50,000,000" → 50,000,000
        - Plain large numbers
    """
    text = text.lower().replace(",", "").replace("₦", "").replace("naira", "").strip()

    # Pattern: range like "5m to 1b" or "5m - 50m" → take upper bound
    range_pattern = r"(\d+\.?\d*)\s*(?:m\b|million)?\s*(?:to|-)\s*(\d+\.?\d*)\s*(?:b\b|billion|m\b|million)"
    range_match = re.search(range_pattern, text)
    if range_match:
        val1 = float(range_match.group(1))
        val2 = float(range_match.group(2))
        # Determine units
        after_val2 = text[range_match.end(2) :]
        if "b" in after_val2[:8] or "billion" in after_val2[:12]:
            upper = int(val2 * 1_000_000_000)
        else:
            upper = int(val2 * 1_000_000)
        return upper

    # Pattern: number + billion
    billion_pattern = r"(\d+\.?\d*)\s*(?:b\b|billion)"
    b_match = re.search(billion_pattern, text)
    if b_match:
        return int(float(b_match.group(1)) * 1_000_000_000)

    # Pattern: number + million/m
    million_pattern = r"(\d+\.?\d*)\s*(?:m\b|million)"
    m_match = re.search(million_pattern, text)
    if m_match:
        return int(float(m_match.group(1)) * 1_000_000)

    # Plain large number (7+ digits)
    plain_pattern = r"\b(\d{7,})\b"
    plain_match = re.search(plain_pattern, text)
    if plain_match:
        return int(plain_match.group(1))

    return None


def extract_location_from_text(text: str) -> Optional[str]:
    """
    Extracts Nigerian location mentions.
    Returns the most specific match found.
    """
    text_lower = text.lower()

    # Try multi-word locations first (more specific)
    multi_word = [l for l in LOCATION_WORDS if " " in l]
    for loc in multi_word:
        if loc in text_lower:
            return loc

    # Then single word locations
    words = set(text_lower.split())
    single_word = [l for l in LOCATION_WORDS if " " not in l]
    for loc in single_word:
        if loc in text_lower and loc not in {"area", "around", "near", "zone"}:
            return loc

    return None


def extract_property_type(text: str) -> Optional[str]:
    """
    Extracts property type from message.
    Returns: 'land', 'house', 'apartment', 'commercial'
    """
    text_lower = text.lower()
    for prop_type, keywords in PROPERTY_TYPE_MAP.items():
        for kw in keywords:
            if kw in text_lower:
                return prop_type
    return None


def extract_intent_keywords(text: str) -> dict:
    """
    Master extractor — runs all extractors and returns everything found.
    """
    result = {}
    budget = extract_budget_from_text(text)
    location = extract_location_from_text(text)
    prop_type = extract_property_type(text)
    if budget:
        result["budget"] = budget
    if location:
        result["location"] = location
    if prop_type:
        result["property_type"] = prop_type
    return result


# ================================================================
# MAIN CLASSIFIER
# ================================================================


def classify_intent(text: str, current_prefs: dict = None) -> IntentResult:
    """
    Classifies incoming message intent using pure Python rules.
    Priority order:
        1. Restart
        2. Greeting
        3. Objection
        4. Media request
        5. Availability
        6. Data extraction (budget + location + property type)
        7. Search ready (all required data present)
        8. Agreement / Handshake
        9. Filler
        10. Unknown → GPT
    """
    if current_prefs is None:
        current_prefs = {}

    text_clean = (text or "").strip()
    text_lower = text_clean.lower()
    words = set(text_lower.split())
    extracted = {}

    # ── 1. RESTART ──────────────────────────────────────
    if any(w in text_lower for w in RESTART_WORDS):
        return IntentResult(
            intent="restart",
            confidence="high",
            extracted={},
            response_key="fresh_start",
            needs_gpt=False,
        )

    # ── 2. GREETING ─────────────────────────────────────
    # Only match if message is short (≤3 words) to avoid "hi I want land"
    if len(text_clean.split()) <= 3 and any(w in words for w in GREETING_WORDS):
        return IntentResult(
            intent="greeting",
            confidence="high",
            extracted={},
            response_key="double_tap_greeting",
            needs_gpt=False,
        )

    # ── 3. OBJECTION ────────────────────────────────────
    for phrase, response_key in OBJECTION_MAP.items():
        if phrase in text_lower:
            return IntentResult(
                intent="objection",
                confidence="high",
                extracted={"objection_type": response_key},
                response_key=response_key,
                needs_gpt=False,
            )

    # ── 4. MEDIA REQUEST ────────────────────────────────
    if any(w in text_lower for w in MEDIA_REQUEST_WORDS):
        return IntentResult(
            intent="media_request",
            confidence="high",
            extracted={},
            response_key="media_redirect",
            needs_gpt=False,
        )

    # ── 5. AVAILABILITY ─────────────────────────────────
    if any(w in text_lower for w in AVAILABILITY_WORDS):
        return IntentResult(
            intent="availability",
            confidence="high",
            extracted={},
            response_key="availability_confirm",
            needs_gpt=False,
        )

    # ── 6. DATA EXTRACTION ──────────────────────────────
    # Run all extractors simultaneously
    extracted = extract_intent_keywords(text_lower)

    # Merge with current prefs to get full picture
    merged = {**current_prefs, **{k: v for k, v in extracted.items() if v}}

    has_budget = bool(merged.get("budget"))
    has_location = bool(merged.get("location"))
    has_prop_type = bool(merged.get("property_type"))

    # If we extracted anything useful — return immediately
    if extracted:
        # Check if search is now ready
        if has_budget and has_location:
            return IntentResult(
                intent="search_ready",
                confidence="high",
                extracted=extracted,
                response_key="search_trigger",
                needs_gpt=False,
            )

        # Budget extracted
        if extracted.get("budget") and not has_location:
            return IntentResult(
                intent="price_query",
                confidence="high",
                extracted=extracted,
                response_key="budget_captured",
                needs_gpt=False,
            )

        # Location extracted
        if extracted.get("location") and not has_budget:
            return IntentResult(
                intent="location_query",
                confidence="high",
                extracted=extracted,
                response_key="location_captured",
                needs_gpt=False,
            )

        # Property type only — ask for location next
        if extracted.get("property_type"):
            return IntentResult(
                intent="property_type_query",
                confidence="high",
                extracted=extracted,
                response_key="property_type_captured",
                needs_gpt=False,
            )

    # ── 7. PRICE TRIGGER WORDS (no number found yet) ────
    if any(w in text_lower for w in PRICE_TRIGGER_WORDS):
        return IntentResult(
            intent="price_query",
            confidence="high",
            extracted={},
            response_key="budget_nudge",
            needs_gpt=False,
        )

    # ── 8. AGREEMENT ────────────────────────────────────
    # Only trigger if message is short and contains agreement words
    # Never trigger on long property description messages
    if len(text_clean.split()) <= 5 and any(w in words for w in AGREEMENT_WORDS):
        return IntentResult(
            intent="agreement",
            confidence="high",
            extracted={},
            response_key="handshake_trigger",
            needs_gpt=False,
        )

    # ── 9. FILLER ───────────────────────────────────────
    # Only pure filler if message is very short and in filler set
    if len(text_clean.split()) <= 2 and text_lower in FILLER_WORDS:
        return IntentResult(
            intent="filler",
            confidence="high",
            extracted={},
            response_key="filler_ack",
            needs_gpt=False,
        )

    # ── 10. UNKNOWN → GPT ───────────────────────────────
    return IntentResult(
        intent="unknown",
        confidence="low",
        extracted={},
        response_key="gpt_extract",
        needs_gpt=True,
    )


# ================================================================
# LEAD SCORER
# ================================================================


def calculate_lead_score(prefs: dict, funnel_stage: str, session_count: int) -> int:
    """
    Scores a lead 0-100 using pure Python signal weighting.
    Zero AI — fully explainable to Realtors.
    """
    score = 0
    if prefs.get("budget"):
        score += 25
    if prefs.get("location"):
        score += 20
    if prefs.get("property_type"):
        score += 10

    stage_scores = {
        "awareness": 0,
        "verification": 10,
        "commitment": 20,
        "handshake": 30,
        "closed": 30,
    }
    score += stage_scores.get(funnel_stage, 0)

    # Returning visitor bonus (max 3 sessions = +15)
    score += min((session_count - 1) * 5, 15)

    return min(score, 100)


def determine_funnel_stage(prefs: dict, intent: str) -> str:
    """Determines funnel stage from conversation state."""
    if intent in ("agreement", "search_ready"):
        if prefs.get("budget") and prefs.get("location"):
            return "commitment"
    if intent == "handshake_trigger":
        return "handshake"

    has_budget = bool(prefs.get("budget"))
    has_location = bool(prefs.get("location"))

    if has_budget and has_location:
        return "commitment"
    if has_budget or has_location:
        return "verification"
    return "awareness"
