"""
EST8GO DOCUMENT TRUST ENGINE
==============================
Nigerian Real Estate Document Scoring System.

Document hierarchy is based on Nigerian land law and
the legal weight each document carries in a transaction.

Scoring Philosophy:
    - Strongest title documents score highest
    - Supporting documents add incremental trust
    - Combination bonuses reward complete documentation
    - Fraud indicators apply deductions

Document Tiers (Nigerian Land Law):
    TIER 1 — Statutory Title (Highest)
        Certificate of Occupancy (C of O)         → 35 pts
        Right of Occupancy (R of O)               → 35 pts
        Governor's Consent                        → 30 pts

    TIER 2 — Gazette / Excision (Community Land)
        Gazette                                   → 28 pts
        Excision                                  → 25 pts
        Approved Layout                           → 20 pts

    TIER 3 — Transactional Documents
        Deed of Assignment                        → 15 pts
        Deed of Conveyance                        → 15 pts
        Contract of Sale                          → 10 pts

    TIER 4 — Supporting / Survey
        Survey Plan (Registered)                  → 12 pts
        Site Plan                                 → 8 pts
        Building Plan Approval                    → 8 pts

    TIER 5 — Complementary Evidence
        Tax Clearance                             → 5 pts
        Receipts of Purchase                      → 5 pts
        Power of Attorney                         → 5 pts
        Probate / Letter of Administration        → 5 pts

    COMBINATION BONUSES:
        C of O + Survey + Deed                    → +10 pts
        Gazette + Survey + Deed                   → +8 pts
        Any Tier 1 + Governor's Consent           → +5 pts

    DEDUCTIONS (Fraud Signals):
        Unregistered survey                       → -10 pts
        Conflicting documents                     → -20 pts
        Missing vendor signature                  → -5 pts
"""

from dataclasses import dataclass, field
from typing import List

# ================================================================
# DOCUMENT REGISTRY
# ================================================================

DOCUMENT_SCORES = {
    # --- TIER 1: Statutory Title ---
    "c_of_o": {
        "label": "Certificate of Occupancy (C of O)",
        "short": "C of O",
        "score": 35,
        "tier": 1,
        "description": "Strongest title. Issued by State Government.",
        "required_for_emerald": True,
    },
    "r_of_o": {
        "label": "Right of Occupancy (R of O)",
        "short": "R of O",
        "score": 35,
        "tier": 1,
        "description": "Statutory right to occupy. Equal weight to C of O.",
        "required_for_emerald": True,
    },
    "governors_consent": {
        "label": "Governor's Consent",
        "short": "Gov. Consent",
        "score": 30,
        "tier": 1,
        "description": "Required for any land transaction in Nigeria.",
        "required_for_emerald": False,
    },
    # --- TIER 2: Gazette / Excision ---
    "gazette": {
        "label": "Gazette",
        "short": "Gazette",
        "score": 28,
        "tier": 2,
        "description": "Government publication confirming land excision.",
        "required_for_emerald": False,
    },
    "excision": {
        "label": "Excision Document",
        "short": "Excision",
        "score": 25,
        "tier": 2,
        "description": "Confirms land released from government acquisition.",
        "required_for_emerald": False,
    },
    "approved_layout": {
        "label": "Approved Layout",
        "short": "Layout",
        "score": 20,
        "tier": 2,
        "description": "Government-approved estate or land layout plan.",
        "required_for_emerald": False,
    },
    # --- TIER 3: Transactional Documents ---
    "deed_of_assignment": {
        "label": "Deed of Assignment",
        "short": "Deed",
        "score": 15,
        "tier": 3,
        "description": "Transfers ownership between parties.",
        "required_for_emerald": False,
    },
    "deed_of_conveyance": {
        "label": "Deed of Conveyance",
        "short": "Conveyance",
        "score": 15,
        "tier": 3,
        "description": "Transfers property under freehold.",
        "required_for_emerald": False,
    },
    "contract_of_sale": {
        "label": "Contract of Sale",
        "short": "Sale Contract",
        "score": 10,
        "tier": 3,
        "description": "Binding agreement between buyer and seller.",
        "required_for_emerald": False,
    },
    # --- TIER 4: Survey Documents ---
    "survey_plan": {
        "label": "Survey Plan (Registered)",
        "short": "Survey",
        "score": 12,
        "tier": 4,
        "description": "Registered survey defining property boundaries.",
        "required_for_emerald": True,
    },
    "site_plan": {
        "label": "Site Plan",
        "short": "Site Plan",
        "score": 8,
        "tier": 4,
        "description": "Architectural site layout of the property.",
        "required_for_emerald": False,
    },
    "building_plan_approval": {
        "label": "Building Plan Approval",
        "short": "Build Approval",
        "score": 8,
        "tier": 4,
        "description": "Local government approval for construction.",
        "required_for_emerald": False,
    },
    # --- TIER 5: Complementary ---
    "tax_clearance": {
        "label": "Tax Clearance Certificate",
        "short": "Tax Clearance",
        "score": 5,
        "tier": 5,
        "description": "Confirms seller has no outstanding tax liabilities.",
        "required_for_emerald": False,
    },
    "purchase_receipts": {
        "label": "Receipts of Purchase",
        "short": "Receipts",
        "score": 5,
        "tier": 5,
        "description": "Payment trail for the property transaction.",
        "required_for_emerald": False,
    },
    "power_of_attorney": {
        "label": "Power of Attorney",
        "short": "POA",
        "score": 5,
        "tier": 5,
        "description": "Authorization for agent to act on owner's behalf.",
        "required_for_emerald": False,
    },
    "probate": {
        "label": "Probate / Letter of Administration",
        "short": "Probate",
        "score": 5,
        "tier": 5,
        "description": "Confirms legal right to sell inherited property.",
        "required_for_emerald": False,
    },
}

