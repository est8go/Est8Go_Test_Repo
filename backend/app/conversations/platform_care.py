# app/conversations/platform_care.py
"""
Est8Go Platform Customer Care Flow
=====================================
World-class sales consultant tone.
Warm, confident, persuasive, Nigerian market savvy.
Turns every enquiry into a relationship.
"""
import random
import re


# ================================================================
# WELCOME — Multiple variants for variety
# ================================================================

WELCOME_VARIANTS = [
    (
        "Hello {name}! 👋\n\n"
        "Welcome to *Est8Go* — Nigeria's property "
        "trust infrastructure.\n\n"
        "I'm Kora. My job is simple: before you "
        "spend a single naira on property, I make "
        "sure what you're buying is exactly what "
        "you're being shown.\n\n"
        "GPS confirmed. Smart-verified. Documents "
        "checked. No surprises. 🛡️\n\n"
        "How can I help you today?\n\n"
        "1️⃣ Find a verified property\n"
        "2️⃣ Find a trusted agency near me\n"
        "3️⃣ How does verification work?\n"
        "4️⃣ Grow your business with Est8Go\n"
        "5️⃣ Report a suspicious listing\n\n"
        "Reply with a number or tell me "
        "what's on your mind."
    ),
    (
        "Hi {name}, good to have you here. 🤝\n\n"
        "You've reached *Est8Go* — where every "
        "listing is verified before it reaches you.\n\n"
        "In a market where 1 in 3 listings is fake, "
        "we built the infrastructure that tells "
        "you the truth.\n\n"
        "What can I help you with?\n\n"
        "1️⃣ Find a verified property\n"
        "2️⃣ Find a verified agency near you\n"
        "3️⃣ Understand how verification works\n"
        "4️⃣ Grow your business with Est8Go\n"
        "5️⃣ Report a suspicious listing\n\n"
        "Reply 1–5 or simply tell me what you need."
    ),
    (
        "Welcome, {name}! 🏡\n\n"
        "You've reached *Est8Go* — Nigeria's most "
        "trusted property verification platform.\n\n"
        "Whether you're buying land, searching for "
        "an apartment, or looking for an agent you "
        "can actually trust — you're in the "
        "right place.\n\n"
        "1️⃣ Find a verified property\n"
        "2️⃣ Find a verified agency near you\n"
        "3️⃣ How our verification works\n"
        "4️⃣ Grow your business with Est8Go\n"
        "5️⃣ Report a suspicious listing\n\n"
        "What would you like to do?"
    ),
]


def get_welcome(name: str) -> str:
    return random.choice(WELCOME_VARIANTS).format(name=name)


# ================================================================
# MENU REPROMPT — When user sends something unclear
# ================================================================

MENU_REPROMPT_VARIANTS = [
    (
        "I want to make sure I give you exactly the right help, {name}. 👇\n\n"
        "Please pick one:\n\n"
        "1️⃣ Find a verified property\n"
        "2️⃣ Find a verified agency near you\n"
        "3️⃣ How verification works\n"
        "4️⃣ Grow your business with Est8Go\n"
        "5️⃣ Report a suspicious listing"
    ),
    (
        "No worries, {name} — let me point you in the right direction.\n\n"
        "1️⃣ Find a verified property\n"
        "2️⃣ Find a verified agency near you\n"
        "3️⃣ How verification works\n"
        "4️⃣ Grow your business with Est8Go\n"
        "5️⃣ Report a suspicious listing\n\n"
        "Which one is closest to what you need?"
    ),
]


def get_reprompt(name: str) -> str:
    return random.choice(MENU_REPROMPT_VARIANTS).format(name=name)


# ================================================================
# OPTION 1 — Find a verified property
# ================================================================

OPTION_1_VARIANTS = [
    (
        "Perfect, {name}. Let's find you "
        "something verified. 🎯\n\n"
        "Three quick questions:\n\n"
        "*Property type?*\n"
        "Land · House · Apartment\n\n"
        "*Which city or area?*\n"
        "Abuja · Lagos · Port Harcourt...\n\n"
        "*Budget range?*\n"
        "e.g. ₦50M or ₦20M–₦80M\n\n"
        "Start with the property type. 🏠"
    ),
    (
        "Good choice, {name}. 💪\n\n"
        "Every property I show you has been "
        "physically visited, GPS-confirmed, "
        "and document-checked. No stories.\n\n"
        "Tell me:\n\n"
        "• *Type?* Land, House, or Apartment\n"
        "• *Area?* Be as specific as you can\n"
        "• *Budget?* Even a rough range helps\n\n"
        "What are you looking for? 👇"
    ),
    (
        "Let's find you something worth "
        "every naira, {name}. 🏡\n\n"
        "I need just three things:\n\n"
        "🏠 *Type* — Land, House or Apartment?\n"
        "📍 *Location* — Which area?\n"
        "💰 *Budget* — What's your range?\n\n"
        "Start wherever feels comfortable."
    ),
]


