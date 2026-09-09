Read these files completely before 
writing any code:
- backend/app/conversations/templates.py
- backend/app/conversations/kora_behavior.py
- backend/app/services/conversation_service.py
- backend/app/services/chatbot/search_service.py
- backend/app/services/chatbot/message_builder.py

This is a WORLD CLASS conversation engine 
overhaul. Read everything first then 
apply ALL changes below in one pass.

════════════════════════════════════════
PART A1 — NEW DATA COLLECTION ORDER
File: templates.py
════════════════════════════════════════

Replace get_next_question function with:

def get_next_question(
    current_data: dict,
    tenant_areas_by_budget: list = None
) -> Optional[str]:
    """
    New funnel order:
    purpose → property_type → bedrooms 
    (if residential) → budget → 
    area (guided by budget) → search
    """
    
    # STEP 1 — Purpose (investment/personal)
    # Only ask if not already known and 
    # buyer hasn't given property details
    if not current_data.get("purpose"):
        return None  # Handled by opener
    
    # STEP 2 — Property type
    if not current_data.get("property_type"):
        purpose = current_data.get(
            "purpose", ""
        )
        if purpose == "investment":
            return (
                "What type of property are "
                "you investing in? 🏢\n\n"
                "🌱 *Land* — buy and hold "
                "or develop\n"
                "🏠 *House* — rental income "
                "or capital gain\n"
                "🏢 *Apartment* — high yield "
                "rental in prime areas"
            )
        else:
            return (
                "What type of property are "
                "you looking for? 🏠\n\n"
                "🌱 *Land* — build your "
                "dream home\n"
                "🏠 *House* — move-in ready "
                "family home\n"
                "🏢 *Apartment* — modern "
                "city living"
            )
    
    # STEP 3 — Bedrooms 
    # Only for house/apartment + personal use
    prop_type = current_data.get(
        "property_type", ""
    )
    purpose = current_data.get("purpose", "")
    
    if (
        prop_type in ("house", "apartment")
        and purpose == "personal"
        and not current_data.get("bedrooms")
        and not current_data.get(
            "bedrooms_skipped"
        )
    ):
        return (
            f"How many bedrooms do you need "
            f"for your {prop_type}? 🛏️\n\n"
            f"1 bed · 2 bed · 3 bed · "
            f"4 bed · 5+ bed\n\n"
            f"(Or say *Any* if flexible)"
        )
    
    # STEP 4 — Budget (before location)
    if (
        not current_data.get("budget_max")
        and not current_data.get("budget")
    ):
        prop_type_title = prop_type.title()
        purpose_hint = ""
        if purpose == "investment":
            purpose_hint = (
                "\n\nMost verified investment "
                "properties start from ₦15M. "
                "Returns depend on location "
                "and trust grade."
            )
        return (
            f"What is your budget for "
            f"this {prop_type_title}? 💰\n\n"
            f"(e.g. '30M', '20M to 80M', "
            f"'₦45,000,000'){purpose_hint}"
        )
    
    # STEP 5 — Area guided by budget
    # If tenant has areas within budget show them
    if not current_data.get("location"):
        budget = (
            current_data.get("budget_max")
            or current_data.get("budget")
            or 0
        )
        budget_fmt = (
            f"₦{int(budget)/1_000_000:.0f}M"
            if budget else ""
        )
        
        if (
            tenant_areas_by_budget
            and len(tenant_areas_by_budget) > 0
        ):
            # Show areas from tenant listings
            areas_list = "\n".join([
                f"📍 *{a['area'].title()}* "
                f"— from "
                f"₦{a['min_price']/1_000_000:.0f}M"
                for a in tenant_areas_by_budget[:4]
            ])
            return (
                f"For *{budget_fmt}* we have "
                f"verified {prop_type.title()} "
                f"listings in:\n\n"
                f"{areas_list}\n\n"
                f"Which area interests you? "
                f"Or type a specific area "
                f"you have in mind. 📍"
            )
        else:
            # No tenant listings in range —
            # ask area generally
            return (
                f"Which area are you "
                f"targeting? 📍\n\n"
                f"Tell me the neighbourhood "
                f"or estate and I'll search "
                f"our verified listings."
            )
    
    # All collected — ready to search
    return None

════════════════════════════════════════
PART A2 — BUDGET-GUIDED AREA LOOKUP
File: search_service.py
════════════════════════════════════════

Add this new function to search_service.py:

def get_tenant_areas_by_budget(
    db,
    tenant_id: int,
    budget: int,
    property_type: str = None,
    city: str = None,
) -> list:
    """
    Returns areas from tenant listings
    that have at least one property
    within the given budget.
    
    Returns list of dicts:
    [
        {
            "area": "lugbe",
            "min_price": 15000000,
            "count": 3
        },
        ...
    ]
    Sorted by min_price ascending.
    """
    from app.listings.models import Listing
    from sqlalchemy import func
    
    query = db.query(
        Listing.location,
        func.min(Listing.price).label(
            "min_price"
        ),
        func.count(Listing.id).label(
            "count"
        )
    ).filter(
        Listing.tenant_id == tenant_id,
        Listing.price <= budget,
        Listing.status == "verified",
    )
    
    if property_type:
        query = query.filter(
            Listing.property_type.ilike(
                f"%{property_type}%"
            )
        )
    
    if city:
        query = query.filter(
            Listing.location.ilike(
                f"%{city}%"
            )
        )
    
    results = query.group_by(
        Listing.location
    ).order_by(
        "min_price"
    ).limit(6).all()
    
    return [
        {
            "area": r.location or "",
            "min_price": int(r.min_price or 0),
            "count": int(r.count or 0),
        }
        for r in results
        if r.location
    ]