# Maximum possible document score (before bonuses)
MAX_DOCUMENT_SCORE = 100

# Combination bonuses
COMBINATION_BONUSES = [
    {
        "docs": {"c_of_o", "survey_plan", "deed_of_assignment"},
        "bonus": 10,
        "label": "Full Title Package (C of O + Survey + Deed)",
    },
    {
        "docs": {"r_of_o", "survey_plan", "deed_of_assignment"},
        "bonus": 10,
        "label": "Full Title Package (R of O + Survey + Deed)",
    },
    {
        "docs": {"gazette", "survey_plan", "deed_of_assignment"},
        "bonus": 8,
        "label": "Gazette Package (Gazette + Survey + Deed)",
    },
    {
        "docs": {"excision", "survey_plan", "deed_of_assignment"},
        "bonus": 8,
        "label": "Excision Package (Excision + Survey + Deed)",
    },
    {
        "docs": {"c_of_o", "governors_consent"},
        "bonus": 5,
        "label": "Statutory Consent Combo",
    },
    {
        "docs": {"r_of_o", "governors_consent"},
        "bonus": 5,
        "label": "Statutory Consent Combo",
    },
]

# Deductions
DEDUCTIONS = {
    "unregistered_survey": {"score": -10, "label": "Unregistered Survey Plan"},
    "conflicting_documents": {"score": -20, "label": "Conflicting Documents Detected"},
    "missing_signature": {"score": -5, "label": "Missing Vendor Signature"},
    "expired_consent": {"score": -15, "label": "Expired Governor's Consent"},
}


# ================================================================
# DOCUMENT SCORE RESULT
# ================================================================


@dataclass
class DocumentScoreResult:
    raw_score: int  # score before cap
    final_score: int  # capped at 100
    grade: str  # Ungraded/Bronze/Silver/Gold/Emerald
    uploaded_docs: List[str]  # list of doc keys uploaded
    missing_emerald_docs: List[str]  # docs needed for Emerald
    bonuses_applied: List[str]  # combination bonuses earned
    deductions_applied: List[str]  # fraud deductions applied
    breakdown: dict  # per-document score breakdown
    upgrade_path: str  # what to do next to raise score


