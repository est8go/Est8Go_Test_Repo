"""
EST8GO KORA OBJECTION ENGINE
==============================
12 Standard Nigerian Real Estate Objections mapped to
executive, consultative closing responses.

Rules-First: Pure Python — zero GPT cost.
Every objection advances the sale, never just answers it.

Philosophy:
    - Never be defensive
    - Reframe every objection as a reason to act NOW
    - Always end with a forward-moving question
    - Maintain the executive, consultative tone
"""

import random

# ================================================================
# THE 12 OBJECTION RESPONSES
# ================================================================

OBJECTION_RESPONSES = {
    # --- 1. STALLING ("let me think", "I'll get back to you") ---
    "objection_stalling": [
        (
            "I completely understand, {name}. The best decisions deserve careful thought. 🧠\n\n"
            "What I can tell you is that *{biz_name}* operates on verified inventory "
            "these are not listings that sit available indefinitely. "
            "Properties at this trust grade move quickly once the right buyer sees them.\n\n"
            "What specific aspect would you like me to clarify before you decide?"
        ),
        (
            "Of course, {name}  a property decision is never trivial. 🏠\n\n"
            "While you think it over, let me share one fact: this listing carries an "
            "*{trust_grade} Trust Score,*  GPS verified, AI-audited, and document checked. "
            "That combination is rare in this market.\n\n"
            "Is there anything about the title documents or location you'd like confirmed first?"
        ),
    ],
    # --- 2. MEDIA REQUEST ("send me the video", "WhatsApp video") ---
    "objection_media": [
        (
            "Absolutely, {name}! 📸\n\n"
            "Our verified property showcase includes high resolution photos and a GPS audit trail "
            " all available at the link I shared above.\n\n"
            "For a full video walkthrough, that is arranged during a *scheduled site inspection* "
            "with our lead agent ensuring you see the property live and unedited.\n\n"
            "Would you like me to schedule that inspection for you? Just share a preferred date."
        ),
        (
            "Great idea, {name}. 🎥\n\n"
            "I want to be transparent, pre-recorded videos can be manipulated. "
            "At *{biz_name}*, we go further: a *live agent walkthrough* at the physical site, "
            "so you see every corner in real time.\n\n"
            "That is our Truth Standard. Shall I connect you with the site agent today?"
        ),
    ],
    # --- 3. AVAILABILITY ("is it still available?", "still there?") ---
    "objection_availability": [
        (
            "✅ Confirmed, {name} this property is *active and verified* in our vault.\n\n"
            "At *{biz_name}*, listings are only visible when they have passed our GPS "
            "and AI audit checks. Anything you see here is live.\n\n"
            "Would you like to schedule a physical inspection before someone else does?"
        ),
        (
            "Yes, {name} still available and freshly verified. 🔒\n\n"
            "Our system automatically removes any property the moment it is sold or "
            "taken off market. You are looking at a live, active listing.\n\n"
            "Shall I lock in a site visit for you?"
        ),
    ],
    # --- 4. PRICE NEGOTIATION ("last price?", "can owner reduce?") ---
    "objection_price": [
        (
            "A fair question, {name}. 💰\n\n"
            "I will be honest with you, properties with a *{trust_grade} Trust Score* "
            "rarely drop in price because the documentation and verification work "
            "has already been done for you. You are paying for certainty, not just land.\n\n"
            "That said, our agent can discuss *flexible payment structures* directly with you. "
            "Would you like me to arrange that conversation?"
        ),
        (
            "I hear you, {name}. Let me be direct. 🤝\n\n"
            "The price reflects a GPS-verified, AI-audited, fully documented property. "
            "In a market full of stories and fake listings, that premium is the difference "
            "between owning property and owning a problem.\n\n"
            "Our agent is available to discuss terms. Shall I connect you?"
        ),
    ],
    # --- 5. BUDGET MISMATCH ("above my budget", "not my budget") ---
    "objection_budget_mismatch": [
        (
            "Understood, {name}  budget alignment is everything. 📊\n\n"
            "Let me search our vault for options within your range. "
            "Our network covers multiple price points, all verified to the same Truth Standard.\n\n"
            "What is your actual comfortable range? I will pull the best matches immediately."
        ),
        (
            "No problem at all, {name}. 🔄\n\n"
            "We have verified properties across a wide price spectrum. "
            "Tell me your realistic budget and I will filter only the options that fit "
            "no wasted time, no pressure.\n\n"
            "What figure works best for you?"
        ),
    ],
    # --- 6. THIRD PARTY ("my wife", "my husband", "my partner") ---
    "objection_third_party": [
        (
            "That is wise, {name} major decisions belong to the whole family. 👨‍👩‍👧\n\n"
            "Here is what I suggest: share the verified property link with them directly. "
            "Everything they need: photos, GPS audit, trust score, and documents "
            "is in one place. No back and forth required.\n\n"
            "Would you like me to prepare a summary they can review at their convenience?"
        ),
        (
            "Absolutely the right approach, {name}. 🤝\n\n"
            "I can prepare a *Verification Summary* for this property "
            "a clean, shareable document showing the GPS proof, AI audit result, "
            "and title documents. Perfect for a joint review.\n\n"
            "Shall I put that together for you now?"
        ),
    ],
    # --- 7. MORE OPTIONS ("show me others", "any other options?") ---
    "objection_more_options": [
        (
            "Of course, {name}! Variety is important. 🔍\n\n"
            "I have pulled our full verified collection matching your criteria. "
            "Every option in our boutique carries the same Truth Standard "
            "GPS-verified, AI audited, and document-checked.\n\n"
            "Tap the boutique link above to browse all available matches. "
            "Which one catches your eye?"
        ),
        (
            "Great — let me expand your options, {name}. 📋\n\n"
            "Our vault has additional verified matches in your area. "
            "I will not waste your time with unverified listings "
            "everything I show you has passed our full audit.\n\n"
            "Take a look at the boutique link. Any of those work for you?"
        ),
    ],
    # --- 8. COLD DISENGAGEMENT ("not interested", "forget it") ---
    "objection_cold": [
        (
            "Understood completely, {name}. No pressure at all. 🙏\n\n"
            "If your property needs change, whether buying, selling, or investing "
            "*{biz_name}* will always have verified options waiting for you.\n\n"
            "Is there anything specific that changed your mind? "
            "Your feedback helps us serve you better."
        ),
        (
            "That is perfectly fine, {name}. 👍\n\n"
            "The market moves fast and so do preferences. "
            "Whenever you are ready to explore again, our vault will be here  "
            "fully verified and updated.\n\n"
            "Is there anything I can improve or clarify before you go?"
        ),
    ],
    # --- 9. NIGERIAN CASUAL ("abeg", "e don do") ---
    "objection_nigerian_casual": [
        (
            "Ha {name}, I hear you! 😄\n\n"
            "But seriously, this one na real deal. GPS verified, documents clean, "
            "AI-checked. No story, no drama.\n\n"
            "Just say the word and I will connect you with the agent directly. "
            "No time wasting. 🤝"
        ),
        (
            "Lol {name}, I feel you! 😂\n\n"
            "But this property no be one of those fake listings. "
            "Everything checked and confirmed, coordinates, photos, papers.\n\n"
            "You want make I send you the verification details? Na facts, I promise. ✅"
        ),
    ],
    # --- 10. INSPECTION OBJECTION ("I can't come now", "too far") ---
    "objection_inspection": [
        (
            "No problem at all, {name}. 📅\n\n"
            "Our site inspections are flexible, weekdays, weekends, early morning. "
            "We work around your schedule, not the other way around.\n\n"
            "What day and time works best for you?"
        ),
        (
            "I understand, {name}  we will make it convenient for you. 🚗\n\n"
            "Our agent can also arrange a *live video walkthrough* as a first step, "
            "so you can preview the property remotely before committing to a visit.\n\n"
            "Would that work for you?"
        ),
    ],
    # --- 11. TRUST / LEGITIMACY ("how do I know it's real?") ---
    "objection_trust": [
        (
            "That is exactly the right question to ask, {name}. 🔍\n\n"
            "At *{biz_name}*, every listing passes three independent checks:\n\n"
            "📍 GPS Verification: physical site location confirmed\n"
            "🤖 AI Vision Audit: photos scanned for CGI or stolen images\n"
            "📄 Document Check: title documents verified and scored\n\n"
            "You can see the full audit trail at the property link. "
            "This is not a promise, it is mathematical proof."
        ),
    ],
    # --- 12. AGENT QUALITY ("is the agent reliable?") ---
    "objection_agent": [
        (
            "Great question, {name}. 🏆\n\n"
            "Every agent on the *{biz_name}* platform carries a *Trust Passport*  "
            "a verified record of their transactions, inspection history, and client ratings.\n\n"
            "You are not dealing with an unknown, you are dealing with a verified professional. "
            "Shall I share their profile with you?"
        ),
    ],
}


