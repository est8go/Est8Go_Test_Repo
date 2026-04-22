import os
import logging
from openai import OpenAI
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def is_company_faq(text: str) -> bool:
    keywords = [
        "who are you",
        "office",
        "location",
        "pay",
        "bank",
        "address",
        "call",
        "phone" "about",
        "where is",
        "account",
        "transfer",
        "installment",
        "company",
        "firm",
    ]
    return any(k in text.lower() for k in keywords)


def answer_company_faq(db: Session, tenant_id: int, user_text: str, profile) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "I'm having trouble accessing my knowledge base."

    client = OpenAI(api_key=api_key)

    company_name = getattr(profile, "company_name", "Est8Go Partner")
    about = getattr(profile, "company_about", "A professional real estate agency.")
    rules = getattr(profile, "payment_rules", "Contact us for details.")

    prompt = f"""
    You are a professional Nigerian Real Estate Consultant for {company_name}.
    KNOWLEDGE BASE:
    - About Us: {about}
    - Payment/Inspection Rules: {rules}
    USER QUESTION: "{user_text}"
    Reply politely in plain text using Nigerian property terms.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"❌ OpenAI FAQ Error: {e}")
        return "I'll have a consultant get back to you shortly with those details."