def get_option_1(name: str) -> str:
    return random.choice(OPTION_1_VARIANTS).format(name=name)


# ================================================================
# OPTION 1 SEARCH REDIRECT — After user gives preferences
# ================================================================

SEARCH_REDIRECT_VARIANTS = [
    (
        "Got it, {name}. 🎯\n\n"
        "I'm connecting you with a verified "
        "Est8Go partner agency that specialises "
        "in exactly that.\n\n"
        "Browse live verified listings now:\n"
        "👉 *est8go.com*\n\n"
        "Every listing shows its full "
        "trust audit trail — GPS, photo analysis, "
        "documents, witnesses.\n\n"
        "A verified agent will reach out shortly."
    ),
    (
        "Understood, {name}. "
        "Let me get the right people on this. 🤝\n\n"
        "I'm flagging your requirements to our "
        "verified agency network now.\n\n"
        "You can also view current listings at:\n"
        "👉 *est8go.com*\n\n"
        "The higher the Trust Score on a listing, "
        "the safer the investment. "
        "Expect a call from a verified agent soon."
    ),
]


def get_search_redirect(name: str) -> str:
    return random.choice(SEARCH_REDIRECT_VARIANTS).format(name=name)


# ================================================================
# OPTION 2 — Find a verified agency
# ================================================================

OPTION_2_VARIANTS = [
    (
        "Smart thinking, {name}. "
        "The right agent changes everything. 🤝\n\n"
        "Est8Go only works with agencies that have "
        "passed our verification standards — "
        "background checked, document verified, "
        "and property quality audited.\n\n"
        "Which city are you looking in?\n\n"
        "We have verified partners in:\n"
        "📍 Abuja · Lagos · Port Harcourt "
        "· Enugu · Ibadan\n\n"
        "Tell me your city and I'll connect "
        "you directly."
    ),
    (
        "The agent you choose determines "
        "everything, {name}. 💯\n\n"
        "Our verified agencies carry the "
        "Est8Go seal — which means they've "
        "been audited, not just registered.\n\n"
        "Where are you looking to buy?\n\n"
        "📍 *Abuja · Lagos · Port Harcourt "
        "· Enugu · Ibadan and more*\n\n"
        "Share your city and I'll make "
        "the introduction."
    ),
]


def get_option_2(name: str) -> str:
    return random.choice(OPTION_2_VARIANTS).format(name=name)


# ================================================================
# OPTION 2 — Agency found response
# ================================================================

def get_agency_found(name: str, location: str) -> str:
    return (
        f"Perfect, {name}! 🎯\n\n"
        f"Let me pull up our verified agency partners in *{location}* for you.\n\n"
        f"You can browse all verified agencies and their listings at:\n"
        f"🔗 *est8go.com*\n\n"
        f"Each agency on our platform displays a *Verified Partner* badge "
        f"and a full trust audit trail — so you know exactly who you're "
        f"dealing with before you pick up the phone. 📱\n\n"
        f"Would you also like me to help you search for a specific "
        f"property in {location}? I can do that for you right now. 🏠"
    )


# ================================================================
# OPTION 3 — How verification works
# ================================================================

OPTION_3_VARIANTS = [
    (
        "Great question, {name}. "
        "This is what makes Est8Go different. 🛡️\n\n"
        "Before any listing goes live, "
        "it goes through four checks:\n\n"
        "📍 *GPS Verification*\n"
        "We visit the physical location. "
        "Coordinates locked. Property confirmed.\n\n"
        "🔍 *Photo Intelligence Audit*\n"
        "Every photo checked for fakes, "
        "recycled images, and misrepresentation.\n\n"
        "📄 *Document Verification*\n"
        "C of O, Survey Plan, Deed of Assignment "
        "— all authenticated.\n\n"
        "👥 *Witness Confirmation*\n"
        "Community members independently confirm "
        "the ownership claim.\n\n"
        "The result: a *Trust Score 0–100* "
        "on every listing.\n\n"
        "🥉 Bronze · 🥈 Silver · 🥇 Gold "
        "· 💎 Emerald\n\n"
        "No other platform in Nigeria does this.\n\n"
        "Ready to find a verified property? "
        "Reply *1* 🏠"
    ),
    (
        "I love this question, {name} — "
        "because the answer is what makes us "
        "completely different. 🛡️\n\n"
        "Every listing goes through "
        "*4 layers of verification:*\n\n"
        "1️⃣ *Physical GPS Visit*\n"
        "Our team goes to the location. Period.\n\n"
        "2️⃣ *Photo Intelligence Audit*\n"
        "Our system compares listing photos to "
        "satellite imagery to catch fakes.\n\n"
        "3️⃣ *Document Authentication*\n"
        "Title documents verified and on record.\n\n"
        "4️⃣ *Community Witness Check*\n"
        "Ownership confirmed on the ground.\n\n"
        "Each property gets a *Trust Score* — "
        "the higher the score, "
        "the safer your investment.\n\n"
        "See it live at *est8go.com*\n\n"
        "Want to find a verified property? "
        "Reply *1* 🏠"
    ),
]


