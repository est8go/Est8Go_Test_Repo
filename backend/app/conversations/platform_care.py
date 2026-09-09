# app/conversations/platform_care.py
"""
Est8Go Platform Customer Care Flow
=====================================
Est8Go's OWN voice, on Est8Go's own number — not Kora speaking as an
agency (that is objection_engine.py and conversation_service.py).
Whoever messages here may be a buyer or an agency owner.

Position:
    Est8Go is where agencies list properties and buyers reach them. We
    hold what an agency records against a listing — coordinates, photos,
    documents on file — and show it. We do not inspect sites,
    authenticate documents, or vet agencies, and nothing here says we
    do. State what is on record; never claim it has been checked.

    Nothing here promises a callback, an investigation or a timeline
    either: reports and agency applications are written to
    convo.data_json and no code notifies anyone, so the copy routes
    people to est8go@gmail.com instead of committing a human who has
    not been told.

Warm, direct, Nigerian market savvy. Turns every enquiry into a
relationship without overselling what the platform is.
"""
import random
import re


# ================================================================
# WELCOME — Multiple variants for variety
# ================================================================

WELCOME_VARIANTS = [
    (
        "Hello {name}! 👋\n\n"
        "Welcome to *Est8Go*. We're where Nigerian agencies "
        "list their properties and buyers reach them "
        "directly.\n\n"
        "Every listing shows what the agency has put on "
        "record for it — coordinates, photos, documents on "
        "file — so you can see what's there before you "
        "call.\n\n"
        "How can I help?\n\n"
        "1️⃣ Find a property\n"
        "2️⃣ Find an agency near you\n"
        "3️⃣ How Est8Go works\n"
        "4️⃣ List your agency on Est8Go\n"
        "5️⃣ Report a listing\n\n"
        "Reply with a number or tell me "
        "what's on your mind."
    ),
    (
        "Hi {name}, good to have you here. 🤝\n\n"
        "You've reached *Est8Go*. Agencies list here, buyers "
        "enquire here, and we keep the two connected.\n\n"
        "We don't verify properties. What we do is show you "
        "exactly what each agency has filed on a listing, so "
        "nothing is hidden behind a phone call.\n\n"
        "What can I help you with?\n\n"
        "1️⃣ Find a property\n"
        "2️⃣ Find an agency near you\n"
        "3️⃣ How Est8Go works\n"
        "4️⃣ List your agency on Est8Go\n"
        "5️⃣ Report a listing\n\n"
        "Reply 1–5 or just tell me what you need."
    ),
    (
        "Welcome, {name}! 🏡\n\n"
        "You've reached *Est8Go* — where Nigerian agencies "
        "put their listings on record and buyers reach them "
        "without the runaround.\n\n"
        "1️⃣ Find a property\n"
        "2️⃣ Find an agency near you\n"
        "3️⃣ How Est8Go works\n"
        "4️⃣ List your agency on Est8Go\n"
        "5️⃣ Report a listing\n\n"
        "Which one can I help with?"
    ),
]


def get_welcome(name: str) -> str:
    return random.choice(WELCOME_VARIANTS).format(name=name)


# ================================================================
# MENU REPROMPT
# ================================================================

MENU_REPROMPT_VARIANTS = [
    (
        "I want to make sure I give you exactly the right help, {name}. 👇\n\n"
        "Please pick one:\n\n"
        "1️⃣ Find a property\n"
        "2️⃣ Find an agency near you\n"
        "3️⃣ How Est8Go works\n"
        "4️⃣ List your agency on Est8Go\n"
        "5️⃣ Report a listing"
    ),
    (
        "No worries, {name} — let me point you in the right direction.\n\n"
        "1️⃣ Find a property\n"
        "2️⃣ Find an agency near you\n"
        "3️⃣ How Est8Go works\n"
        "4️⃣ List your agency on Est8Go\n"
        "5️⃣ Report a listing\n\n"
        "Which one is closest to what you need?"
    ),
]


def get_reprompt(name: str) -> str:
    return random.choice(MENU_REPROMPT_VARIANTS).format(name=name)


# ================================================================
# OPTION 1 — Find a property
# ================================================================