# ================================================================
# CORE SCORING FUNCTION
# ================================================================


def calculate_document_score(
    uploaded_doc_keys: List[str], deduction_flags: List[str] = None
) -> DocumentScoreResult:
    """
    Calculates the document trust score for a listing.

    Args:
        uploaded_doc_keys: List of document keys from DOCUMENT_SCORES
                           e.g. ['c_of_o', 'survey_plan', 'deed_of_assignment']
        deduction_flags:   List of deduction keys from DEDUCTIONS
                           e.g. ['unregistered_survey']

    Returns:
        DocumentScoreResult with full breakdown
    """
    if deduction_flags is None:
        deduction_flags = []

    uploaded_set = set(uploaded_doc_keys)
    breakdown = {}
    raw_score = 0
    bonuses_applied = []
    deductions_applied = []

    # --- BASE SCORES ---
    for doc_key in uploaded_doc_keys:
        if doc_key in DOCUMENT_SCORES:
            doc = DOCUMENT_SCORES[doc_key]
            pts = doc["score"]
            raw_score += pts
            breakdown[doc_key] = {
                "label": doc["short"],
                "score": pts,
                "tier": doc["tier"],
            }

    # --- COMBINATION BONUSES ---
    for combo in COMBINATION_BONUSES:
        if combo["docs"].issubset(uploaded_set):
            raw_score += combo["bonus"]
            bonuses_applied.append(f"+{combo['bonus']} pts: {combo['label']}")

    # --- DEDUCTIONS ---
    for flag in deduction_flags:
        if flag in DEDUCTIONS:
            ded = DEDUCTIONS[flag]
            raw_score += ded["score"]  # negative value
            deductions_applied.append(f"{ded['score']} pts: {ded['label']}")

    # --- CAP AT 100 ---
    final_score = max(0, min(raw_score, MAX_DOCUMENT_SCORE))

    # --- GRADE ---
    grade = _get_grade(final_score, uploaded_set)

    # --- MISSING EMERALD DOCS ---
    required = {k for k, v in DOCUMENT_SCORES.items() if v.get("required_for_emerald")}
    missing_emerald = list(required - uploaded_set)

    # --- UPGRADE PATH ---
    upgrade_path = _build_upgrade_path(final_score, uploaded_set, missing_emerald)

    return DocumentScoreResult(
        raw_score=raw_score,
        final_score=final_score,
        grade=grade,
        uploaded_docs=uploaded_doc_keys,
        missing_emerald_docs=missing_emerald,
        bonuses_applied=bonuses_applied,
        deductions_applied=deductions_applied,
        breakdown=breakdown,
        upgrade_path=upgrade_path,
    )


# ================================================================
# HELPERS
# ================================================================


def _get_grade(score: int, uploaded_set: set) -> str:
    """
    Grade is based on score AND document completeness.
    Emerald requires: score >= 85 AND all required docs uploaded.
    """
    required = {k for k, v in DOCUMENT_SCORES.items() if v.get("required_for_emerald")}
    has_required = required.issubset(uploaded_set)

    if score >= 85 and has_required:
        return "Emerald"
    elif score >= 75:
        return "Gold"
    elif score >= 50:
        return "Silver"
    elif score >= 25:
        return "Bronze"
    else:
        return "Ungraded"


