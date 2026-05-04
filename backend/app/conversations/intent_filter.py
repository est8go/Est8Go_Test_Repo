"""
EST8GO INTENT PRE-FILTER
=========================
Rules-First Layer (80/20 Mandate):
Handles 70% of incoming messages using pure Python keyword matching.
Only ambiguous or complex messages escalate to GPT.

Zero AI cost. Millisecond response. 100% predictable.

Intent Categories:
    - GREETING       → Double-tap flow
    - PRICE_QUERY    → Budget extraction
    - LOCATION_QUERY → Location extraction
    - AVAILABILITY   → Property status check
    - MEDIA_REQUEST  → Video/photo request
    - OBJECTION      → 12 standard Nigerian RE objections
    - AGREEMENT      → Buyer is ready to proceed
    - RESTART        → Clear session
    - FILLER         → Noise (ok, thanks, noted)
    - UNKNOWN        → Escalate to GPT
"""

from dataclasses import dataclass

# ================================================================
# INTENT RESULT
# ================================================================


@dataclass
class IntentResult:
    intent: str  # the classified intent
    confidence: str  # 'high' (rules) or 'low' (escalate to GPT)
    extracted: dict  # any data extracted (budget, location, etc.)
    response_key: str  # maps to a Kora response template
    needs_gpt: bool  # True = escalate to GPT


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

AGREEMENT_WORDS = {
    "yes",
    "yeah",
    "yep",
    "yh",
    "sure",
    "ok",
    "okay",
    "connect",
    "interested",
    "proceed",
    "go ahead",
    "let's go",
    "lets go",
    "i'm in",
    "im in",
    "schedule",
    "visit",
    "inspection",
    "i want it",
    "book",
    "confirm",
    "deal",
    "accept",
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
}