def get_tenant_cheapest_listing(
    db,
    tenant_id: int,
    property_type: str = None,
) -> dict:
    """
    Returns the cheapest verified listing
    for this tenant regardless of location.
    Used when buyer budget is too low.
    """
    from app.listings.models import Listing
    
    query = db.query(Listing).filter(
        Listing.tenant_id == tenant_id,
        Listing.status == "verified",
    )
    
    if property_type:
        query = query.filter(
            Listing.property_type.ilike(
                f"%{property_type}%"
            )
        )
    
    listing = query.order_by(
        Listing.price.asc()
    ).first()
    
    if not listing:
        return {}
    
    price = listing.price or 0
    if price >= 1_000_000_000:
        price_fmt = f"₦{price/1_000_000_000:.1f}B"
    elif price >= 1_000_000:
        price_fmt = f"₦{price/1_000_000:.0f}M"
    else:
        price_fmt = f"₦{price:,}"
    
    return {
        "id": listing.id,
        "title": listing.title,
        "location": listing.location,
        "price": price,
        "price_fmt": price_fmt,
        "trust_score": listing.trust_score,
        "trust_grade": listing.trust_grade,
        "property_type": listing.property_type,
    }

════════════════════════════════════════
PART A3 — WORLD CLASS OPENER
File: kora_behavior.py
════════════════════════════════════════

Add these opener functions:

def get_conversational_opener(
    first_name: str,
    biz_name: str,
    areas: str,
) -> str:
    """
    Warm conversational opener for 
    new buyers with no details given.
    """
    import random
    variants = [
        (
            f"Welcome to *{biz_name}*, "
            f"{first_name}! 🏡\n\n"
            f"You've just connected to one "
            f"of {areas}'s most trusted "
            f"verified property networks.\n\n"
            f"Before I open our vault — "
            f"quick question:\n\n"
            f"Are you buying for "
            f"*yourself to live in*, "
            f"or is this an *investment*?"
        ),
        (
            f"Hello {first_name}! "
            f"Great to have you here. 🤝\n\n"
            f"At *{biz_name}* every property "
            f"is GPS-verified and document-"
            f"checked before it reaches you. "
            f"No fake listings. No surprises.\n\n"
            f"To find your perfect match — "
            f"are you searching for a "
            f"*personal home* or an "
            f"*investment property*?"
        ),
        (
            f"Hi {first_name}! "
            f"Welcome to *{biz_name}*. 🏠\n\n"
            f"I'm Kora — your personal "
            f"property guide. I only show "
            f"you verified deals that have "
            f"been physically inspected "
            f"and document-checked.\n\n"
            f"Quick question to get started:\n\n"
            f"Are you buying to *live in* "
            f"or as an *investment*?"
        ),
    ]
    return random.choice(variants)


def get_investment_followup(
    first_name: str,
) -> str:
    return (
        f"Smart move, {first_name}. 📈\n\n"
        f"Verified properties consistently "
        f"outperform unverified ones — "
        f"buyers pay premium for certainty.\n\n"
        f"Are you buying to *rent out* "
        f"for monthly income, or to "
        f"*resell* for capital appreciation?"
    )


def get_personal_followup(
    first_name: str,
) -> str:
    return (
        f"Wonderful, {first_name}. 🏡\n\n"
        f"Finding a home you'll love "
        f"is personal — I take that "
        f"seriously.\n\n"
        f"What type of property are "
        f"you looking for?\n\n"
        f"🌱 *Land* — build your dream home\n"
        f"🏠 *House* — move-in ready\n"
        f"🏢 *Apartment* — modern city living"
    )


# Add to determine_bot_voice function:
# Handle new opener flags

if raw_reply == "opener_flag":
    return get_conversational_opener(
        first_name,
        biz_name,
        areas,
    )

if raw_reply == "investment_followup_flag":
    return get_investment_followup(first_name)

if raw_reply == "personal_followup_flag":
    return get_personal_followup(first_name)

════════════════════════════════════════
PART A4 — RETURNING BUYER WELCOME
File: conversation_service.py
════════════════════════════════════════

Replace build_welcome_back_message 
function with this world class version:

