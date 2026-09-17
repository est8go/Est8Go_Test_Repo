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
        "phone",
        "about",
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

    # We extract these and USE them in the prompt below (clearing the warnings)
    c_name = getattr(profile, "company_name", "Est8Go Partner")
    c_about = getattr(profile, "company_about", "A professional real estate agency.")
    c_rules = getattr(profile, "payment_rules", "Contact us for details.")
    c_phone = getattr(profile, "phone_whatsapp", "our official line")

    # THE REFINED PROMPT SOCKET
    prompt = f"""
    SYSTEM: You are the Senior Consultant for {c_name}.
    STRICT RULE: Do NOT write emails/letters. No "Dear Stakeholders".
    STRICT RULE: Answer in 2-3 SHORT sentences.
    
    OUR PROFILE: {c_about}
    OUR RULES: {c_rules}
    CONTACT: {c_phone}
    
    USER QUESTION: "{user_text}"
    
    INSTRUCTIONS:
    1. Use the info above to answer directly.
    2. Use a {profile.tone} tone.
    3. If emoji_mode is True, use 1-2 emojis.
    
    REPLY AS A WHATSAPP CHAT MESSAGE:
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"❌ OpenAI FAQ Error: {e}")
        return f"Thanks for asking! You can reach {c_name} directly at {c_phone} for full details."

    except Exception as e:
        logger.error(f"❌ OpenAI FAQ Error: {e}")
        return "I'll have a consultant get back to you shortly with those details."
