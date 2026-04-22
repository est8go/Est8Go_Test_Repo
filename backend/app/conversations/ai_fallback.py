import os
import logging
import google.generativeai as genai
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
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return "I'm having trouble accessing my knowledge base."

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    company_name = getattr(profile, "company_name", "Est8Go Partner")
    about = getattr(profile, "company_about", "A professional real estate agency.")
    rules = getattr(profile, "payment_rules", "Contact us for details.")

    prompt = f"Consultant for {company_name}. Knowledge: {about}. Rules: {rules}. Question: {user_text}. Reply politely in Nigerian terms."

    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"❌ FAQ Error: {e}")
        return "A consultant will provide you with those details shortly."