def get_option_3(name: str) -> str:
    return random.choice(OPTION_3_VARIANTS).format(name=name)


# ================================================================
# OPTION 4 — Grow your business with Est8Go
# ================================================================

OPTION_4_INTRO_VARIANTS = [
    (
        "Excellent decision, {name}. 🚀\n\n"
        "The agencies on Est8Go are closing "
        "deals faster because buyers already "
        "*trust* their listings before they "
        "even make contact.\n\n"
        "When your listings carry the Est8Go "
        "verification badge, buyers stop "
        "negotiating from fear and start "
        "transacting from confidence.\n\n"
        "*What you get as a partner:*\n\n"
        "✅ GPS-verified listing badges\n"
        "✅ Kora — 24/7 lead qualification "
        "on WhatsApp\n"
        "✅ Trust scores that win buyer "
        "confidence instantly\n"
        "✅ Your own verified property vault\n"
        "✅ Full pipeline management dashboard\n\n"
        "Let me get your details — "
        "takes less than 2 minutes. 📋\n\n"
        "*What is your agency or "
        "business name?*"
    ),
    (
        "This could be one of the best "
        "decisions you make for your agency "
        "this year, {name}. 💯\n\n"
        "Here's the reality: buyers are tired "
        "of being defrauded. When they see an "
        "Est8Go verified listing, they don't "
        "ask *'is this real?'* — they ask "
        "*'how do I buy it?'* 🎯\n\n"
        "*Est8Go partner agencies get:*\n\n"
        "🛡️ Verified badges — instant "
        "buyer trust\n"
        "📱 Kora — 24/7 WhatsApp lead capture\n"
        "📊 Dashboard — listings, leads, "
        "analytics\n"
        "🌐 Verified vault — shareable "
        "for marketing\n\n"
        "Let me get your details — "
        "takes less than 2 minutes. 📋\n\n"
        "*What is your agency or "
        "business name?*"
    ),
]


def get_option_4_intro(name: str) -> str:
    return random.choice(OPTION_4_INTRO_VARIANTS).format(name=name)


FORM_STEP_2 = (
    "Got it. 👍\n\n"
    "*Which city or state do you "
    "primarily operate in?*"
)

FORM_STEP_3 = (
    "Great. 📍\n\n"
    "*Approximately how many active "
    "listings do you currently have?*"
)

FORM_STEP_4 = (
    "Perfect. 🏠\n\n"
    "*What is your full name?*"
)

FORM_STEP_5 = (
    "Almost done. 😊\n\n"
    "*What is the best phone number "
    "to reach you on?*"
)


def get_form_confirm(
    name: str,
    agency: str,
    city: str,
    listings: str,
    contact_name: str,
    phone: str,
) -> str:
    return (
        f"✅ *Application Received — "
        f"Thank you, {name}!*\n\n"
        f"Here's what we've recorded:\n\n"
        f"🏢 *Agency:* {agency}\n"
        f"📍 *City:* {city}\n"
        f"🏠 *Listings:* {listings}\n"
        f"👤 *Contact:* {contact_name}\n"
        f"📞 *Phone:* {phone}\n\n"
        f"Our team will reach out to you "
        f"within *24 hours* to complete "
        f"your onboarding.\n\n"
        f"Welcome to the Est8Go family. 🎉\n\n"
        f"Is there anything else I can "
        f"help you with? Reply *menu* "
        f"anytime. 😊"
    )


# ================================================================
# OPTION 5 — Report a suspicious listing
# ================================================================

