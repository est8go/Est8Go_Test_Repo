import random


def get_executive_response(key: str, name: str, biz_name: str) -> str:
    """World-Class responses with high-end vocabulary and variety."""

    RESPONSES = {
        "intro": [
            f"Hello {name}, we're pleased you're here. I am the lead assistant for *{biz_name}*.",
            f"Greetings {name}. It is a pleasure to connect. I manage the digital portfolio for *{biz_name}*.",
            f"Hi {name}! Welcome to the *{biz_name}* executive portal. I'll be guiding your search today.",
            f"Hi {name}, thank you for reaching out to *{biz_name}*. My role is to help you discover secure and verified property opportunities with ease.",
            f"You're welcome, {name}. I’ll be assisting you throughout your search on behalf of *{biz_name}*.",
            f"Hello {name}. It's a pleasure connecting with you. I’m here to help you navigate trusted property options under *{biz_name}*.",
            f"Welcome aboard, {name}. At *{biz_name}*, we prioritize clarity, verification, and a stress free property experience.",
            f"Greetings {name}. I’ll be your dedicated assistant while we explore the most suitable verified listings for your needs.",
        ],
        "intent_location": [
            "To begin, are you interested in a **dry plot of land** for development, or a **finished apartment**? Also, which specific location appeals to you most?",
            "What is your primary focus today,**prime land** or a **move in ready home**? Please also share your preferred vicinity.",
            "Shall we look at **residential land** or **completed housing**? Please let me know which area in Abuja you are targeting.",
            "Kindly tell me the type of property you're interested in and the exact area you'd like us to prioritize.",
            "To narrow the best matches quickly, what property category and location are you currently considering?",
            "Are you primarily looking for investment property, residential living, or commercial use? Please include your preferred vicinity.",
            "What area would you like us to search in, and are you interested in land, apartments, duplexes, or commercial spaces?",
            "Please share your ideal location and preferred property type so I can prioritize the most relevant verified options.",
        ],
        "budget_nudge": [
            "Excellent, {name}. To filter our most exclusive matches, what is your intended **investment scope** for this location?",
            "I have noted your interest. {name}, what **budgetary range** are we working with to ensure a perfect fit?",
            "Perfect. What is your **capital ceiling** for this property? This helps me prioritize the best verified deals for you.",
            "To ensure I present only realistic and relevant options, what price range would you like me to focus on?",
            "What budget framework are we working with for this property search, {name}?",
            "Having a budget range helps me filter out unsuitable listings and focus on properties that truly match your expectations.",
            "Kindly indicate your preferred investment range so I can streamline the search effectively.",
            "What financial range feels comfortable for you at the moment? This helps improve listing accuracy considerably.",
        ],
        "resume_prompt": [
            "I see we were previously exploring options for you, {name}. Would you like to **continue** from where we left off, or shall we **start fresh**?",
            "Welcome back! Should I pull up your **previous preferences**, or are we looking for something **entirely new** today?",
            "Your earlier search history is still available, {name}. Would you like me to continue from there?",
            "Welcome again, {name}. I can either resume your previous search flow or help you start a new one entirely.",
            "I still have your previous property preferences on record. Should I continue from there or reset the search?",
            "Glad to see you back, {name}. Let me know whether you'd like continuity from your earlier search or a completely new direction.",
        ],
    }
    template = random.choice(RESPONSES.get(key, ["I am here to assist you, {name}."]))
    return template.format(name=name, biz_name=biz_name)