def build_welcome_back_message(
    convo,
    display_name: str,
    session_state: str,
    biz_name: str,
) -> str:
    """
    World class returning buyer welcome.
    Personalised based on previous search
    and time away.
    """
    data = json.loads(convo.data_json or "{}")
    location = (
        data.get("location") or ""
    ).title()
    prop_type = (
        data.get("property_type") or ""
    ).title()
    purpose = data.get("purpose", "")
    budget = (
        data.get("budget_max") or 
        data.get("budget")
    )
    bedrooms = data.get("bedrooms", "")
    
    # Format budget
    budget_fmt = ""
    if budget:
        try:
            b = int(budget)
            budget_fmt = (
                f"₦{b/1_000_000:.0f}M"
            )
        except (ValueError, TypeError):
            pass
    
    # Build search summary
    search_parts = []
    if bedrooms and bedrooms != "any":
        search_parts.append(
            f"{bedrooms}-bed"
        )
    if prop_type:
        search_parts.append(prop_type)
    if location:
        search_parts.append(f"in {location}")
    if budget_fmt:
        search_parts.append(
            f"within {budget_fmt}"
        )
    
    search_summary = (
        " ".join(search_parts) 
        if search_parts 
        else "a property"
    )
    
    if session_state == "hot":
        # < 3 days — direct continuation
        return (
            f"Welcome back, {display_name}! "
            f"🔥\n\n"
            f"You were just here looking "
            f"for *{search_summary}*.\n\n"
            f"Shall I pull up where "
            f"we left off?\n\n"
            f"Reply *Yes* to continue or "
            f"*New Search* to start fresh."
        )
    
    elif session_state == "warm":
        # 3-14 days — gentle resume
        purpose_note = ""
        if purpose == "investment":
            purpose_note = (
                f" The market has seen some "
                f"movement — good time to act."
            )
        return (
            f"Good to have you back, "
            f"{display_name}! 👋\n\n"
            f"It's been a few days since "
            f"we last spoke. The verified "
            f"inventory at *{biz_name}* "
            f"has been updated.{purpose_note}\n\n"
            f"You were looking for "
            f"*{search_summary}*.\n\n"
            f"Continue your search or "
            f"start fresh?\n\n"
            f"Reply *Continue* or "
            f"*New Search*."
        )
    
    else:
        # > 14 days — near fresh start
        return (
            f"Welcome back to *{biz_name}*, "
            f"{display_name}! 🏡\n\n"
            f"It's been a while — we have "
            f"exciting new verified listings "
            f"since your last visit.\n\n"
            f"Last time you searched for "
            f"*{search_summary}*.\n\n"
            f"Shall we start fresh or "
            f"continue from where you left?\n\n"
            f"Reply *Continue* or "
            f"*New Search*."
        )

════════════════════════════════════════
PART A5 — MAIN ORCHESTRATION CHANGES
File: conversation_service.py
════════════════════════════════════════

CHANGE 1 — New buyer greeting:

Find the greeting handler section:
if is_greeting:
    session_state = get_session_state(convo)

    if session_state == "new" or not convo:
        ...
        intro = get_executive_response(...)
        await send_meta_message(...)

Replace the NEW buyer block with:

if session_state == "new" or not convo:
    if not convo:
        res = start_conversation_service(
            channel, sender_id, 
            whatsapp_name, tenant_id, db
        )
        convo = db.get(
            Conversation, 
            res["conversation_id"]
        )
    
    # Check if buyer gave details 
    # in greeting message
    # e.g. "Hi I want land in Maitama 50M"
    greeting_has_details = bool(
        extract_intent_keywords(
            text_body.lower(),
            tenant_locations
        )
    )
    
    if greeting_has_details:
        # Skip opener — go straight 
        # to funnel processing
        # Set purpose as general
        convo_data = json.loads(
            convo.data_json or "{}"
        )
        convo_data["purpose"] = "general"
        convo.data_json = json.dumps(
            convo_data
        )
        db.commit()
        # Fall through to intent pipeline
        # by NOT returning here
    else:
        # New buyer with no details — 
        # show conversational opener
        opener = get_conversational_opener(
            first_name, biz_name,
            tenant_profile.get(
                "areas_covered", "Abuja"
            )
        )
        await send_meta_message(
            sender_id, opener,
            phone_number_id=platform_id,
        )
        # Set state to awaiting_purpose
        convo_data = json.loads(
            convo.data_json or "{}"
        )
        convo_data["awaiting_purpose"] = True
        convo.data_json = json.dumps(
            convo_data
        )
        convo.state = "ACTIVE"
        convo.last_active_at = (
            datetime.now(timezone.utc)
            .replace(tzinfo=None)
        )
        db.commit()
        return

CHANGE 2 — Purpose handler:

Add this block BEFORE the intent pipeline
(before step 8):

# ── PURPOSE HANDLER ──────────────────
_saved = json.loads(convo.data_json or "{}")
if _saved.get("awaiting_purpose"):
    _text = text_body.strip().lower()
    
    # Detect investment intent
    investment_words = {
        "investment", "invest", "roi",
        "rental", "rent out", "resell",
        "capital", "yield", "return",
        "buy to let", "commercial",
        "income", "profit", "appreciation"
    }
    personal_words = {
        "personal", "myself", "family",
        "live in", "living", "home",
        "residential", "my own", "stay",
        "house for myself", "move in",
        "own use", "we want to live"
    }
    
    _words = set(_text.split())
    
    if _words & investment_words or any(
        w in _text for w in investment_words
    ):
        purpose = "investment"
        followup = get_investment_followup(
            first_name
        )
    elif _words & personal_words or any(
        w in _text for w in personal_words
    ):
        purpose = "personal"
        followup = get_personal_followup(
            first_name
        )
    else:
        # Unclear — default to personal
        # most Nigerian buyers are personal
        purpose = "personal"
        followup = get_personal_followup(
            first_name
        )
    
    _saved["purpose"] = purpose
    _saved.pop("awaiting_purpose", None)
    convo.data_json = json.dumps(_saved)
    convo.state = "ACTIVE"
    convo.last_active_at = (
        datetime.now(timezone.utc)
        .replace(tzinfo=None)
    )
    db.commit()
    
    await send_meta_message(
        sender_id, followup,
        phone_number_id=platform_id,
    )
    return