OPTION_5_VARIANTS = [
    (
        "Thank you for this, {name}. 🙏\n\n"
        "Every report protects someone from "
        "losing their life savings. "
        "We take every one personally.\n\n"
        "Please share:\n\n"
        "1. *Property details* — address, "
        "listing link, or agent name/number\n"
        "2. *What's suspicious* — what raised "
        "your concern?\n"
        "3. *Any evidence* — screenshots, "
        "documents, anything helps\n\n"
        "We investigate within *24 hours*. "
        "Fraudulent listings are removed "
        "immediately.\n\n"
        "Your identity is 100% confidential. 🔒\n\n"
        "Go ahead — share what you know. 👇"
    ),
    (
        "You did the right thing, {name}. 💪\n\n"
        "Property fraud is destroying families "
        "in this country. Est8Go was built "
        "specifically to fight it — and reports "
        "like yours are how we win.\n\n"
        "Please tell me:\n\n"
        "📌 *What listing or agent?*\n"
        "Address, link, name, or number\n\n"
        "🚨 *What's suspicious?*\n"
        "Fake photos, wrong location, "
        "document issues, double selling\n\n"
        "📸 *Any evidence?*\n"
        "Screenshots welcome\n\n"
        "We treat every report with urgency. "
        "Your identity stays confidential. 🔒\n\n"
        "What can you share with me? 👇"
    ),
]


def get_option_5(name: str) -> str:
    return random.choice(OPTION_5_VARIANTS).format(name=name)


# ================================================================
# REPORT CONFIRMATION
# ================================================================

def get_report_confirm(name: str, ref: str) -> str:
    return (
        f"✅ *Report Received — Thank You, {name}*\n\n"
        f"Your report has been logged and escalated to our "
        f"trust investigation team.\n\n"
        f"🔖 *Reference:* EST-{ref}\n"
        f"⏱️ *Response time:* Within 24 hours\n\n"
        f"We will update you on the outcome. "
        f"If the listing is confirmed fraudulent, it will be "
        f"removed and the agent blacklisted from our platform.\n\n"
        f"You've just protected someone from a very costly mistake. "
        f"Thank you for that. 🙏\n\n"
        f"Is there anything else I can help you with? "
        f"Reply *menu* anytime to see your options. 👇"
    )


# ================================================================
# FALLBACK — When message doesn't match anything
# ================================================================

FALLBACK_VARIANTS = [
    (
        "Let me make sure I help you properly, "
        "{name}. 😊\n\n"
        "Here's what I can do for you:\n\n"
        "1️⃣ *Find a verified property*\n"
        "2️⃣ *Find a trusted agency near you*\n"
        "3️⃣ *How verification works*\n"
        "4️⃣ *Grow your business with Est8Go*\n"
        "5️⃣ *Report a suspicious listing*\n\n"
        "Which one can I help you with?"
    ),
    (
        "Happy to help, {name}. "
        "Let me make sure I understand "
        "what you need. 🤝\n\n"
        "1️⃣ Find a verified property\n"
        "2️⃣ Find a verified agency near you\n"
        "3️⃣ How our verification works\n"
        "4️⃣ Grow your business with Est8Go\n"
        "5️⃣ Report a suspicious listing\n\n"
        "Reply with a number or tell me "
        "what you're looking for."
    ),
]


def get_fallback(name: str) -> str:
    return random.choice(FALLBACK_VARIANTS).format(name=name)


# ================================================================
# MAIN ROUTER
# ================================================================

