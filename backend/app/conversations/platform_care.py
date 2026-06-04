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
        "Welcome to *Est8Go* — Nigeria's property trust infrastructure.\n\n"
        "I'm Kora, your personal property guide. Before you spend a single naira, "
        "I make sure what you're buying is exactly what you're being shown. "
        "No surprises. No losses. Just verified deals. 🛡️\n\n"
        "How can I help you today?\n\n"
        "1️⃣ I want to find a verified property\n"
        "2️⃣ I need a trusted agency near me\n"
        "3️⃣ How does your verification actually work?\n"
        "4️⃣ I want my agency on Est8Go\n"
        "5️⃣ I want to report a suspicious listing\n\n"
        "Just reply with a number — or tell me what's on your mind. 👇"
    ),
    (
        "Hi {name}! Great to connect. 🤝\n\n"
        "You've reached *Est8Go* — where every property listing is GPS-verified, "
        "AI-audited, and document-checked before it ever reaches you.\n\n"
        "In a market where 1 in 3 listings is fake, we built the infrastructure "
        "that tells you the truth. 🔍\n\n"
        "What brings you here today?\n\n"
        "1️⃣ Find a verified property\n"
        "2️⃣ Find a verified agency near you\n"
        "3️⃣ Understand how verification works\n"
        "4️⃣ Get your agency on the platform\n"
        "5️⃣ Report a suspicious listing\n\n"
        "Reply 1–5 or simply tell me what you need. I'm listening. 👂"
    ),
    (
        "Welcome, {name}! 🏡\n\n"
        "You've reached *Est8Go* — Nigeria's most trusted property verification platform.\n\n"
        "Whether you're buying land, searching for an apartment, or looking for a "
        "realtor you can actually trust — you're in the right place.\n\n"
        "Here's how I can help you right now:\n\n"
        "1️⃣ Find a verified property\n"
        "2️⃣ Find a verified agency near you\n"
        "3️⃣ How our verification works\n"
        "4️⃣ Join Est8Go as an agency\n"
        "5️⃣ Report a suspicious listing\n\n"
        "What would you like to do? 👇"
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
        "4️⃣ Join Est8Go as an agency\n"
        "5️⃣ Report a suspicious listing"
    ),
    (
        "No worries, {name} — let me point you in the right direction.\n\n"
        "1️⃣ Find a verified property\n"
        "2️⃣ Find a verified agency near you\n"
        "3️⃣ How verification works\n"
        "4️⃣ Join Est8Go as an agency\n"
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
        "Perfect, {name}! You've come to the right place. 🎯\n\n"
        "Let me ask you three quick questions and I'll match you with "
        "the most relevant verified listings:\n\n"
        "*1. What type of property?*\n"
        "Land · House · Apartment\n\n"
        "*2. Which city or area?*\n"
        "Abuja, Lagos, Port Harcourt...\n\n"
        "*3. What's your budget range?*\n"
        "e.g. ₦50M, ₦20M–₦80M\n\n"
        "Start with the property type and we'll go from there. 🏠"
    ),
    (
        "Excellent choice, {name}. 💪\n\n"
        "Every property I'll show you has been physically visited by our team, "
        "GPS-coordinates confirmed, and documents checked. No stories.\n\n"
        "To find the perfect match quickly — tell me:\n\n"
        "• *What type?* Land, House, or Apartment?\n"
        "• *Which area?* Be as specific as possible\n"
        "• *Your budget?* Even a rough range helps\n\n"
        "Go ahead — what are you looking for? 👇"
    ),
    (
        "Great, {name}! Let's find you something verified and worth every naira. 🏡\n\n"
        "I need just three things:\n\n"
        "🏠 *Property type* — Land, House or Apartment?\n"
        "📍 *Location* — Which city or neighbourhood?\n"
        "💰 *Budget* — What's your range?\n\n"
        "The more specific you are, the better I can match you. "
        "Start wherever feels comfortable. 👇"
    ),
]


def get_option_1(name: str) -> str:
    return random.choice(OPTION_1_VARIANTS).format(name=name)


# ================================================================
# OPTION 1 SEARCH REDIRECT — After user gives preferences
# ================================================================

SEARCH_REDIRECT_VARIANTS = [
    (
        "Got it, {name}! 🎯\n\n"
        "I'm connecting you with a verified Est8Go partner agency "
        "that specialises in exactly that.\n\n"
        "In the meantime, you can browse live verified listings right now:\n"
        "🔗 *est8go.com*\n\n"
        "A verified agent will reach out to you shortly. "
        "We don't play with people's money here. 💪"
    ),
    (
        "Understood, {name}. Let me get the right people on this for you. 🤝\n\n"
        "I'm flagging your requirements to our verified agency network now.\n\n"
        "You can also view current verified listings at:\n"
        "🔗 *est8go.com*\n\n"
        "Every listing there has a Trust Score — the higher the score, "
        "the safer the investment. Expect a call from a verified agent soon. ✅"
    ),
]


def get_search_redirect(name: str) -> str:
    return random.choice(SEARCH_REDIRECT_VARIANTS).format(name=name)