# ── BEDROOMS HANDLER ─────────────────
if _saved.get("awaiting_bedrooms"):
    _text = text_body.strip().lower()
    
    # Extract bedroom count
    bedroom_map = {
        "1": "1", "one": "1", "1 bed": "1",
        "2": "2", "two": "2", "2 bed": "2",
        "3": "3", "three": "3", "3 bed": "3",
        "4": "4", "four": "4", "4 bed": "4",
        "5": "5", "five": "5", "5+": "5+",
        "any": "any", "flexible": "any",
        "doesn't matter": "any",
    }
    
    bedrooms = "any"
    for key, val in bedroom_map.items():
        if key in _text:
            bedrooms = val
            break
    
    # Also check for digit
    import re as _re2
    _digit = _re2.search(r'\b(\d)\b', _text)
    if _digit:
        bedrooms = _digit.group(1)
    
    _saved["bedrooms"] = bedrooms
    _saved.pop("awaiting_bedrooms", None)
    convo.data_json = json.dumps(_saved)
    db.commit()
    
    # Ask budget next
    prop_type = (
        _saved.get("property_type") or 
        "property"
    ).title()
    bed_str = (
        f"{bedrooms}-bedroom " 
        if bedrooms != "any" 
        else ""
    )
    
    await send_meta_message(
        sender_id,
        f"Perfect. What is your budget "
        f"for a {bed_str}"
        f"{prop_type}? 💰\n\n"
        f"(e.g. '30M', '20M to 80M', "
        f"'₦45,000,000')",
        phone_number_id=platform_id,
    )
    return

CHANGE 3 — Budget captured → show 
areas from tenant listings:

In add_message_service or after budget 
is captured in the intent pipeline,
add this after budget is extracted:

After budget is saved to current_data
and BEFORE asking for location,
query tenant areas within budget:

# After budget captured — 
# show tenant areas within budget
if (
    extracted.get("budget") or
    extracted.get("budget_max")
) and not current_data.get("location"):
    
    from app.services.chatbot.search_service\
        import get_tenant_areas_by_budget
    
    budget_val = (
        extracted.get("budget_max") or
        extracted.get("budget") or
        current_data.get("budget_max") or
        current_data.get("budget")
    )
    
    prop_type = current_data.get(
        "property_type", ""
    )
    
    areas = get_tenant_areas_by_budget(
        db, tenant_id, 
        int(budget_val),
        prop_type,
    )
    
    # Save areas to convo for use in 
    # get_next_question
    current_data["tenant_areas_in_budget"] = (
        areas
    )
    convo.data_json = json.dumps(current_data)
    db.commit()

CHANGE 4 — Pass areas to get_next_question:

Find every call to get_next_question
and add tenant_areas_by_budget parameter:

Replace:
next_q = get_next_question(current_data)

With:
next_q = get_next_question(
    current_data,
    tenant_areas_by_budget=current_data.get(
        "tenant_areas_in_budget", []
    )
)

Do this for ALL occurrences.

CHANGE 5 — Returning buyer welcome update:

Find build_welcome_back_message call:
welcome_msg = build_welcome_back_message(
    convo, first_name
)

Replace with:
session_state = get_session_state(convo)
welcome_msg = build_welcome_back_message(
    convo, first_name, 
    session_state, biz_name
)

════════════════════════════════════════
PART A6 — WORLD CLASS NO-RESULTS CASCADE
File: conversation_service.py
════════════════════════════════════════

Find BOTH no-results blocks 
(step 10 and completed_flag step 11).

Replace with this 6-level cascade:

# ════════════════════════════════
# WORLD CLASS NO-RESULTS CASCADE
# ════════════════════════════════

_loc = (prefs.get("location") or "").lower()
_ptype = prefs.get("property_type", "")
_budget = (
    prefs.get("budget_max") or 
    prefs.get("budget")
)
_purpose = prefs.get("purpose", "general")
_budget_fmt = (
    f"₦{int(_budget)/1_000_000:.0f}M"
    if _budget else ""
)
_loc_title = _loc.title()
_ptype_title = _ptype.title()

# Track searched areas to prevent loops
_searched = set(
    prefs.get("_searched_areas", [])
)
_searched.add(_loc)
prefs["_searched_areas"] = list(_searched)

# ── LEVEL 1: Nearby areas (same tenant) ──
from app.services.chatbot.message_builder\
    import NEARBY_AREAS

_nearby = [
    a for a in 
    NEARBY_AREAS.get(_loc, [])
    if a not in _searched
]

