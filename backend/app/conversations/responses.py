import random


def get_response(key: str, name: str, tenant_profile: dict) -> str:
    """
    Generates a branded, persona-aware response for the user.

    Args:
        key: The type of message (e.g., 'greeting', 'nudge_location')
        name: The User's first name
        tenant_profile: Dict containing 'business_name', 'tone', and 'emoji'
    """

    biz_name = tenant_profile.get("business_name", "your realtor")
    tone = tenant_profile.get("tone", "friendly")
    emoji = tenant_profile.get("emoji", "🏠")

    # Define the response library
    # We use lists [] so the bot doesn't say the same thing every time (Human feel)

    RESPONSES = {
        "greeting": (
            [
                f"Hi {name} {emoji}, I'm the assistant for *{biz_name}*. How can I help you find the right property today?",
                f"Hello {name}! You're speaking with the *{biz_name}* Assistant. Ready to explore some verified listings? 😊",
            ]
            if tone == "friendly"
            else [
                f"Good day {name}. This is the automated assistant for *{biz_name}*. How may we assist your property search today?",
                f"Greetings {name}. Welcome to the *{biz_name}* digital portal. Please let us know what you are looking for.",
            ]
        ),
        "nudge_location": [
            f"Which area are you considering for your next investment with *{biz_name}*?",
            f"To help *{biz_name}* find the best deal, {name}, which location do you prefer? 📍",
        ],
        "nudge_budget": [
            f"What budget range are we working with for this *{biz_name}* property?",
            f"Could you share your budget? It helps *{biz_name}* filter out the noise for you. 💰",
        ],
        "inspection_confirm": [
            f"Excellent choice, {name}! I've sent your request to the *{biz_name}* team. They will contact you shortly to confirm the time. 👍🏽",
        ],
        "filler": [
            f"I’m with you {name} 👍🏽 — just give me a bit more detail so *{biz_name}* can serve you better.",
            f"Alright, help *{biz_name}* understand your requirements a bit more.",
        ],
    }

    # If the key is not found, provide a safe fallback
    options = RESPONSES.get(
        key,
        [f"Understood. *{biz_name}* is here to help you find the perfect property!"],
    )

    return random.choice(options)