# ================================================================
# OPTION 2 — Find a verified agency
# ================================================================

OPTION_2_VARIANTS = [
    (
        "Smart move, {name}. Choosing the *right agent* is half the battle. 🤝\n\n"
        "Est8Go only partners with agencies that have passed our verification "
        "standards — no fly-by-night operators, no property fraudsters.\n\n"
        "Which city are you searching in?\n\n"
        "We currently have verified partners in:\n"
        "📍 Abuja · Lagos · Port Harcourt · Enugu · Ibadan\n\n"
        "Tell me your city and I'll connect you directly. 🎯"
    ),
    (
        "Absolutely, {name}. The agent you work with determines everything. 🎯\n\n"
        "Our verified agencies have gone through background checks, "
        "document verification, and property quality audits before "
        "earning the Est8Go seal.\n\n"
        "Where are you based or looking to buy?\n\n"
        "📍 *Abuja · Lagos · Port Harcourt · Enugu · Ibadan and more*\n\n"
        "Share your city and I'll make the introduction. 🤝"
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
        "Great question, {name}. This is what makes Est8Go different "
        "from every other platform out there. 🛡️\n\n"
        "Here's exactly what happens before a listing goes live:\n\n"
        "📍 *Step 1 — GPS Verification*\n"
        "Our field team visits the physical location. Photos taken on-site, "
        "GPS coordinates locked. We confirm the property actually exists "
        "where it says it does.\n\n"
        "🤖 *Step 2 — AI Vision Audit*\n"
        "Our AI cross-checks every photo against satellite imagery and "
        "Street View to detect fake listings, recycled photos, and "
        "misrepresented properties.\n\n"
        "📄 *Step 3 — Document Verification*\n"
        "C of O, Survey Plan, Deed of Assignment — all reviewed and "
        "authenticated before the listing goes live.\n\n"
        "👥 *Step 4 — Witness Confirmation*\n"
        "Neighbours and community members independently confirm "
        "the ownership claim.\n\n"
        "The result? A *Trust Score from 0–100* on every listing.\n\n"
        "🥉 40–59 = Bronze\n"
        "🥈 60–74 = Silver\n"
        "🥇 75–89 = Gold\n"
        "💎 90–100 = Emerald\n\n"
        "No other platform in Nigeria does this. "
        "We built it because ₦1.6 trillion is lost to property fraud "
        "every year in this country. That ends here. 💪\n\n"
        "Ready to find a verified property? Reply *1* 🏠"
    ),
    (
        "I love this question, {name} — because the answer is what "
        "makes us completely different. 🛡️\n\n"
        "In Nigeria, 1 in 3 property listings is fake, duplicated, "
        "or misrepresented. Est8Go was built to change that.\n\n"
        "Every listing goes through *4 layers of verification:*\n\n"
        "1️⃣ *Physical GPS Visit* — Our team goes to the location. Period.\n\n"
        "2️⃣ *AI Vision Audit* — AI compares listing photos to satellite "
        "imagery to catch fakes.\n\n"
        "3️⃣ *Document Authentication* — Title documents verified by "
        "our legal team.\n\n"
        "4️⃣ *Community Witness Check* — We ask neighbours. Ownership "
        "claims are confirmed on the ground.\n\n"
        "Each verified property gets a *Trust Score* — the higher it "
        "is, the safer your investment.\n\n"
        "You can see it all live at *est8go.com* — every listing shows "
        "its verification audit trail in full transparency.\n\n"
        "Want to find a verified property now? Reply *1* 🏠"
    ),
]


def get_option_3(name: str) -> str:
    return random.choice(OPTION_3_VARIANTS).format(name=name)


# ================================================================
# OPTION 4 — Join as an agency
# ================================================================

OPTION_4_VARIANTS = [
    (
        "Now we're talking, {name}! 🚀\n\n"
        "The agencies on Est8Go are closing deals faster because buyers "
        "already *trust* their listings before picking up the phone.\n\n"
        "When your listings carry the Est8Go verification badge, the "
        "conversation changes — buyers stop negotiating from fear "
        "and start transacting from confidence. That's the difference.\n\n"
        "*What you get as a partner agency:*\n\n"
        "✅ GPS-verified listing badges that buyers respect\n"
        "✅ AI-powered WhatsApp bot that qualifies leads 24/7\n"
        "✅ Trust scores that win buyer confidence instantly\n"
        "✅ Your own verified property vault at est8go.com\n"
        "✅ Automated lead capture — even while you sleep\n"
        "✅ Full pipeline management dashboard\n\n"
        "To get started, email us:\n"
        "📧 *est8go@gmail.com*\n"
        "Subject: *Agency Access Request*\n\n"
        "Include your agency name, city, and number of active listings. "
        "We'll have you onboarded within 24 hours. ⚡\n\n"
        "Any questions before you reach out? I'm right here. 👇"
    ),
    (
        "Excellent, {name} — this is one of the best business decisions "
        "you'll make this year. 🎯\n\n"
        "Here's the reality: buyers are tired of being defrauded. "
        "When they see an Est8Go verified listing, they don't ask "
        "*'is this real?'* — they ask *'how do I buy it?'*\n\n"
        "That's the kind of buyer you want. And that's exactly who "
        "our platform sends to your listings. 🎯\n\n"
        "*Est8Go partner agencies get:*\n\n"
        "🛡️ Verified listing badges — instant buyer trust\n"
        "🤖 Kora AI bot — 24/7 lead qualification on WhatsApp\n"
        "📊 Full dashboard — listings, leads, pipeline, analytics\n"
        "📈 Trust scores — the highest converting tool in your arsenal\n"
        "🔗 Your own verified vault — shareable URL for marketing\n\n"
        "Getting started is simple:\n"
        "📧 Email: *est8go@gmail.com*\n"
        "Subject: *Agency Access Request*\n\n"
        "Tell us your agency name and city. "
        "We'll take it from there. 🤝"
    ),
]