_nearby_results = {}
for _area in _nearby[:5]:
    try:
        _exp = execute_premium_search(
            db, tenant_id,
            {**prefs, "location": _area}
        )
        _exp_matches = _exp.get("data", [])
        if _exp_matches:
            _nearby_results[_area] = (
                _exp_matches
            )
    except Exception:
        continue

if _nearby_results:
    _msg = (
        f"No verified {_ptype_title} "
        f"listings in *{_loc_title}*"
    )
    if _budget_fmt:
        _msg += f" within *{_budget_fmt}*"
    _msg += (
        f" — but I found verified options "
        f"close by:\n\n"
    )
    
    _best = None
    for _area, _area_listings in (
        _nearby_results.items()
    ):
        _l = _area_listings[0]
        _p = _l.price or 0
        _p_fmt = (
            f"₦{_p/1_000_000:.0f}M"
            if _p >= 1_000_000
            else f"₦{_p:,}"
        )
        _s = _l.trust_score or 0
        _g = (
            _l.trust_grade or "verified"
        ).title()
        
        _msg += (
            f"📍 *{_area.title()}*\n"
            f"🏠 {_l.title}\n"
            f"💰 {_p_fmt} | "
            f"🛡️ {_s}/100 ({_g})\n\n"
        )
        if _best is None:
            _best = _l
    
    # Check if all nearby are over budget
    _all_prices = [
        _v[0].price 
        for _v in _nearby_results.values()
        if _v
    ]
    _min_nearby = (
        min(_all_prices) 
        if _all_prices else 0
    )
    
    if _budget and _min_nearby > _budget:
        _min_fmt = (
            f"₦{_min_nearby/1_000_000:.0f}M"
        )
        _msg += (
            f"💡 These are above your "
            f"{_budget_fmt} budget. "
            f"Closest option is "
            f"*{_min_fmt}*.\n\n"
            f"Would you like to adjust "
            f"your budget to match? "
            f"Or shall I check our "
            f"wider verified network? 🤝"
        )
    else:
        _msg += (
            f"Would any of these work "
            f"for you? Just say the "
            f"area name to search "
            f"further. 😊"
        )
    
    if _best:
        prefs["last_viewed_id"] = _best.id
        prefs["last_viewed_title"] = (
            _best.title or ""
        )
    
    convo.data_json = json.dumps(prefs)
    convo.state = "HANDOFF"
    convo.funnel_stage = "commitment"
    convo.last_active_at = (
        datetime.now(timezone.utc)
        .replace(tzinfo=None)
    )
    db.commit()
    
    await send_meta_message(
        sender_id, _msg,
        phone_number_id=platform_id,
    )
    return

# ── LEVEL 2: Tenant over-budget options ──
from app.services.chatbot.search_service\
    import get_tenant_cheapest_listing

_cheapest = get_tenant_cheapest_listing(
    db, tenant_id, _ptype
)

if _cheapest and _cheapest.get("price"):
    _cheap_fmt = _cheapest.get(
        "price_fmt", ""
    )
    _cheap_loc = (
        _cheapest.get("location") or ""
    ).title()
    _cheap_score = _cheapest.get(
        "trust_score", 0
    )
    _cheap_grade = (
        _cheapest.get("trust_grade") or 
        "verified"
    ).title()
    
    _stretch_msg = (
        f"Our closest verified "
        f"{_ptype_title} to your "
        f"budget is:\n\n"
        f"🏠 *{_cheapest.get('title')}*\n"
        f"📍 {_cheap_loc}\n"
        f"💰 *{_cheap_fmt}* | "
        f"🛡️ {_cheap_score}/100 "
        f"({_cheap_grade})\n\n"
    )
    
    if _budget:
        _diff = (
            (_cheapest["price"] - _budget) 
            / 1_000_000
        )
        _stretch_msg += (
            f"That's ₦{_diff:.0f}M above "
            f"your current budget.\n\n"
        )
    
    _stretch_msg += (
        f"Would you like to consider "
        f"this option? Or shall I check "
        f"what our verified partner "
        f"network has within "
        f"{_budget_fmt}? 🤝"
    )
    
    prefs["awaiting_stretch_choice"] = True
    prefs["stretch_listing_id"] = (
        _cheapest.get("id")
    )
    convo.data_json = json.dumps(prefs)
    convo.state = "ACTIVE"
    db.commit()
    
    await send_meta_message(
        sender_id, _stretch_msg,
        phone_number_id=platform_id,
    )
    return

# ── LEVEL 3: Partner referral ──────────
# Ask permission first
_referral_perm_msg = (
    f"I've searched thoroughly in "
    f"*{_loc_title}* and nearby areas, "
    f"{first_name}.\n\n"
    f"May I check our verified partner "
    f"network in the same city? 🤝\n\n"
    f"All properties are Est8Go verified "
    f"— GPS confirmed and document "
    f"checked.\n\n"
    f"Reply *Yes* to search the "
    f"wider network."
)

prefs["awaiting_referral_permission"] = True
convo.data_json = json.dumps(prefs)
convo.state = "ACTIVE"
db.commit()

await send_meta_message(
    sender_id, _referral_perm_msg,
    phone_number_id=platform_id,
)
return