OPTION_1_VARIANTS = [
    (
        "Perfect, {name}. Let's find you "
        "something. 🎯\n\n"
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
        "For every property I show you, you'll see what the "
        "agency has on record — coordinates, photos, "
        "documents on file. What you check beyond that is up "
        "to you.\n\n"
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
        "Quickest route is to browse what's listed and "
        "message the agency directly from any property that "
        "fits:\n"
        "👉 *est8go.com*\n\n"
        "Each listing shows what the agency has on record — "
        "coordinates, photos, documents on file.\n\n"
        "Tell me your city and I'll point you at the "
        "agencies covering it."
    ),
    (
        "Understood, {name}. 🤝\n\n"
        "Everything currently listed is here:\n"
        "👉 *est8go.com*\n\n"
        "Each one shows what the agency has filed against "
        "it, so you can compare before you call. A listing "
        "with more on record simply gives you more to "
        "check — it isn't a guarantee.\n\n"
        "Want me to narrow it down by city?"
    ),
]


def get_search_redirect(name: str) -> str:
    return random.choice(SEARCH_REDIRECT_VARIANTS).format(name=name)


# ================================================================
# OPTION 2 — Find an agency
# ================================================================

OPTION_2_VARIANTS = [
    (
        "Smart thinking, {name}. "
        "The right agency changes everything. 🤝\n\n"
        "Straight with you: Est8Go doesn't vet or rate "
        "agencies. What we do is make them accountable — "
        "every agency here operates under a named account, "
        "and every listing and document is attached to "
        "it.\n\n"
        "Which city are you looking in?\n\n"
        "📍 Abuja · Lagos · Port Harcourt "
        "· Enugu · Ibadan\n\n"
        "Tell me your city and I'll point you to "
        "who covers it."
    ),
    (
        "The agency you choose matters more than "
        "anything else, {name}. 💯\n\n"
        "Worth knowing: we don't grade agencies. What you "
        "get here is a named business with its listings on "
        "record, not an anonymous number.\n\n"
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
        f"You can browse the agencies covering *{location}* and everything "
        f"they have listed here:\n"
        f"🔗 *est8go.com*\n\n"
        f"Each listing shows what that agency has on record for it — "
        f"coordinates, photos, documents on file — so you can see what's "
        f"there before you pick up the phone. 📱\n\n"
        f"Want me to help you search for a specific "
        f"property in {location}? 🏠"
    )


# ================================================================
# OPTION 3 — How Est8Go works
# ================================================================

OPTION_3_VARIANTS = [
    (
        "Good question, {name}. Here's what we do, "
        "and what we don't. 🛡️\n\n"
        "*What agencies put on record*\n\n"
        "📍 *Site coordinates*\n"
        "Captured on-site by the agency, with the date "
        "recorded.\n\n"
        "🔍 *Photo checks*\n"
        "Listing photos are screened automatically for "
        "signs of reuse or manipulation.\n\n"
        "📄 *Documents on file*\n"
        "C of O, Survey Plan, Deed and others, uploaded by "
        "the agency and listed by type.\n\n"
        "*What that means*\n\n"
        "Each listing carries a score out of 100 showing "
        "how much of that the agency has actually filed. "
        "More on record means more for you to examine. It "
        "is not a verdict on whether the property is "
        "genuine.\n\n"
        "*What we don't do*\n\n"
        "We don't inspect sites, authenticate documents or "
        "vet agencies.\n\n"
        "Ready to look? Reply *1* 🏠"
    ),
    (
        "I like this question, {name}, because the honest "
        "answer is short. 🛡️\n\n"
        "Est8Go is where agencies put listings on record "
        "and buyers reach them directly. For each listing "
        "you can see:\n\n"
        "1️⃣ *Coordinates* — where the agency says it is, "
        "and when they recorded it\n"
        "2️⃣ *Photos* — screened automatically for reuse "
        "and manipulation\n"
        "3️⃣ *Documents on file* — which title documents "
        "the agency has uploaded\n\n"
        "That's a record, not a verification. We don't "
        "visit sites and we don't authenticate title — "
        "your own lawyer does that, and should.\n\n"
        "See it live at *est8go.com*\n\n"
        "Want to find a property? Reply *1* 🏠"
    ),
]


def get_option_3(name: str) -> str:
    return random.choice(OPTION_3_VARIANTS).format(name=name)


# ================================================================
# OPTION 4 — List your agency on Est8Go
# ================================================================

OPTION_4_INTRO_VARIANTS = [
    (
        "Good decision, {name}. 🚀\n\n"
        "Est8Go gives your listings somewhere buyers can "
        "actually inspect — coordinates, photos and "
        "documents on record, visible before anyone calls "
        "you. Fewer \"is this real?\" conversations, more "
        "real ones.\n\n"
        "*What you get:*\n\n"
        "✅ A public listing page for every property\n"
        "✅ Kora — 24/7 lead capture and qualification "
        "on WhatsApp\n"
        "✅ Your own shareable property vault\n"
        "✅ Full pipeline and lead dashboard\n"
        "✅ An embeddable widget for your own site\n\n"
        "Let me take your details — "
        "under 2 minutes. 📋\n\n"
        "*What is your agency or "
        "business name?*"
    ),
    (
        "Worth two minutes of your time, {name}. 💯\n\n"
        "Buyers are cautious for good reason. Est8Go "
        "doesn't ask them to take your word for it — it "
        "gives you somewhere to show what you actually hold "
        "on a property, so the conversation starts further "
        "along. 🎯\n\n"
        "*Est8Go agencies get:*\n\n"
        "🛡️ A listing page showing what's on record\n"
        "📱 Kora — 24/7 WhatsApp lead capture\n"
        "📊 Dashboard — listings, leads, "
        "analytics\n"
        "🌐 A shareable vault for your "
        "marketing\n\n"
        "Let me take your details — "
        "under 2 minutes. 📋\n\n"
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
    # No timeline is promised here: nothing in the platform care flow
    # notifies anyone. The form is written to convo.data_json and that
    # is all, so the email address is the only real route forward.
    return (
        f"✅ *Details received — "
        f"thank you, {name}!*\n\n"
        f"Here's what we've recorded:\n\n"
        f"🏢 *Agency:* {agency}\n"
        f"📍 *City:* {city}\n"
        f"🏠 *Listings:* {listings}\n"
        f"👤 *Contact:* {contact_name}\n"
        f"📞 *Phone:* {phone}\n\n"
        f"Next step is onboarding, which we set up by "
        f"email. To move it along, reach us directly at "
        f"*est8go@gmail.com* with your agency name.\n\n"
        f"Anything else I can help with? Reply *menu* "
        f"anytime. 😊"
    )


# ================================================================
# OPTION 5 — Report a listing
# ================================================================

OPTION_5_VARIANTS = [
    (
        "Thank you for this, {name}. 🙏\n\n"
        "Reports like this are how bad listings get taken "
        "down. Please share:\n\n"
        "1. *Property details* — address, "
        "listing link, or agency name/number\n"
        "2. *What's wrong* — what raised "
        "your concern?\n"
        "3. *Any evidence* — screenshots, "
        "documents, anything helps\n\n"
        "We won't pass your name to the agency. 🔒\n\n"
        "Go ahead — share what you know. 👇"
    ),
    (
        "You did the right thing, {name}. 💪\n\n"
        "Please tell me:\n\n"
        "📌 *Which listing or agency?*\n"
        "Address, link, name, or number\n\n"
        "🚨 *What's wrong?*\n"
        "Wrong location, reused photos, "
        "document problems, double selling\n\n"
        "📸 *Any evidence?*\n"
        "Screenshots welcome\n\n"
        "We won't pass your name to the agency. 🔒\n\n"
        "What can you share with me? 👇"
    ),
]


def get_option_5(name: str) -> str:
    return random.choice(OPTION_5_VARIANTS).format(name=name)


# ================================================================
# REPORT CONFIRMATION
# ================================================================

def get_report_confirm(name: str, ref: str) -> str:
    # Deliberately promises no investigation and no timeline. The report
    # is stored on the conversation row and nothing alerts anyone, so
    # the email address is the only route that actually reaches a human.
    return (
        f"✅ *Report received — thank you, {name}*\n\n"
        f"🔖 *Reference:* EST-{ref}\n\n"
        f"We've logged what you sent. A listing that turns out to be "
        f"misrepresented can be removed from the platform.\n\n"
        f"To make sure this is picked up quickly, email the same details "
        f"to *est8go@gmail.com* quoting your reference.\n\n"
        f"Anything else I can help you with? "
        f"Reply *menu* anytime. 👇"
    )


# ================================================================
# FALLBACK — When message doesn't match anything
# ================================================================

FALLBACK_VARIANTS = [
    (
        "Let me make sure I help you properly, "
        "{name}. 😊\n\n"
        "Here's what I can do for you:\n\n"
        "1️⃣ *Find a property*\n"
        "2️⃣ *Find an agency near you*\n"
        "3️⃣ *How Est8Go works*\n"
        "4️⃣ *List your agency on Est8Go*\n"
        "5️⃣ *Report a listing*\n\n"
        "Which one can I help you with?"
    ),
    (
        "Happy to help, {name}. "
        "Let me make sure I understand "
        "what you need. 🤝\n\n"
        "1️⃣ Find a property\n"
        "2️⃣ Find an agency near you\n"
        "3️⃣ How Est8Go works\n"
        "4️⃣ List your agency on Est8Go\n"
        "5️⃣ Report a listing\n\n"
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
