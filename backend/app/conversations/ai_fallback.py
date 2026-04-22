import os
import logging
from google import genai  # <--- NEW import
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
        return "I'm sorry, I'm having trouble accessing my knowledge base."

    # Setup NEW Client
    client = genai.Client(api_key=api_key)

    company_name = getattr(profile, "company_name", "Est8Go Partner")
    about = getattr(profile, "company_about", "A professional real estate agency.")
    rules = getattr(profile, "payment_rules", "Contact us for details.")

    prompt = f"""
    You are a professional Nigerian Real Estate Consultant for {company_name}.
    
    KNOWLEDGE BASE:
    - About Us: {about}
    - Payment/Inspection Rules: {rules}
    
    USER QUESTION: "{user_text}"
    
    INSTRUCTIONS:
    - Answer using only the information provided above.
    - Be polite, professional, and use Nigerian property terms.
    - If you cannot find the answer in the knowledge base, say: "That's a great question. Let me alert a human consultant to provide you with the specific details on that."
    
    REPLY IN PLAIN TEXT:
    """

    try:
        # NEW generation method
        response = client.models.generate_content(
            model="gemini-1.5-flash", contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"❌ Gemini FAQ Error: {e}")
        return "I'll have a consultant get back to you shortly with those details."
