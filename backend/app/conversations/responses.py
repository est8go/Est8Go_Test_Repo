import random


def get_executive_response(key: str, name: str, biz_name: str) -> str:
    """World-Class responses with high-end vocabulary and variety."""

    RESPONSES = {
        "intro": [
            f"Hello {name}, we're pleased you're here. I am the lead assistant for *{biz_name}*.",
            f"Greetings {name}. It is a pleasure to connect. I manage the digital portfolio for *{biz_name}*.",
            f"Hi {name}! Welcome to the *{biz_name}* executive portal. I'll be guiding your search today.",
        ],
        "intent_location": [
            "To begin, are you interested in a **dry plot of land** for development, or a **finished apartment**? Also, which specific location appeals to you most?",
            "What is your primary focus today,**prime land** or a **move in ready home**? Please also share your preferred vicinity.",
            "Shall we look at **residential land** or **completed housing**? Please let me know which area in Abuja you are targeting.",
        ],
        "budget_nudge": [
            "Excellent, {name}. To filter our most exclusive matches, what is your intended **investment scope** for this location?",
            "I have noted your interest. {name}, what **budgetary range** are we working with to ensure a perfect fit?",
            "Perfect. What is your **capital ceiling** for this property? This helps me prioritize the best verified deals for you.",
        ],
        "resume_prompt": [
            "I see we were previously exploring options for you, {name}. Would you like to **continue** from where we left off, or shall we **start fresh**?",
            "Welcome back! Should I pull up your **previous preferences**, or are we looking for something **entirely new** today?",
        ],
    }
    template = random.choice(RESPONSES.get(key, ["I am here to assist you, {name}."]))
    return template.format(name=name, biz_name=biz_name)