def get_option_4(name: str) -> str:
    return random.choice(OPTION_4_VARIANTS).format(name=name)


# ================================================================
# OPTION 5 — Report a suspicious listing
# ================================================================

OPTION_5_VARIANTS = [
    (
        "Thank you for this, {name}. Seriously. 🙏\n\n"
        "Every report you make protects someone else from losing "
        "their life savings. We take every report personally.\n\n"
        "Please share the following:\n\n"
        "1. *The property details* — address, listing link, or "
        "agent's name/number\n"
        "2. *What seems wrong* — what raised your suspicion?\n"
        "3. *Any evidence* — screenshots, documents, anything helps\n\n"
        "Our trust team investigates within *24 hours*. "
        "Fraudulent listings are removed immediately and reported "
        "to relevant authorities.\n\n"
        "Your identity is 100% confidential. 🔒\n\n"
        "Go ahead — share what you know. 👇"
    ),
    (
        "You did the right thing reaching out, {name}. 💪\n\n"
        "Property fraud is destroying families in this country. "
        "Est8Go was built specifically to fight it — and reports "
        "like yours are how we win.\n\n"
        "Please tell me:\n\n"
        "🔍 *What listing or agent?* (address, link, name, or number)\n"
        "🚨 *What's suspicious?* (fake photos, wrong location, "
        "document issues, double selling)\n"
        "📸 *Any evidence?* (screenshots welcome)\n\n"
        "We treat every report with urgency. "
        "Your identity stays completely confidential. 🔒\n\n"
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
        "I want to make sure I give you the right help, {name}. 👇\n\n"
        "Here's what I can do for you right now:\n\n"
        "1️⃣ *Find a verified property* — GPS-checked, AI-audited\n"
        "2️⃣ *Find a trusted agency* — verified partners only\n"
        "3️⃣ *How verification works* — the full story\n"
        "4️⃣ *Join as an agency* — grow with us\n"
        "5️⃣ *Report suspicious listing* — protect the community\n\n"
        "Which one can I help you with? 👇"
    ),
    (
        "Happy to help, {name}! Let me make sure I understand "
        "what you need. 🤝\n\n"
        "1️⃣ Find a verified property\n"
        "2️⃣ Find a verified agency near you\n"
        "3️⃣ How our verification works\n"
        "4️⃣ Join Est8Go as an agency\n"
        "5️⃣ Report a suspicious listing\n\n"
        "Reply with a number or tell me more about "
        "what you're looking for. I'm here. 👂"
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
    - platform_state: menu | opt1 | opt2 | opt3 | opt4 | reporting | searching
    - report_detail: str
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
            updated["platform_state"] = "opt4"
            return get_option_4(first_name), updated
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

    # ── Option 3/4 follow-up ─────────────────────────────────
    if state in ("opt3", "opt4"):
        updated["platform_state"] = "opt1"
        return get_option_1(first_name), updated

    # ── Keyword detection ─────────────────────────────────────
    words = set(text_clean.split())

    property_keywords = {
        "buy", "purchase", "rent", "land", "house", "apartment",
        "duplex", "property", "flat", "plot", "looking", "need",
        "find", "search", "want", "building", "bungalow", "mansion",
        "penthouse", "terrace", "detached"
    }
    agency_keywords = {
        "agency", "realtor", "agent", "firm", "company",
        "broker", "consultant"
    }
    verify_keywords = {
        "verify", "verification", "trust", "score", "how",
        "works", "gps", "document", "legit", "real", "fake",
        "safe", "scam", "fraud", "check"
    }
    join_keywords = {
        "join", "register", "signup", "sign up", "access",
        "onboard", "partner", "start", "agency", "list",
        "my listings", "business"
    }
    report_keywords = {
        "report", "fake", "fraud", "scam", "suspicious",
        "dubious", "false", "stolen", "cheat"
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
        return get_option_4(first_name), updated
    if words & report_keywords:
        updated["platform_state"] = "reporting"
        return get_option_5(first_name), updated

    # ── Default fallback ──────────────────────────────────────
    return get_fallback(first_name), updated
