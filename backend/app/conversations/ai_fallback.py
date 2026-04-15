# app/conversations/ai_fallback.py
# (This file handles answering company FAQs. It checks your DB cache first, meaning 90% of FAQ questions will cost $0.00 in LLM fees).

from __future__ import annotations
import re
import logging
from typing import Optional

from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from openai import OpenAI

from app.ai_cache.models import AiCache
from app.company_profiles.models import CompanyProfile

logger = logging.getLogger(__name__)
client = OpenAI()

FAQ_KEYWORDS = {
    "installment",
    "discount",
    "office",
    "policy",
    "pay",
    "plan",
    "fee",
    "where are you",
    "who are you",
}


# ---------------------------------------------------------
# CACHE HELPERS
# ---------------------------------------------------------
def _normalize(text: str) -> str:
    t = (text or "").strip().lower()
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"[^a-z0-9 ?!.,-]", "", t)
    return t[:240]


def cache_get(db: Session, tenant_id: int, text: str) -> Optional[str]:
    try:
        key = _normalize(text)
        row = (
            db.query(AiCache)
            .filter(
                AiCache.tenant_id == tenant_id,
                AiCache.state == "FAQ",
                AiCache.prompt_key == key,
            )
            .first()
        )
        return row.answer if row else None
    except OperationalError:
        return None


def cache_set(db: Session, tenant_id: int, text: str, answer: str) -> None:
    try:
        key = _normalize(text)
        row = AiCache(tenant_id=tenant_id, state="FAQ", prompt_key=key, answer=answer)
        db.add(row)
        db.commit()
    except (IntegrityError, OperationalError):
        db.rollback()


# ---------------------------------------------------------
# FAQ ROUTER & GENERATOR
# ---------------------------------------------------------
def is_company_faq(text: str) -> bool:
    """PYTHON ROUTER: Determines if we should trigger the LLM FAQ fallback."""
    text_lower = text.lower()
    return "?" in text_lower or any(kw in text_lower for kw in FAQ_KEYWORDS)


def answer_company_faq(
    db: Session, tenant_id: int, user_text: str, profile: CompanyProfile
) -> str:
    """Returns answers to company-specific questions (Checks Cache First)."""

    # 1. Check Cache to save LLM cost
    cached = cache_get(db, tenant_id, user_text)
    if cached:
        return cached

    # 2. Call LLM if not cached
    system_prompt = f"""
    You are a polite assistant for {profile.company_name or 'Our Firm'}.
    Answer the user's question using ONLY this company data:
    - About: {profile.short_about or 'Premium real estate services.'}
    - Office: {profile.office_address or 'Details shared upon request.'}
    - Areas: {profile.areas_covered or 'Strategic high-value locations.'}
    - Payment: {profile.payment_options or 'Flexible plans available.'}
    
    Rule 1: Keep it under 2 sentences.
    Rule 2: Do not invent rules or properties. If you don't know, say a consultant will clarify.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            temperature=0.3,
        )
        answer = response.choices[0].message.content.strip()

        # 3. Save to Cache for next time
        cache_set(db, tenant_id, user_text, answer)
        return answer

    except Exception as e:
        logger.error(f"FAQ LLM failed: {e}")
        return "That's a great question! I'll have a human consultant clarify that for you."