FILLER_WORDS = {
    "ok",
    "okay",
    "noted",
    "thanks",
    "thank you",
    "alright",
    "cool",
    "got it",
    "seen",
    "amen",
    "nice",
    "wow",
    "great",
    "perfect",
    "wonderful",
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

PRICE_WORDS = {
    "price",
    "how much",
    "cost",
    "budget",
    "million",
    "naira",
    "₦",
    "m ",
    "m?",
    "negotiate",
    "last price",
    "best price",
    "discount",
    "reduce",
    "payment plan",
    "installment",
    "mortgage",
    "flexible",
}

LOCATION_WORDS = {
    "lekki",
    "VI",
    "victoria island",
    "ikoyi",
    "ajah",
    "abuja",
    "maitama",
    "asokoro",
    "gwarinpa",
    "jabi",
    "wuse",
    "garki",
    "kubwa",
    "lugbe",
    "katampe",
    "lagos",
    "ph",
    "port harcourt",
    "ibadan",
    "kano",
    "enugu",
    "where",
    "location",
    "area",
    "estate",
    "mainland",
    "island",
    "owerri",
    "benin",
    "warri",
}

# The 12 Standard Nigerian Real Estate Objections
OBJECTION_MAP = {
    # Objection text fragment → response key
    "get back to you": "objection_stalling",
    "i'll think": "objection_stalling",
    "let me think": "objection_stalling",
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
# BUDGET EXTRACTOR (Pure Python)
# ================================================================


def extract_budget_from_text(text: str) -> int | None:
    """
    Extracts budget figures from Nigerian real estate messages.
    Handles: '50m', '50 million', '₦50,000,000', '50M', '150m'
    Returns value in naira (integer) or None if not found.
    """
    import re

    text = text.lower().replace(",", "").replace("₦", "").strip()

    # Pattern: number followed by 'm' or 'million'
    pattern = r"(\d+\.?\d*)\s*(?:m\b|million)"
    match = re.search(pattern, text)
    if match:
        value = float(match.group(1))
        return int(value * 1_000_000)

    # Pattern: plain large number (e.g. 50000000)
    pattern2 = r"\b(\d{7,})\b"
    match2 = re.search(pattern2, text)
    if match2:
        return int(match2.group(1))

    return None


def extract_location_from_text(text: str) -> str | None:
    """
    Extracts Nigerian location mentions from message text.
    Returns the first matched location or None.
    """
    text_lower = text.lower()
    for location in LOCATION_WORDS:
        if location.lower() in text_lower:
            # Return properly cased version
            return location
    return None


# ================================================================
# MAIN CLASSIFIER
# ================================================================


def classify_intent(text: str, current_prefs: dict = None) -> IntentResult:
    """
    Classifies incoming message intent using pure Python rules.

    Args:
        text:          The raw message from the buyer
        current_prefs: Current conversation preferences (budget, location, etc.)

    Returns:
        IntentResult with intent, confidence, extracted data, and GPT flag
    """
    if current_prefs is None:
        current_prefs = {}

    text_clean = (text or "").strip()
    text_lower = text_clean.lower()
    extracted = {}

    # --- 1. RESTART (highest priority — memory wipe) ---
    if any(w in text_lower for w in RESTART_WORDS):
        return IntentResult(
            intent="restart",
            confidence="high",
            extracted={},
            response_key="fresh_start",
            needs_gpt=False,
        )

    # --- 2. GREETING ---
    if any(w in text_lower for w in GREETING_WORDS):
        return IntentResult(
            intent="greeting",
            confidence="high",
            extracted={},
            response_key="double_tap_greeting",
            needs_gpt=False,
        )

    # --- 3. AGREEMENT / HANDSHAKE TRIGGER ---
    if any(w in text_lower for w in AGREEMENT_WORDS):
        return IntentResult(
            intent="agreement",
            confidence="high",
            extracted={},
            response_key="handshake_trigger",
            needs_gpt=False,
        )

    # --- 4. OBJECTION DETECTION (12 standard objections) ---
    for phrase, response_key in OBJECTION_MAP.items():
        if phrase in text_lower:
            return IntentResult(
                intent="objection",
                confidence="high",
                extracted={"objection_type": response_key},
                response_key=response_key,
                needs_gpt=False,
            )

    # --- 5. MEDIA REQUEST ---
    if any(w in text_lower for w in MEDIA_REQUEST_WORDS):
        return IntentResult(
            intent="media_request",
            confidence="high",
            extracted={},
            response_key="media_redirect",
            needs_gpt=False,
        )

    # --- 6. AVAILABILITY CHECK ---
    if any(w in text_lower for w in AVAILABILITY_WORDS):
        return IntentResult(
            intent="availability",
            confidence="high",
            extracted={},
            response_key="availability_confirm",
            needs_gpt=False,
        )

    # --- 7. PRICE / BUDGET EXTRACTION ---
    budget = extract_budget_from_text(text_lower)
    if budget:
        extracted["budget"] = budget
        return IntentResult(
            intent="price_query",
            confidence="high",
            extracted=extracted,
            response_key="budget_captured",
            needs_gpt=False,
        )

    if any(w in text_lower for w in PRICE_WORDS):
        return IntentResult(
            intent="price_query",
            confidence="high",
            extracted={},
            response_key="budget_nudge",
            needs_gpt=False,
        )

    # --- 8. LOCATION EXTRACTION ---
    location = extract_location_from_text(text_lower)
    if location:
        extracted["location"] = location
        return IntentResult(
            intent="location_query",
            confidence="high",
            extracted=extracted,
            response_key="location_captured",
            needs_gpt=False,
        )

    # --- 9. FILLER (noise — no response needed) ---
    if text_lower in FILLER_WORDS or len(text_clean) <= 3:
        return IntentResult(
            intent="filler",
            confidence="high",
            extracted={},
            response_key="filler_ack",
            needs_gpt=False,
        )

    # --- 10. UNKNOWN — escalate to GPT ---
    return IntentResult(
        intent="unknown",
        confidence="low",
        extracted={},
        response_key="gpt_extract",
        needs_gpt=True,
    )


# ================================================================
# LEAD SCORER (Pure Python)
# ================================================================


def calculate_lead_score(prefs: dict, funnel_stage: str, session_count: int) -> int:
    """
    Scores a lead 0-100 based on conversation signals.
    Pure Python — zero AI cost. Fully explainable to Realtors.

    Scoring:
        Budget provided        = +25 pts
        Location provided      = +20 pts
        Property type known    = +10 pts
        Funnel stage bonus     = +10-30 pts
        Returning visitor      = +5 pts per session (max +15)
        Response speed bonus   = +5 pts (handled externally)
    """
    score = 0

    # Data completeness
    if prefs.get("budget"):
        score += 25
    if prefs.get("location"):
        score += 20
    if prefs.get("property_type"):
        score += 10

    # Funnel stage bonus
    stage_scores = {
        "awareness": 0,
        "verification": 10,
        "commitment": 20,
        "handshake": 30,
        "closed": 30,
    }
    score += stage_scores.get(funnel_stage, 0)

    # Returning visitor bonus (max 3 sessions = +15)
    returning_bonus = min((session_count - 1) * 5, 15)
    score += returning_bonus

    return min(score, 100)  # cap at 100


def determine_funnel_stage(prefs: dict, intent: str) -> str:
    """
    Determines funnel stage from conversation state.
    Pure Python rules — no AI needed.
    """
    if intent in ("agreement",):
        return "handshake"

    has_budget = bool(prefs.get("budget"))
    has_location = bool(prefs.get("location"))

    if has_budget and has_location:
        return "commitment"
    if has_budget or has_location:
        return "verification"

    return "awareness"