════════════════════════════════════════
PART A7 — REFERRAL + CONSULTANT HANDLERS
File: conversation_service.py
════════════════════════════════════════

Add these handlers BEFORE the intent 
pipeline (before step 8):

# ── STRETCH CHOICE HANDLER ───────────
_saved2 = json.loads(convo.data_json or "{}")
if _saved2.get("awaiting_stretch_choice"):
    _choice = text_body.strip().lower()
    _saved2.pop("awaiting_stretch_choice", None)
    _stretch_id = _saved2.pop(
        "stretch_listing_id", None
    )
    
    _yes_words = {
        "yes", "ok", "okay", "sure", 
        "consider", "show me", "yes please",
        "i'll consider", "let me see",
        "show details", "proceed"
    }
    _no_words = {
        "no", "nope", "partner", 
        "check partner", "wider network",
        "other options", "not interested"
    }
    
    if any(w in _choice for w in _yes_words):
        # Show the stretch listing
        if _stretch_id:
            _lst = db.get(Listing, _stretch_id)
            if _lst:
                _p = _lst.price or 0
                _p_fmt = (
                    f"₦{_p/1_000_000:.0f}M"
                    if _p >= 1_000_000
                    else f"₦{_p:,}"
                )
                _score = _lst.trust_score or 0
                _grade = (
                    _lst.trust_grade or 
                    "verified"
                ).title()
                base_url = os.getenv(
                    "BASE_URL",
                    "https://api.est8go.com"
                )
                
                await send_meta_message(
                    sender_id,
                    f"Excellent choice, "
                    f"{first_name}! 🎯\n\n"
                    f"*{_lst.title}*\n"
                    f"📍 {(_lst.location or '').title()}\n"
                    f"💰 *{_p_fmt}*\n"
                    f"🛡️ Trust Score: "
                    f"*{_score}/100 ({_grade})*\n\n"
                    f"🔗 View full details:\n"
                    f"{base_url}/public/property/"
                    f"{_lst.id}\n\n"
                    f"Would you like to schedule "
                    f"a site inspection? 📅",
                    phone_number_id=platform_id,
                )
                _saved2["last_viewed_id"] = (
                    _lst.id
                )
                _saved2["last_viewed_title"] = (
                    _lst.title or ""
                )
                convo.data_json = json.dumps(
                    _saved2
                )
                convo.funnel_stage = "commitment"
                convo.state = "HANDOFF"
                db.commit()
        return
    else:
        # Check partner network
        _saved2[
            "awaiting_referral_permission"
        ] = True
        convo.data_json = json.dumps(_saved2)
        db.commit()
        
        await send_meta_message(
            sender_id,
            f"Understood, {first_name}. 🤝\n\n"
            f"May I check our verified partner "
            f"network? All properties are "
            f"Est8Go verified.\n\n"
            f"Reply *Yes* to search the "
            f"wider network.",
            phone_number_id=platform_id,
        )
        return