# ================================================================
# RESPONSE GETTER
# ================================================================


def get_objection_response(
    response_key: str, name: str, biz_name: str, trust_grade: str = "Verified"
) -> str:
    """
    Returns a randomised executive objection response.

    Args:
        response_key: The objection key from OBJECTION_RESPONSES
        name:         Buyer's first name
        biz_name:     Tenant's business name
        trust_grade:  The listing's trust grade (Emerald/Gold/Silver/Bronze/Verified)

    Returns:
        Formatted response string
    """
    templates = OBJECTION_RESPONSES.get(
        response_key,
        [
            "I understand your concern, {name}. Could you share a bit more "
            "so I can assist you better? 🙏"
        ],
    )

    template = random.choice(templates)
    return template.format(name=name, biz_name=biz_name, trust_grade=trust_grade)


# ================================================================
# MEDIA REDIRECT BUILDER
# ================================================================


def build_media_redirect(name: str, biz_name: str, showroom_link: str) -> str:
    """
    Specific media request handler that includes the showroom link.
    Called when buyer asks for video/photos.
    """
    return (
        f"Absolutely, {name}! 📸\n\n"
        f"Tap below to view the full verified photo gallery and GPS audit trail:\n"
        f"{showroom_link}\n\n"
        f"For a *live video walkthrough*, our agent visits the site with you in person — "
        f"so what you see is exactly what you get.\n\n"
        f"Shall I schedule that with *{biz_name}*'s lead agent? Just share a preferred date. 📅"
    )
