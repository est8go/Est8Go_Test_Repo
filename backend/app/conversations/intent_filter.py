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
from difflib import get_close_matches
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
    "sure",
    "okay",
    "ok",
    "fine",
    "continue",
    "book inspection",
    "i'll take it",
    "i will take it",
    "send details",
    "share details",
    "i like it",
    "looks good",
    "sounds good",
    "works for me",
    "perfect",
    "great",
    "approved",
    "i'm ready",
    "im ready",
    "let's proceed",
    "lets proceed",
    "i can pay",
    "payment ready",
    "cash ready",
    "ready for inspection",
    "when can we inspect",
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
    "search again",
    "change search",
    "cancel search",
    "reset search",
    "another search",
    "new property search",
    "start a new one",
    "begin fresh",
    "complete new direction",
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
    "thank u",
    "okay",
    "ok",
    "interesting",
    "understood",
    "copy that",
    "received",
    "hmm",
    "hmmm",
    "lol",
    "lmao",
    "😂",
    "👍",
    "👌",
    "sounds nice",
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
    "occupied",
    "vacant",
    "still on market",
    "has it sold",
    "any buyer yet",
    "has someone paid",
    "still vacant",
    "is the land still there",
    "is the apartment still available",
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
    "budget range",
    "₦",
    "million",
    "billion",
    "rent",
    "annual rent",
    "service charge",
    "agency fee",
    "legal fee",
    "commission",
    "negotiable",
    "can owner reduce",
    "cheapest",
    "affordable",
    "luxury",
    "premium",
    "expensive",
    "too much",
    "too expensive",
    "within my budget",
    "budget friendly",
}

# Short location tokens that must match as whole words (not substrings of longer words)
# e.g. "ph" must not match "physical", "phone", "photograph"
LOCATION_FALSE_POSITIVES = {"ph"}

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
    "gwagwalada",
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

PROPERTY_TYPE_ALIASES = {
    # Apartment/flat variants and typos
    "flat":          "apartment",
    "flats":         "apartment",
    "appartment":    "apartment",
    "appartments":   "apartment",
    "aprtment":      "apartment",
    "studio":        "apartment",
    "condo":         "apartment",
    "condominium":   "apartment",
    "unit":          "apartment",
    # House variants
    "bungalow":      "house",
    "mansion":       "house",
    "duplex":        "house",
    "duplexes":      "house",
    "terrace":       "house",
    "townhouse":     "house",
    "semi detached": "house",
    "detached":      "house",
    "villa":         "house",
    # Land variants
    "plot":          "land",
    "plots":         "land",
    "parcel":        "land",
    "parcels":       "land",
    "acres":         "land",
    "hectare":       "land",
    "hectares":      "land",
    "sqm":           "land",
    "dry land":      "land",
    "dry plot":      "land",
}

COMPARISON_PATTERNS = [
    "compare",
    "difference between",
    "which is better",
    "tell me more about option",
    "more about number",
    "option 1",
    "option 2",
    "option 3",
    "first one",
    "second one",
    "third one",
    "the first one",
    "the second one",
    "the last one",
    "number 1",
    "number 2",
]

LOST_BUYER_PHRASES = {
    "so what do i do", "what do i do", "what now", "what should i do",
    "what can i do", "what next", "what do i do now", "help me", "help",
    "i don't know", "i dont know", "what are my options",
    "what options do i have", "so what happens now", "guide me",
    "what do you suggest", "suggest something", "any suggestions",
    "what do you recommend", "recommend something", "i'm confused",
    "im confused", "not sure what to do", "i need help",
    "what should i search", "how do i find",
}


def normalise_property_type(ptype: str) -> str:
    if not ptype:
        return ptype
    return PROPERTY_TYPE_ALIASES.get(
        ptype.lower().strip(), ptype.lower().strip()
    )


# Property reference pattern — catches "Est8Go property #24" from WhatsApp button clicks
PROPERTY_REF_PATTERN = re.compile(r"est8go property #(\d+)", re.IGNORECASE)