# ── REFERRAL PERMISSION HANDLER ──────
if _saved2.get("awaiting_referral_permission"):
    _choice = text_body.strip().lower()
    _yes_words = {
        "yes", "ok", "sure", "go ahead",
        "check", "search", "yes please",
        "proceed", "absolutely"
    }
    
    if any(w in _choice for w in _yes_words):
        _saved2.pop(
            "awaiting_referral_permission", 
            None
        )
        
        # Search partner tenants 
        # same city only
        _ptype = _saved2.get(
            "property_type", ""
        )
        _budget = (
            _saved2.get("budget_max") or
            _saved2.get("budget")
        )
        _loc = (
            _saved2.get("location") or ""
        ).lower()
        
        # Determine city from location
        _city = None
        for city in [
            "abuja", "lagos", 
            "port harcourt", "enugu", 
            "ibadan"
        ]:
            if city in _loc:
                _city = city
                break
        
        try:
            from app.listings.models import (
                Listing as _RL
            )
            from app.tenants.models import (
                Tenant as _RT
            )
            
            _ref_query = db.query(_RL).filter(
                _RL.tenant_id != tenant_id,
                _RL.status == "verified",
                _RL.trust_score > 30,
            )
            
            if _ptype:
                _ref_query = _ref_query.filter(
                    _RL.property_type.ilike(
                        f"%{_ptype}%"
                    )
                )
            
            if _budget:
                _ref_query = _ref_query.filter(
                    _RL.price <= int(_budget)
                )
            
            if _city:
                _ref_query = _ref_query.filter(
                    _RL.location.ilike(
                        f"%{_city}%"
                    )
                )
            
            _ref_listing = (
                _ref_query
                .order_by(
                    _RL.trust_score.desc()
                )
                .first()
            )
            
            if _ref_listing:
                _rp = _ref_listing.price or 0
                # Show approximate range 
                # NOT exact price
                _rp_range = (
                    f"₦{(_rp * 0.9)/1_000_000:.0f}M"
                    f" – "
                    f"₦{(_rp * 1.1)/1_000_000:.0f}M"
                    if _rp >= 1_000_000
                    else f"₦{_rp:,}"
                )
                _city_show = (
                    _city.title() 
                    if _city 
                    else "same city"
                )
                _grade = (
                    _ref_listing.trust_grade or 
                    "verified"
                ).title()
                
                # TEASER ONLY — no agency name,
                # no exact price, no link
                _ref_msg = (
                    f"Good news, {first_name}! 🎯\n\n"
                    f"I found a verified match "
                    f"in our wider network:\n\n"
                    f"🏠 {_ref_listing.property_type.title() if _ref_listing.property_type else 'Property'} — "
                    f"{_city_show}\n"
                    f"💰 Around {_rp_range}\n"
                    f"🛡️ Est8Go Verified "
                    f"({_grade} grade) ✓\n\n"
                    f"A consultant will share "
                    f"the full details with "
                    f"you directly.\n\n"
                    f"Shall I connect you now? 📞"
                )
                
                _saved2[
                    "awaiting_consultant"
                ] = True
                _saved2[
                    "referral_listing_id"
                ] = _ref_listing.id
                convo.data_json = json.dumps(
                    _saved2
                )
                convo.funnel_stage = "commitment"
                db.commit()
                
                await send_meta_message(
                    sender_id, _ref_msg,
                    phone_number_id=platform_id,
                )
                return
            
            else:
                # Nothing anywhere — 
                # offer vault browse + consultant
                _base = os.getenv(
                    "BASE_URL",
                    "https://api.est8go.com"
                )
                _slug = tenant_profile.get(
                    "slug", ""
                )
                
                await send_meta_message(
                    sender_id,
                    f"I've searched our entire "
                    f"verified network, "
                    f"{first_name}.\n\n"
                    f"Two options:\n\n"
                    f"1️⃣ *Browse our full vault* — "
                    f"you may find something "
                    f"I missed:\n"
                    f"👉 {_base}/public/{_slug}\n\n"
                    f"2️⃣ *Speak to a consultant* — "
                    f"they have access to "
                    f"off-market verified deals "
                    f"not yet listed online.\n\n"
                    f"Which would you prefer?",
                    phone_number_id=platform_id,
                )
                _saved2[
                    "awaiting_last_resort"
                ] = True
                convo.data_json = json.dumps(
                    _saved2
                )
                db.commit()
                return
        
        except Exception as _re:
            logger.error(
                f"Referral search failed: {_re}"
            )
    else:
        # Buyer declined referral
        _saved2.pop(
            "awaiting_referral_permission",
            None
        )
        convo.data_json = json.dumps(_saved2)
        db.commit()
        
        await send_meta_message(
            sender_id,
            f"No problem, {first_name}. 😊\n\n"
            f"Would you like to:\n\n"
            f"1️⃣ *Try a different area* — "
            f"tell me another location\n"
            f"2️⃣ *Adjust your budget* — "
            f"tell me your new range\n"
            f"3️⃣ *Change property type* — "
            f"Land · House · Apartment\n"
            f"4️⃣ *Start fresh* — "
            f"say *New Search*",
            phone_number_id=platform_id,
        )
        return

