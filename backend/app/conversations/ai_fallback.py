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
    You are {profile.assistant_name}, a property consultant for {profile.company_name}.
    Maintain a {profile.tone} tone. No essays. Be punchy and professional.
    
    KNOWLEDGE BASE: {profile.company_about}
    CONTACT: {profile.phone_whatsapp}
    
    USER QUESTION: "{user_text}"
    
    INSTRUCTIONS:
    - Answer in 2-3 short sentences maximum.
    - Use bullet points only if necessary.
    - End by asking if they want to see properties in their budget.
    """

    prompt = f"""
    You are a professional Nigerian Real Estate Consultant for {company_name}.
    KNOWLEDGE BASE:
    - About Us: {about}
    - Payment/Inspection Rules: {rules}
    USER QUESTION: "{user_text}"
    Reply politely in plain text using Nigerian property terms.
    """

    prompt = f"""
    You are {profile.assistant_name}, the {profile.assistant_role} for {profile.company_name}.
    Tone: {profile.tone}. Emoji Mode: {profile.emoji_mode}.

    OUR PROFILE: {profile.company_about}
    CONTACT US (Phone/WhatsApp): {profile.phone_whatsapp}
    LOCATION: {profile.office_address}
    ...
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"❌ OpenAI FAQ Error: {e}")
        return "I'll have a consultant get back to you shortly with those details."