def _build_upgrade_path(
    score: int, uploaded_set: set, missing_emerald: List[str]
) -> str:
    """Builds a human-readable upgrade instruction for the Realtor portal."""

    if score >= 85 and not missing_emerald:
        return "🟢 Emerald status achieved. No action required."

    steps = []

    if missing_emerald:
        for doc_key in missing_emerald:
            doc = DOCUMENT_SCORES.get(doc_key, {})
            label = doc.get("label", doc_key)
            pts = doc.get("score", 0)
            steps.append(f"Upload {label} to gain +{pts} pts")

    # Suggest highest-value missing doc from any tier
    all_missing = set(DOCUMENT_SCORES.keys()) - uploaded_set
    if all_missing:
        best = max(all_missing, key=lambda k: DOCUMENT_SCORES[k]["score"])
        best_doc = DOCUMENT_SCORES[best]
        if best not in missing_emerald:
            steps.append(
                f"Upload {best_doc['label']} to gain " f"+{best_doc['score']} pts"
            )

    pts_needed = 85 - score
    if pts_needed > 0:
        steps.insert(0, f"Need {pts_needed} more points for Emerald status.")

    return " → ".join(steps) if steps else "Continue uploading documents."


# ================================================================
# COMBINED TRUST SCORE (GPS + AI + DOCUMENTS)
# ================================================================


def calculate_full_trust_score(
    gps_verified: bool,
    gps_expired: bool,
    gps_location_match: bool,
    gps_photo_match: bool,
    ai_verified: bool,
    document_keys: List[str],
    deduction_flags: List[str] = None,
    listing=None,
) -> dict:
    """
    Full trust breakdown for the portal and Kora.

    The NUMBER comes from trust_engine.calculate_confidence_score —
    the single implementation. This function only assembles the
    per-pillar breakdown around it.

    It used to compute its own total and disagreed with that scorer on
    every pillar: GPS graduated 15/10/5 against a flat 30, documents
    rescaled to 40 rather than truncated, witnesses at 2 points rather
    than 5, and a different grade ladder. The same listing came out
    90/emerald there and 73/Silver here. Because this path runs on
    photo upload (via the AI audit) and writes trust_score, a listing's
    grade depended on which action the agency performed last.

    gps_photo_match is accepted for signature compatibility and
    reported in the breakdown, but no code has ever written that
    column, so it is always False.
    """
    from app.services.trust_engine import (
        calculate_confidence_score,
        grade_for_score,
    )

    doc_result = calculate_document_score(document_keys, deduction_flags)

    # The stored document_score is on a 0-100 scale; the trust pillar
    # truncates it at 50. Build a stand-in when no listing row is given.
    if listing is not None:
        subject = listing
    else:
        class _Subject:
            latitude = 1.0 if gps_verified else None
            longitude = 1.0 if gps_verified else None
            gps_verified_at = True if gps_verified else None
            ai_verified_real = ai_verified
            document_score = doc_result.final_score
        subject = _Subject()

    final_score = calculate_confidence_score(subject)
    grade = grade_for_score(final_score)

    gps_score = 30 if (
        getattr(subject, "latitude", None)
        and getattr(subject, "longitude", None)
        and getattr(subject, "gps_verified_at", None)
    ) else 0
    ai_score = 20 if getattr(subject, "ai_verified_real", False) else 0
    doc_scaled = min(getattr(subject, "document_score", 0) or 0, 50)

    breakdown = {
        "gps": {
            "score": gps_score,
            "max": 30,
            "status": ["coordinates_captured"] if gps_score else [],
            "expired": gps_expired,
            "location_match": gps_location_match,
            "photo_match": gps_photo_match,
        },
        "ai_vision": {
            "score": ai_score,
            "max": 20,
            "status": "passed" if ai_score else "not audited",
        },
        "documents": {
            "score": doc_scaled,
            "max": 50,
            "raw_doc_score": doc_result.final_score,
            "grade": doc_result.grade,
            "uploaded": doc_result.uploaded_docs,
            "bonuses": doc_result.bonuses_applied,
            "deductions": doc_result.deductions_applied,
            "upgrade_path": doc_result.upgrade_path,
        },
    }

    return {
        "total_score": final_score,
        "grade": grade,
        "breakdown": breakdown,
        "emerald_ready": grade == "emerald",
        "upgrade_path": doc_result.upgrade_path,
    }