# ── CONSULTANT CONNECTION HANDLER ────
if _saved2.get("awaiting_consultant"):
    _choice = text_body.strip().lower()
    _yes_words = {
        "yes", "ok", "sure", "connect",
        "yes please", "go ahead",
        "connect me", "absolutely"
    }
    
    if any(w in _choice for w in _yes_words):
        _saved2.pop("awaiting_consultant", None)
        _ref_id = _saved2.pop(
            "referral_listing_id", None
        )
        
        # Build buyer brief
        _ptype = (
            _saved2.get("property_type") or 
            "property"
        ).title()
        _loc = (
            _saved2.get("location") or 
            "any area"
        ).title()
        _budget = (
            _saved2.get("budget_max") or
            _saved2.get("budget")
        )
        _budget_str = (
            f"₦{int(_budget)/1_000_000:.0f}M"
            if _budget else "not specified"
        )
        _bedrooms = _saved2.get(
            "bedrooms", ""
        )
        _purpose = _saved2.get(
            "purpose", "not specified"
        )
        _bed_str = (
            f"{_bedrooms} bedrooms" 
            if _bedrooms and _bedrooms != "any"
            else ""
        )
        
        _buyer_brief = (
            f"🔔 *NEW LEAD — CONSULTANT REQUIRED*\n\n"
            f"👤 Buyer: {first_name} "
            f"({whatsapp_name})\n"
            f"📱 Contact: {sender_id}\n\n"
            f"📋 *Search Brief:*\n"
            f"• Purpose: {_purpose.title()}\n"
            f"• Property: {_ptype}"
            f"{' ' + _bed_str if _bed_str else ''}\n"
            f"• Area: {_loc}\n"
            f"• Budget: {_budget_str}\n"
        )
        
        if _ref_id:
            _ref_lst = db.get(Listing, _ref_id)
            if _ref_lst:
                _ref_p = _ref_lst.price or 0
                _ref_fmt = (
                    f"₦{_ref_p/1_000_000:.0f}M"
                    if _ref_p >= 1_000_000
                    else f"₦{_ref_p:,}"
                )
                _buyer_brief += (
                    f"\n🏠 *Matched Listing:*\n"
                    f"{_ref_lst.title}\n"
                    f"📍 {(_ref_lst.location or '').title()}\n"
                    f"💰 {_ref_fmt}\n"
                    f"🛡️ Trust: "
                    f"{_ref_lst.trust_score}/100\n"
                )
        
        _buyer_brief += (
            f"\n⚡ Buyer is ready to proceed. "
            f"Please reach out within 2 hours."
        )
        
        # Alert realtor first, 
        # tenant as backup
        try:
            await alert_realtor_of_lead(
                db, _ref_id or 0, 
                sender_id, biz_name,
                phone_number_id=platform_id,
                custom_message=_buyer_brief
            )
        except Exception as _ae:
            logger.warning(
                f"Consultant alert failed: {_ae}"
            )
            # Fallback — send to tenant number
            _tenant_wa = getattr(
                tenant, 
                "whatsapp_phone_number", 
                None
            )
            if _tenant_wa:
                try:
                    await send_meta_message(
                        _tenant_wa,
                        _buyer_brief,
                        phone_number_id=platform_id,
                    )
                except Exception:
                    pass
        
        # Confirm to buyer
        await send_meta_message(
            sender_id,
            f"You're all set, {first_name}! ✅\n\n"
            f"Your search brief has been "
            f"sent to our consultant:\n\n"
            f"📋 *{_ptype}* in *{_loc}*\n"
            f"💰 Budget: *{_budget_str}*\n\n"
            f"They will reach out within "
            f"*2 hours* with full details "
            f"on verified options that "
            f"match your exact requirements.\n\n"
            f"Please keep your phone "
            f"available. 📱\n\n"
            f"Thank you for choosing "
            f"*{biz_name}* — where every "
            f"property is verified before "
            f"it reaches you. 🛡️",
            phone_number_id=platform_id,
        )
        
        convo.data_json = json.dumps(_saved2)
        convo.funnel_stage = "closed"
        convo.state = "CLOSED"
        convo.lead_score = 90
        convo.last_active_at = (
            datetime.now(timezone.utc)
            .replace(tzinfo=None)
        )
        db.commit()
        return
    
    else:
        # Declined consultant
        _saved2.pop("awaiting_consultant", None)
        _saved2.pop(
            "referral_listing_id", None
        )
        convo.data_json = json.dumps(_saved2)
        db.commit()
        
        await send_meta_message(
            sender_id,
            f"No problem, {first_name}. 😊\n\n"
            f"Is there anything else I can "
            f"help you with?\n\n"
            f"Say *New Search* to search "
            f"for a different property, "
            f"or *Menu* to see all options.",
            phone_number_id=platform_id,
        )
        return

# ── LAST RESORT HANDLER ──────────────
if _saved2.get("awaiting_last_resort"):
    _choice = text_body.strip().lower()
    _saved2.pop("awaiting_last_resort", None)
    
    if "1" in _choice or "browse" in _choice or "vault" in _choice:
        _base = os.getenv(
            "BASE_URL",
            "https://api.est8go.com"
        )
        _slug = tenant_profile.get("slug", "")
        convo.data_json = json.dumps(_saved2)
        db.commit()
        
        await send_meta_message(
            sender_id,
            f"Here's our full verified "
            f"property vault, {first_name}:\n\n"
            f"👉 {_base}/public/{_slug}\n\n"
            f"Every listing is GPS-verified "
            f"and document-checked. "
            f"Take your time browsing. 😊\n\n"
            f"Reply *I'm interested* on "
            f"any listing and I'll connect "
            f"you immediately.",
            phone_number_id=platform_id,
        )
        return
    
    else:
        # Consultant connection
        _saved2["awaiting_consultant"] = True
        convo.data_json = json.dumps(_saved2)
        db.commit()
        
        await send_meta_message(
            sender_id,
            f"Great choice, {first_name}. 📞\n\n"
            f"Our property consultants have "
            f"access to off-market verified "
            f"deals not yet listed online.\n\n"
            f"Shall I connect you now?",
            phone_number_id=platform_id,
        )
        return

════════════════════════════════════════
SELF CHECK — ALL 15 CRITERIA:
════════════════════════════════════════
1.  New buyer with no details → 
    conversational opener fires ✅
2.  New buyer WITH details in greeting → 
    skip opener, go straight to funnel ✅
3.  "Investment" detected → 
    investment language + rent/resell Q ✅
4.  "Personal" detected → 
    warm language + bedrooms Q ✅
5.  Budget collected BEFORE location ✅
6.  After budget → show tenant areas 
    with real prices from DB ✅
7.  Returning buyer HOT → 
    direct continuation message ✅
8.  Returning buyer WARM → 
    gentle resume message ✅
9.  Returning buyer COLD → 
    near-fresh start message ✅
10. No results Level 1 → 
    nearby with REAL listings shown ✅
11. No results Level 2 → 
    tenant cheapest option offered ✅
12. No results Level 3 → 
    referral with permission asked ✅
13. Referral → TEASER only 
    no agency name, no exact price ✅
14. Consultant → realtor alert + 
    tenant backup ✅
15. _searched_areas prevents 
    infinite loop ✅

Commit message: "feat: world class 
conversation engine — budget-first flow,
conversational opener, investment vs 
personal, returning buyer welcome,
6-level no-results cascade, 
referral with permission, 
consultant connection"
Push to GitHub.