def detect_property_reference(text: str) -> Optional[int]:
    match = PROPERTY_REF_PATTERN.search(text or "")
    if match:
        return int(match.group(1))
    return None


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
    "too high": "objection_price",
    "price is too high": "objection_price",
    "price too high": "objection_price",
    "find something within my budget": "objection_budget_mismatch",
    "within my budget": "objection_budget_mismatch",
    "something cheaper": "objection_budget_mismatch",
    "more affordable": "objection_budget_mismatch",
    "cheaper options": "objection_budget_mismatch",
    "i cant afford": "objection_budget_mismatch",
    "i can't afford": "objection_budget_mismatch",
    "lower budget": "objection_budget_mismatch",
    "reduce my budget": "objection_budget_mismatch",
    "not my budget": "objection_budget_mismatch",
    "above my budget": "objection_budget_mismatch",
    "my wife": "objection_third_party",
    "my husband": "objection_third_party",
    "my partner": "objection_third_party",
    "show me others": "objection_more_options",
    "any other": "objection_more_options",
    "other options": "objection_more_options",
    "don't you have other": "objection_more_options",
    "show me more": "objection_more_options",
    "what else do you have": "objection_more_options",
    "any other properties": "objection_more_options",
    "more options": "objection_more_options",
    "see other properties": "objection_more_options",
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
        - "5m to 1b" → takes UPPER bound
        - "not more than 60m", "max 40m", "up to 80m" → ceiling
        - "fifteen million", "thirty m" → word numbers
        - "1.5b" → 1,500,000,000
        - Plain large numbers (7+ digits)
        - "I have 15" (bare number, millions implied when < 1000)
    """
    text = text.lower().replace(",", "").replace("₦", "").replace("naira", "").strip()

    # Word number map (Nigerian RE common ranges)
    WORD_MILLIONS = {
        "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
        "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
        "eighteen": 18, "nineteen": 19, "twenty": 20, "twenty five": 25,
        "thirty": 30, "thirty five": 35, "forty": 40, "forty five": 45,
        "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80,
        "ninety": 90, "hundred": 100, "one fifty": 150, "two hundred": 200,
    }

    # Ceiling phrases — extract the number after the phrase
    CEILING_PHRASES = [
        "not more than", "no more than", "maximum of", "maximum",
        "max of", "max", "at most", "up to", "within", "below",
        "less than", "under", "budget of", "my budget is",
        "i have", "i've got", "i got",
    ]

    # Check ceiling phrases first (most specific)
    for phrase in sorted(CEILING_PHRASES, key=len, reverse=True):
        if phrase in text:
            remainder = text[text.index(phrase) + len(phrase):].strip()
            val = extract_budget_from_text(remainder)
            if val:
                return val

    # Pattern: range like "5m to 1b" or "5m - 50m" → take upper bound
    range_pattern = r"(\d+\.?\d*)\s*(?:m\b|million)?\s*(?:to|-)\s*(\d+\.?\d*)\s*(?:b\b|billion|m\b|million)"
    range_match = re.search(range_pattern, text)
    if range_match:
        val1 = float(range_match.group(1))
        val2 = float(range_match.group(2))
        after_val2 = text[range_match.end(2):]
        if "b" in after_val2[:8] or "billion" in after_val2[:12]:
            return int(val2 * 1_000_000_000)
        else:
            return int(val2 * 1_000_000)

    # Pattern: number + k (thousands)
    k_match = re.search(r"(\d+\.?\d*)\s*k\b", text)
    if k_match:
        return int(float(k_match.group(1)) * 1_000)

    # Half / quarter million shorthand
    if "half million" in text or "half a million" in text:
        return 500_000
    if "quarter million" in text:
        return 250_000

    # Pattern: number + billion (including decimals like 1.5b)
    billion_pattern = r"(\d+\.?\d*)\s*(?:b\b|billion)"
    b_match = re.search(billion_pattern, text)
    if b_match:
        return int(float(b_match.group(1)) * 1_000_000_000)

    # Pattern: number + million/m (including decimals like 1.5m)
    million_pattern = r"(\d+\.?\d*)\s*(?:m\b|million)"
    m_match = re.search(million_pattern, text)
    if m_match:
        return int(float(m_match.group(1)) * 1_000_000)

    # Word number check (e.g. "fifteen million", "thirty m")
    for phrase in sorted(WORD_MILLIONS.keys(), key=len, reverse=True):
        if phrase in text:
            multiplier = 1_000_000
            remainder_after = text[text.index(phrase) + len(phrase):].strip()
            if remainder_after.startswith("b") or "billion" in remainder_after[:8]:
                multiplier = 1_000_000_000
            return int(WORD_MILLIONS[phrase] * multiplier)

    # Plain large number (7+ digits)
    plain_pattern = r"\b(\d{7,})\b"
    plain_match = re.search(plain_pattern, text)
    if plain_match:
        return int(plain_match.group(1))

    # Bare small number — implies millions if between 1 and 999
    # e.g. "I have 15" → 15M, "budget is 80" → 80M
    bare_match = re.search(r"\b(\d{1,3})\b", text)
    if bare_match:
        val = int(bare_match.group(1))
        if 1 <= val <= 999:
            return val * 1_000_000

    return None


def extract_location_from_text(
    text: str, dynamic_locations: list = None
) -> Optional[str]:
    """
    Extracts location — checks dynamic DB locations first, then static list.
    """
    text_lower = text.lower()

    # Layer 1: Dynamic locations from database (tenant-specific)
    if dynamic_locations:
        for loc in sorted(dynamic_locations, key=len, reverse=True):
            if loc and loc in text_lower:
                return loc

    # Layer 2: Static fallback — major Nigerian areas
    for loc in sorted(LOCATION_WORDS, key=len, reverse=True):
        if " " in loc and loc in text_lower:
            return loc

    words = set(text_lower.split())
    for loc in LOCATION_WORDS:
        if " " not in loc and loc not in {"area", "around", "near", "zone"}:
            if loc in LOCATION_FALSE_POSITIVES:
                # Only match when the token is a standalone word, not a substring
                if re.search(r"\b" + re.escape(loc) + r"\b", text_lower):
                    return loc
            elif loc in text_lower:
                return loc

    # Layer 3: Fuzzy fallback — catches misspellings
    fuzzy = fuzzy_location_match(text, dynamic_locations or [])
    if fuzzy:
        return fuzzy

    return None


def fuzzy_location_match(text: str, known_locations: list) -> str | None:
    """
    Catches misspellings like 'Guzap', 'Guzapee', 'Leki', 'Maitatma'.
    Uses Python stdlib difflib — zero cost.
    cutoff=0.82 balances precision vs recall for Nigerian place names.
    """
    words = text.lower().split()
    all_locations = list(set(known_locations + LOCATION_WORDS))

    # Try each word individually
    for word in words:
        if len(word) < 3:
            continue
        match = get_close_matches(word, all_locations, n=1, cutoff=0.82)
        if match:
            return match[0]

    # Try two-word combinations (e.g. "victoria iland")
    for i in range(len(words) - 1):
        phrase = words[i] + " " + words[i + 1]
        match = get_close_matches(phrase, all_locations, n=1, cutoff=0.85)
        if match:
            return match[0]

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
    # Second pass: check aliases (catches typos and extra synonyms)
    for alias, prop_type in sorted(
        PROPERTY_TYPE_ALIASES.items(), key=lambda x: -len(x[0])
    ):
        if alias in text_lower:
            return prop_type
    return None


def extract_intent_keywords(text: str, dynamic_locations: list = None) -> dict:
    result = {}
    budget = extract_budget_from_text(text)
    location = extract_location_from_text(text, dynamic_locations or [])
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


def classify_intent(
    text: str, current_prefs: dict = None, dynamic_locations: list = None
) -> IntentResult:
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
    # ── 0. PROPERTY PAGE LEAD — highest priority ────────
    _prop_id = detect_property_reference(text or "")
    if _prop_id:
        return IntentResult(
            intent="property_page_lead",
            confidence="high",
            extracted={"listing_id": _prop_id},
            response_key="property_page_lead",
            needs_gpt=False,
        )

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
    extracted = extract_intent_keywords(text_lower, dynamic_locations or [])

    # Merge with current prefs to get full picture
    merged = {**current_prefs, **{k: v for k, v in extracted.items() if v}}

    has_budget = bool(merged.get("budget"))
    has_location = bool(merged.get("location")) or bool(extracted.get("location"))
    has_prop_type = bool(merged.get("property_type")) or bool(
        extracted.get("property_type")
    )

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

    # ── 7.5. COMPARISON ─────────────────────────────────
    if any(pattern in text_lower for pattern in COMPARISON_PATTERNS):
        return IntentResult(
            intent="comparison",
            confidence="high",
            extracted={},
            response_key="comparison",
            needs_gpt=False,
        )

    # ── 7.8. LOST BUYER ─────────────────────────────────────
    if any(phrase in text_lower for phrase in LOST_BUYER_PHRASES) or text_lower in LOST_BUYER_PHRASES:
        return IntentResult(
            intent="lost_buyer",
            confidence="high",
            extracted={},
            response_key="lost_buyer_guidance",
            needs_gpt=False,
        )

    # ── 8. AGREEMENT ────────────────────────────────────
    is_agreement = (
        (len(text_clean.split()) <= 5 and any(w in words for w in AGREEMENT_WORDS))
        or text_lower.startswith("yes")
        or any(
            phrase in text_lower
            for phrase in [
                "schedule",
                "i would like",
                "i'd like",
                "i want to visit",
                "book inspection",
                "let's meet",
                "lets meet",
                "i am interested",
                "i'm interested",
                "yes please",
                "sure",
            ]
        )
    )
    if is_agreement:
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