def get_platform_care_response(
    text: str,
    first_name: str,
    convo_data: dict,
) -> tuple[str, dict]:
    """
    Routes incoming message to correct care response.
    Returns (response_text, updated_convo_data).

    convo_data keys:
    - platform_state: menu | opt1 | opt2 | opt3 | opt4_step1-5
                      | reporting | searching
    - report_detail: str
    - form_agency, form_city, form_listings, form_contact: str
    """
    text_clean = text.strip().lower()
    state = convo_data.get("platform_state", "menu")
    updated = dict(convo_data)

    # ── Direct number selection ───────────────────────────────
    if text_clean in ("1", "2", "3", "4", "5"):
        if text_clean == "1":
            updated["platform_state"] = "opt1"
            return get_option_1(first_name), updated
        if text_clean == "2":
            updated["platform_state"] = "opt2"
            return get_option_2(first_name), updated
        if text_clean == "3":
            updated["platform_state"] = "opt3"
            return get_option_3(first_name), updated
        if text_clean == "4":
            updated["platform_state"] = "opt4_step1"
            return get_option_4_intro(first_name), updated
        if text_clean == "5":
            updated["platform_state"] = "reporting"
            return get_option_5(first_name), updated

    # ── Menu / reset ──────────────────────────────────────────
    if text_clean in ("menu", "back", "home", "restart", "options"):
        updated["platform_state"] = "menu"
        return get_welcome(first_name), updated

    # ── Reporting flow ────────────────────────────────────────
    if state == "reporting":
        import random as _r
        ref = str(_r.randint(100000, 999999))
        updated["platform_state"] = "menu"
        updated["report_detail"] = text
        return get_report_confirm(first_name, ref), updated

    # ── Option 1 follow-up (got property preferences) ────────
    if state == "opt1":
        updated["platform_state"] = "searching"
        return get_search_redirect(first_name), updated

    # ── Option 2 follow-up (got location) ────────────────────
    if state == "opt2":
        location = text.strip().title()
        updated["platform_state"] = "menu"
        return get_agency_found(first_name, location), updated

    # ── Option 3 follow-up — guide to property search ────────
    if state == "opt3":
        updated["platform_state"] = "opt1"
        return get_option_1(first_name), updated

    # ── Option 4 multi-step form ──────────────────────────────
    if state == "opt4_step1":
        updated["form_agency"] = text.strip()
        updated["platform_state"] = "opt4_step2"
        return FORM_STEP_2, updated

    if state == "opt4_step2":
        updated["form_city"] = text.strip().title()
        updated["platform_state"] = "opt4_step3"
        return FORM_STEP_3, updated

    if state == "opt4_step3":
        updated["form_listings"] = text.strip()
        updated["platform_state"] = "opt4_step4"
        return FORM_STEP_4, updated

    if state == "opt4_step4":
        updated["form_contact"] = text.strip().title()
        updated["platform_state"] = "opt4_step5"
        return FORM_STEP_5, updated

    if state == "opt4_step5":
        phone = text.strip()
        agency = updated.get("form_agency", "—")
        city = updated.get("form_city", "—")
        listings = updated.get("form_listings", "—")
        contact = updated.get("form_contact", "—")

        try:
            from app.database.db import get_db
            from sqlalchemy import text as sql_text
            import json as _json
            _db = next(get_db())
            _db.execute(sql_text("""
                INSERT INTO platform_issues
                (title, description, severity,
                 affected_area, tenant_id, status)
                VALUES (:title, :desc, 'low',
                        'agency_application', 12, 'open')
            """), {
                "title": f"Agency Application — {agency}",
                "desc": _json.dumps({
                    "agency": agency,
                    "city": city,
                    "listings": listings,
                    "contact": contact,
                    "phone": phone,
                    "source": "whatsapp_care",
                }),
            })
            _db.commit()
        except Exception as _e:
            import logging
            logging.warning(f"Could not save agency application: {_e}")

        for key in ("form_agency", "form_city", "form_listings", "form_contact"):
            updated.pop(key, None)
        updated["platform_state"] = "menu"

        return get_form_confirm(
            first_name, agency, city, listings, contact, phone
        ), updated

    # ── Keyword detection ─────────────────────────────────────
    words = set(text_clean.split())

    property_keywords = {
        "buy", "purchase", "rent", "land", "house", "apartment",
        "duplex", "property", "flat", "plot", "looking", "need",
        "find", "search", "want", "building", "bungalow", "mansion",
        "penthouse", "terrace", "detached",
        "oga", "madam", "i want", "i dey", "dey find", "i need",
        "e dey", "na",
    }
    agency_keywords = {
        "agency", "realtor", "agent", "firm", "company",
        "broker", "consultant",
        "person", "guy", "who fit", "who get",
    }
    verify_keywords = {
        "verify", "verification", "trust", "score", "how",
        "works", "gps", "document", "legit", "real", "fake",
        "safe", "scam", "fraud", "check",
        "e real", "e legit", "dem dey", "true true", "original",
    }
    join_keywords = {
        "join", "register", "signup", "sign up", "access",
        "onboard", "partner", "start", "list",
        "my listings", "business",
        "grow", "platform", "get on",
        "how to list", "add my agency",
        "i want to list", "register agency",
        "make i", "how to enter", "i wan join", "i want join", "add me",
    }
    report_keywords = {
        "report", "fake", "fraud", "scam", "suspicious",
        "dubious", "false", "stolen", "cheat",
        "dem dey lie", "na scam", "e fake", "dem cheat", "419",
    }

    if words & property_keywords:
        updated["platform_state"] = "opt1"
        return get_option_1(first_name), updated
    if words & agency_keywords:
        updated["platform_state"] = "opt2"
        return get_option_2(first_name), updated
    if words & verify_keywords:
        return get_option_3(first_name), updated
    if words & join_keywords:
        updated["platform_state"] = "opt4_step1"
        return get_option_4_intro(first_name), updated
    if words & report_keywords:
        updated["platform_state"] = "reporting"
        return get_option_5(first_name), updated

    # ── Default fallback ──────────────────────────────────────
    return get_fallback(first_name), updated
