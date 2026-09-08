"""
EST8GO MASTER CONVERSATION SERVICE (v3.0)
==========================================
Complete pipeline:
    1. Tenant Resolution (dynamic — no hardcoded IDs)
    2. Intent Pre-Filter (Python — 70% of messages free)
    3. Objection Handler (12 Nigerian RE objections)
    4. Session Memory (Hot/Warm/Cold resume)
    5. Lead Scoring (0-100, saved after every message)
    6. Funnel Stage Tracking (awareness → closed)
    7. GPT Extraction (only for unknown intents)
    8. Search + Handshake Delivery
"""

import logging
import json
import json as _json
import os
import re
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.listings.models import Listing
from app.services.notification_service import alert_realtor_of_lead
from app.conversations.responses import get_executive_response

# Domain & Infrastructure
from app.conversations.models import Conversation
from app.services.tenant_service import get_tenant_profile
from app.services.meta_sender_service import (
    send_meta_message,
)

# Logic Engines
from app.conversations.templates import is_filler, get_next_question, normalise_location
from app.conversations.brain import extract_preferences
from app.conversations.ai_fallback import is_company_faq, answer_company_faq
from app.company_profiles.models import CompanyProfile

# Intent Pre-Filter & Lead Scorer
from app.conversations.intent_filter import (
    classify_intent,
    calculate_lead_score,
    determine_funnel_stage,
    detect_property_reference,
)

# Objection Engine
from app.conversations.objection_engine import (
    get_objection_response,
    build_media_redirect,
)

# Search & Message Builders
from app.services.chatbot.search_service import execute_premium_search
from app.services.chatbot.message_builder import (
    build_property_summary,
    build_comparison_message,
    build_no_results_message,
    build_referral_summary,
    build_inspection_confirmation,
    _factual_badges,
)
from app.services.chatbot.kora_behavior import (
    determine_bot_voice,
    get_conversational_opener,
    get_investment_followup,
    get_personal_followup,
)
from app.services.chatbot.fallback_engine import handle_logic_error

# Tenant Resolver
from app.services.tenant_resolver import (
    resolve_tenant_from_webhook,
    extract_platform_id_from_webhook,
)

# Platform Care
from app.conversations.platform_care import (
    get_welcome,
    get_platform_care_response,
)

# In-memory deduplication set
_processed_messages: set = set()
logger = logging.getLogger(__name__)


def universal_fallback(
    prefs: dict,
    first_name: str,
    biz_name: str = "our team",
) -> str:
    """
    Never-fail response. Called whenever
    a reply would otherwise be empty or
    a raw *_flag string. Always returns
    something useful — never a dead end.
    """
    try:
        from app.conversations.templates import (
            get_next_question
        )
        nq = get_next_question(
            prefs,
            tenant_areas_by_budget=prefs.get(
                "tenant_areas_in_budget", []
            ),
        )
        if nq:
            return nq
    except Exception:
        pass

    # Location + budget known but stuck —
    # offer re-search
    if prefs.get("location") and (
        prefs.get("budget")
        or prefs.get("budget_max")
    ):
        _loc = (prefs.get("location") or "").title()
        _pt = prefs.get("property_type", "properties")
        return (
            f"Want me to pull up "
            f"{_pt} in {_loc} again, "
            f"{first_name}? Reply *Yes* "
            f"and I'll search now. 😊"
        )

    # Cold fallback — guided menu,
    # never a dead end
    return (
        f"I want to get this right, "
        f"{first_name}. 😊\n\n"
        f"Let's find you a property:\n\n"
        f"Just tell me:\n"
        f"🏠 *Property type*: Land, House "
        f"or Apartment\n"
        f"💰 *Budget*: e.g. 30M, 50M\n"
        f"📍 *Area*: e.g. Lekki, Guzape, GRA\n\n"
        f"Or say *New Search* to start fresh."
    )


def _get_negotiation_note(listing, db: Session) -> str:
    """
    Returns a negotiation hint string (or empty string) for a listing.
    Two signals: days on market + price vs area average.
    """
    from sqlalchemy import func

    notes = []

    # Signal 1: Days on market
    try:
        if listing.created_at:
            days = (datetime.utcnow() - listing.created_at).days
            if days > 90:
                notes.append(
                    f"⏰ *Listed for {days} days*, the seller may be open to negotiation."
                )
            elif days > 45:
                notes.append(
                    f"⏰ On market for {days} days, worth discussing price with the agent."
                )
    except Exception:
        pass

    # Signal 2: Price vs area average
    try:
        if listing.price and listing.location and listing.property_type:
            loc_fragment = (listing.location or "").split(",")[0].strip()
            avg_result = (
                db.query(func.avg(Listing.price))
                .filter(
                    Listing.property_type.ilike(f"%{listing.property_type}%"),
                    Listing.location.ilike(f"%{loc_fragment}%"),
                    Listing.status == "verified",
                    Listing.id != listing.id,
                )
                .scalar()
            )
            if avg_result:
                avg_price = int(avg_result)
                diff_pct = ((listing.price - avg_price) / avg_price) * 100
                avg_m = avg_price / 1_000_000
                if diff_pct > 15:
                    notes.append(
                        f"💡 *Market insight:* Priced {diff_pct:.0f}% above area average "
                        f"(₦{avg_m:.0f}M). There may be room to negotiate."
                    )
                elif diff_pct < -10:
                    notes.append(
                        f"✅ *Below area average* (₦{avg_m:.0f}M), this is good value "
                        f"for a property here."
                    )
    except Exception:
        pass

    return "\n".join(notes)


# ================================================================
# SESSION MEMORY — Hot / Warm / Cold
# ================================================================


def get_session_state(convo: Conversation) -> str:
    """
    Determines buyer session state based on last activity.

    Hot  → last active < 3 days   (pick up mid-funnel, direct to close)
    Warm → last active 3-14 days  (gentle resume, re-qualify lightly)
    Cold → last active > 14 days  (full re-qualify, treat as near-new)
    New  → no previous session
    """
    if not convo or not convo.last_active_at:
        return "new"

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    last_active = convo.last_active_at

    # Handle timezone-aware datetimes
    if hasattr(last_active, "tzinfo") and last_active.tzinfo:
        now = datetime.now(timezone.utc)

    delta = now - last_active

    if delta < timedelta(days=3):
        return "hot"
    elif delta < timedelta(days=14):
        return "warm"
    else:
        return "cold"


def build_resume_message(
    session_state: str, name: str, biz_name: str, prefs: dict
) -> str:
    """
    Returns the correct resume greeting based on session state.
    """
    location = prefs.get("location", "")
    budget = prefs.get("budget", "")
    budget_fmt = f"₦{int(budget):,}" if budget else ""

    if session_state == "hot":
        # Direct to close — they were just here
        context = ""
        if location and budget_fmt:
            context = (
                f"You were looking at *{location}* properties "
                f"within *{budget_fmt}*. "
            )
        elif location:
            context = f"You were exploring options in *{location}*. "

        return (
            f"Welcome back, {name}! 🔥\n\n"
            f"{context}"
            f"Shall I pull up where we left off?"
        )

    elif session_state == "warm":
        # Gentle nudge — acknowledge the gap
        return (
            f"Good to have you back, {name}. 👋\n\n"
            f"It's been a few days since we last spoke. "
            f"The inventory at *{biz_name}* has been updated since then.\n\n"
            f"Would you like to continue your previous search or explore fresh options?"
        )

    else:
        # Cold — near full re-qualify
        return (
            f"Welcome back to *{biz_name}*, {name}! 🏠\n\n"
            f"It's been a while, the market has moved and we have "
            f"exciting new listings available.\n\n"
            f"Shall we start fresh, or would you like me to recall your "
            f"previous preferences?"
        )


# ================================================================
# RETURNING BUYER HELPERS
# ================================================================


def is_returning_buyer(convo) -> bool:
    """True when buyer has an active mid-funnel search and was gone >30 mins."""
    if not convo or not convo.last_active_at:
        return False
    if convo.funnel_stage in ("awareness", "closed", None):
        return False
    last = convo.last_active_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return (now - last).total_seconds() > 1800


def build_welcome_back_message(
    convo,
    display_name: str,
    session_state: str,
    biz_name: str,
) -> str:
    """World class returning buyer welcome. Personalised by search history and time away."""
    data = json.loads(convo.data_json or "{}")
    location = (data.get("location") or "").title()
    prop_type = (data.get("property_type") or "").title()
    purpose = data.get("purpose", "")
    budget = data.get("budget_max") or data.get("budget")
    bedrooms = data.get("bedrooms", "")

    budget_fmt = ""
    if budget:
        try:
            b = int(budget)
            budget_fmt = f"₦{b/1_000_000:.0f}M"
        except (ValueError, TypeError):
            pass

    search_parts = []
    if bedrooms and bedrooms != "any":
        search_parts.append(f"{bedrooms}-bed")
    if prop_type:
        search_parts.append(prop_type)
    if location:
        search_parts.append(f"in {location}")
    if budget_fmt:
        search_parts.append(f"within {budget_fmt}")

    search_summary = " ".join(search_parts) if search_parts else "a property"

    if session_state == "hot":
        return (
            f"Welcome back, {display_name}! 🔥\n\n"
            f"You were just here looking for *{search_summary}*.\n\n"
            f"Shall I pull up where we left off?\n\n"
            f"Reply *Yes* to continue or *New Search* to start fresh."
        )

    elif session_state == "warm":
        purpose_note = ""
        if purpose == "investment":
            purpose_note = " The market has seen some movement — good time to act."
        return (
            f"Good to have you back, {display_name}! 👋\n\n"
            f"It's been a few days since we last spoke. The inventory at "
            f"*{biz_name}* has been updated.{purpose_note}\n\n"
            f"You were looking for *{search_summary}*.\n\n"
            f"Continue your search or start fresh?\n\n"
            f"Reply *Continue* or *New Search*."
        )

    else:
        return (
            f"Welcome back to *{biz_name}*, {display_name}! 🏡\n\n"
            f"It's been a while, we have exciting new listings since your last visit.\n\n"
            f"Last time you searched for *{search_summary}*.\n\n"
            f"Shall we start fresh or continue from where you left?\n\n"
            f"Reply *Continue* or *New Search*."
        )


# ================================================================
# LEAD SCORE UPDATER
# ================================================================


def update_conversation_intelligence(
    convo: Conversation, prefs: dict, intent: str, db: Session
):
    """
    Updates lead score, funnel stage, and session data after every message.
    Pure Python — zero AI cost.
    """
    # Calculate new funnel stage
    new_stage = determine_funnel_stage(prefs, intent)

    # Only advance funnel — never go backwards
    stage_order = ["awareness", "verification", "commitment", "handshake", "closed"]
    current_idx = stage_order.index(convo.funnel_stage or "awareness")
    new_idx = stage_order.index(new_stage)
    final_stage = stage_order[max(current_idx, new_idx)]

    # Calculate lead score
    new_score = calculate_lead_score(prefs, final_stage, convo.session_count or 1)

    # Update conversation
    convo.funnel_stage = final_stage
    convo.lead_score = new_score
    convo.last_active_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()

    logger.info(
        f"📊 LEAD UPDATE: Conversation {convo.id} | "
        f"Stage: {final_stage} | Score: {new_score}"
    )


# ================================================================
# CONVERSATION START
# ================================================================


def start_conversation_service(
    channel: str, uid: str, name: str, t_id: int, db: Session
):
    """Initializes interaction using the branded voice engine."""
    tenant_profile = get_tenant_profile(db, t_id)
    first_name = name.split()[0] if name else "there"

    convo = Conversation(
        tenant_id=t_id,
        channel=channel,
        external_user_id=uid,
        display_name=name,
        state="ACTIVE",
        data_json="{}",
        funnel_stage="awareness",
        lead_score=0,
        session_count=1,
        is_bot_active=True,
        last_active_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(convo)
    db.commit()
    db.refresh(convo)

    greeting = determine_bot_voice("start", "hi", first_name, tenant_profile)
    return {"conversation_id": convo.id, "reply": greeting}


# ================================================================
# STATE MACHINE
# ================================================================


def add_message_service(conversation_id: int, text: str, tenant_id: int, db: Session):
    convo = db.query(Conversation).get(conversation_id)
    text_clean = (text or "").strip().lower()

    # Atomic memory wipe
    if any(k in text_clean for k in ["new search", "restart", "start again"]):
        convo.data_json = "{}"
        convo.state = "ACTIVE"
        convo.funnel_stage = "awareness"
        convo.lead_score = 0
        db.commit()
        return {"reply": "fresh_start_flag", "prefs": {}, "intent": "restart"}

    if is_filler(text_clean):
        return {"reply": "filler_flag", "prefs": {}, "intent": "filler"}

    # FAQ Check
    if is_company_faq(text_clean):
        profile = (
            db.query(CompanyProfile)
            .filter(CompanyProfile.tenant_id == tenant_id)
            .first()
        )
        faq_reply = answer_company_faq(db, tenant_id, text_clean, profile)
        return {"reply": faq_reply, "prefs": {}, "intent": "faq"}

    # Intent Pre-Filter (Python — free)
    current_data = json.loads(convo.data_json or "{}")
    # Pull dynamic locations from this tenant's listings
    from app.listings.models import Listing as ListingModel

    tenant_locations = [
        r[0].lower()
        for r in db.query(ListingModel.location)
        .filter(ListingModel.tenant_id == tenant_id)
        .distinct()
        .all()
        if r[0]
    ]
    intent_result = classify_intent(text_clean, current_data, tenant_locations)

    # PROPERTY PAGE LEAD — short-circuit before any merge or GPT
    if intent_result.intent == "property_page_lead":
        return {
            "reply": "property_page_lead_flag",
            "prefs": current_data,
            "intent": "property_page_lead",
            "listing_id": intent_result.extracted.get("listing_id"),
        }

    # ALWAYS merge extracted data immediately — before get_next_question
    if intent_result.extracted:
        # Belt-and-braces: never let a unit-less "budget" extracted alongside
        # a location overwrite an established budget — that's almost always a
        # digit from an area name ("Wuse 2") rather than money. A budget with
        # an explicit unit (₦, m, million, b, k) is always honoured.
        _has_money_unit = bool(
            re.search(r"\d\s*(?:m\b|million|k\b|b\b|billion)", text_clean)
            or "₦" in text_clean
            or "naira" in text_clean
        )
        for k, v in intent_result.extracted.items():
            if not v:  # only update if value is not None/empty
                continue
            if (
                k == "budget"
                and intent_result.extracted.get("location")
                and current_data.get("budget")
                and not _has_money_unit
            ):
                continue  # keep the established budget
            current_data[k] = v
        # B5: when a fresh SINGLE budget is entered (no range), sync
        # budget_max to match it — so a stale budget_max (seeded by a
        # property-page entry or a no-results restore) can't override
        # the new ceiling in execute_premium_search (budget_max wins).
        # A genuine range supplies its own budget_max and is left alone.
        _new_budget = intent_result.extracted.get("budget")
        _new_budget_max = intent_result.extracted.get("budget_max")
        if _new_budget and not _new_budget_max:
            # honour the belt-and-braces guard: if the unit-less budget was
            # rejected above (digit from an area name), don't sync either
            if not (
                intent_result.extracted.get("location")
                and current_data.get("budget") != _new_budget
                and not _has_money_unit
            ):
                current_data["budget_max"] = current_data.get("budget")
        if current_data.get("location"):
            current_data["location"] = normalise_location(current_data["location"])
        convo.data_json = json.dumps(current_data)
        db.commit()

    # After budget captured — show tenant areas within budget
    _extr = intent_result.extracted or {}
    if (
        (_extr.get("budget") or _extr.get("budget_max"))
        and not _extr.get("location")
        and not current_data.get("location")
    ):
        try:
            from app.services.chatbot.search_service import get_tenant_areas_by_budget
            _bval = (
                _extr.get("budget_max") or _extr.get("budget")
                or current_data.get("budget_max") or current_data.get("budget")
            )
            _areas = get_tenant_areas_by_budget(
                db, tenant_id, int(_bval),
                current_data.get("property_type", ""),
            )
            current_data["tenant_areas_in_budget"] = _areas
            convo.data_json = json.dumps(current_data)
            db.commit()
        except Exception:
            pass

    # If intent is known — return immediately without GPT
    if not intent_result.needs_gpt:
        next_q = (
            get_next_question(
                current_data,
                tenant_areas_by_budget=current_data.get("tenant_areas_in_budget", []),
            ) if not intent_result.extracted else None
        )

        # Handle all known intents without GPT
        if intent_result.intent == "objection":
            return {
                "reply": intent_result.response_key,
                "prefs": current_data,
                "intent": "objection",
                "objection_key": intent_result.response_key,
            }

        if intent_result.intent == "agreement":
            return {
                "reply": "handshake_flag",
                "prefs": current_data,
                "intent": "agreement",
            }

        if intent_result.intent == "search_ready":
            return {
                "reply": "completed_flag",
                "prefs": current_data,
                "intent": "search_ready",
            }

        if intent_result.intent in (
            "property_type_query",
            "location_query",
            "price_query",
            "search_ready",
        ):
            if not current_data.get("purpose"):
                current_data["purpose"] = "general"
                convo.data_json = json.dumps(current_data)
                db.commit()
            next_q = get_next_question(
                current_data,
                tenant_areas_by_budget=current_data.get("tenant_areas_in_budget", []),
            )
            if not next_q:
                # All data collected — trigger search
                convo.state = "HANDOFF"
                db.commit()
                return {
                    "reply": "completed_flag",
                    "prefs": current_data,
                    "intent": intent_result.intent,
                }
            return {
                "reply": next_q,
                "prefs": current_data,
                "intent": intent_result.intent,
            }

        if next_q is None:
            convo.state = "HANDOFF"
            db.commit()
            return {
                "reply": "completed_flag",
                "prefs": current_data,
                "intent": intent_result.intent,
            }

        return {
            "reply": next_q or intent_result.response_key,
            "prefs": current_data,
            "intent": intent_result.intent,
        }

    # Hard cap — stop calling GPT after
    # N misses in one conversation to
    # prevent cost runaway on gibberish
    _gpt_calls = current_data.get("gpt_call_count", 0)
    if _gpt_calls >= 5:
        # Don't call GPT — return a guided
        # fallback via rules
        current_data["gpt_call_count"] = _gpt_calls
        next_q = get_next_question(
            current_data,
            tenant_areas_by_budget=current_data.get(
                "tenant_areas_in_budget", []
            ),
        )
        if not next_q:
            next_q = "completed_flag"
        return {
            "reply": next_q,
            "prefs": current_data,
            "intent": "gpt_capped",
        }

    # Unknown intent — escalate to GPT
    try:
        updated_data = extract_preferences(text_clean, current_data)
    except Exception as _gpt_err:
        logging.warning(f"GPT extract failed: {_gpt_err}")
        # GPT failed — fall back to rules
        updated_data = current_data
    # Track consecutive GPT misses — if GPT also extracts nothing,
    # increment miss counter. At 2 consecutive misses, force guided reset.
    if not updated_data or updated_data == current_data:
        miss_count = current_data.get("gpt_miss_count", 0) + 1
        updated_data["gpt_miss_count"] = miss_count
    else:
        updated_data["gpt_miss_count"] = 0
    # Count this GPT call against the per-conversation cap
    # (after the miss comparison so it doesn't affect equality)
    updated_data["gpt_call_count"] = _gpt_calls + 1
    # Preserve internal tracking keys GPT strips out
    for key in (
        "last_viewed_id",
        "last_viewed_title",
        "last_viewed_price",
        "last_viewed_location",
    ):
        if key in current_data and key not in updated_data:
            updated_data[key] = current_data[key]
    if updated_data.get("location"):
        updated_data["location"] = normalise_location(updated_data["location"])
    convo.data_json = json.dumps(updated_data)
    next_q = get_next_question(
        updated_data,
        tenant_areas_by_budget=updated_data.get("tenant_areas_in_budget", []),
    )

    if not next_q:
        convo.state = "HANDOFF"
        next_q = "completed_flag"

    db.commit()
    return {"reply": next_q, "prefs": updated_data, "intent": "gpt_extracted"}


# ================================================================
# NO-RESULTS CASCADE HELPER
# ================================================================


async def _send_property_card(
    db: Session,
    sender_id: str,
    listing,
    summary: str,
    phone_number_id: str = None,
    access_token: str = None,
) -> None:
    """
    Sends property results as an image card (photo + summary caption),
    falling back to plain text when the listing has no usable image or
    the image send fails.

    This is a plain WhatsApp type:"image" message — free-form, no Meta
    template involved, so it works inside the 24h window like any reply.

    Extracted from the two copies previously inlined on the main search
    path so every results path can deliver the same card. Text is never
    lost: a buyer always receives the summary, image or not.
    """
    try:
        from app.listings.models import ListingImage
        from app.services.notification_service import send_meta_image_message
        _img = (
            db.query(ListingImage)
            .filter(ListingImage.listing_id == listing.id)
            .order_by(ListingImage.is_main.desc().nullslast())
            .first()
        )
        if _img and _img.url:
            await send_meta_image_message(
                sender_id, _img.url, summary,
                phone_number_id=phone_number_id,
                access_token=access_token,
            )
            return
    except Exception as _e:
        logger.warning(f"Image card send failed, falling back to text: {_e}")

    await send_meta_message(
        sender_id, summary,
        phone_number_id=phone_number_id,
        access_token=access_token,
    )


async def _no_results_cascade(
    prefs: dict,
    first_name: str,
    sender_id: str,
    tenant_id: int,
    db,
    convo,
    platform_id: str,
    tenant_profile: dict,
    biz_name: str,
    access_token=None,
):
    """6-level no-results cascade: nearby → cheapest → referral permission."""
    _loc = (prefs.get("location") or "").lower()
    _ptype = prefs.get("property_type", "")
    _budget = prefs.get("budget_max") or prefs.get("budget")
    _budget_fmt = f"₦{int(_budget)/1_000_000:.0f}M" if _budget else ""
    _loc_title = _loc.title()
    _ptype_title = (_ptype or "property").title()

    _searched = set(prefs.get("_searched_areas", []))
    _searched.add(_loc)
    prefs["_searched_areas"] = list(_searched)

    # ── LEVEL 1: Nearby areas (real listings) ──────────────────
    from app.services.chatbot.message_builder import NEARBY_AREAS
    _nearby = [a for a in NEARBY_AREAS.get(_loc, []) if a not in _searched]

    _nearby_results = {}
    for _area in _nearby[:5]:
        try:
            _exp = execute_premium_search(db, tenant_id, {**prefs, "location": _area})
            _exp_matches = _exp.get("data", [])
            if _exp_matches:
                _nearby_results[_area] = _exp_matches
        except Exception:
            continue

    if _nearby_results:
        _msg = f"No {_ptype_title} listings in *{_loc_title}*"
        if _budget_fmt:
            _msg += f" within *{_budget_fmt}*"
        _msg += ", but I found some close options nearby:\n\n"

        _best = None
        for _area, _area_listings in _nearby_results.items():
            _l = _area_listings[0]
            _p = _l.price or 0
            _p_fmt = f"₦{_p/1_000_000:.0f}M" if _p >= 1_000_000 else f"₦{_p:,}"
            _b = _factual_badges(_l)
            _b_line = " · ".join(_b) if _b else "Verification details on the listing"
            _msg += f"📍 *{_area.title()}*\n🏠 {_l.title}\n💰 {_p_fmt}\n🛡️ {_b_line}\n\n"
            if _best is None:
                _best = _l

        _all_prices = [_v[0].price for _v in _nearby_results.values() if _v]
        _min_nearby = min(_all_prices) if _all_prices else 0

        if _budget and _min_nearby > _budget:
            _min_fmt = f"₦{_min_nearby/1_000_000:.0f}M"
            _msg += (
                f"💡 These are above your {_budget_fmt} budget. "
                f"Closest option is *{_min_fmt}*.\n\n"
                f"Would you like to adjust your budget to match? "
                f"Or shall I check our wider partner network? 🤝"
            )
        else:
            _msg += "Would any of these work for you? Just say the area name to search further. 😊"

        if _best:
            prefs["last_viewed_id"] = _best.id
            prefs["last_viewed_title"] = _best.title or ""

        convo.data_json = json.dumps(prefs)
        convo.state = "HANDOFF"
        convo.funnel_stage = "commitment"
        convo.last_active_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        await send_meta_message(sender_id, _msg, phone_number_id=platform_id, access_token=access_token)
        return

    # ── LEVEL 2: Tenant cheapest option ────────────────────────
    from app.services.chatbot.search_service import get_tenant_cheapest_listing
    _cheapest = get_tenant_cheapest_listing(db, tenant_id, _ptype, budget=_budget)

    if _cheapest and _cheapest.get("price"):
        _cheap_fmt = _cheapest.get("price_fmt", "")
        _cheap_loc = (_cheapest.get("location") or "").title()
        _stretch_msg = (
            f"Our closest {_ptype_title} to your budget is:\n\n"
            f"🏠 *{_cheapest.get('title')}*\n"
            f"📍 {_cheap_loc}\n"
            f"💰 *{_cheap_fmt}*\n\n"
        )

        if _budget:
            _delta = _cheapest["price"] - _budget
            _delta_m = abs(_delta) / 1_000_000
            if _delta > 0:
                _stretch_msg += (
                    f"That's ₦{_delta_m:.0f}M above "
                    f"your budget, but it's our closest "
                    f"match.\n\n"
                )
            elif _delta < 0:
                _stretch_msg += (
                    f"Good news, it's ₦{_delta_m:.0f}M "
                    f"*within* your budget. ✅\n\n"
                )
            else:
                _stretch_msg += (
                    f"It's right at your budget. ✅\n\n"
                )

        _stretch_msg += (
            f"Would you like to consider this option? Or shall I check what our "
            f"partner network has within {_budget_fmt}? 🤝"
        )

        prefs["awaiting_stretch_choice"] = True
        prefs["stretch_listing_id"] = _cheapest.get("id")
        convo.data_json = json.dumps(prefs)
        convo.state = "ACTIVE"
        db.commit()
        await send_meta_message(sender_id, _stretch_msg, phone_number_id=platform_id, access_token=access_token)
        return

    # ── LEVEL 3: Partner referral permission ───────────────────
    _referral_perm_msg = (
        f"I've searched thoroughly in *{_loc_title}* and nearby areas, {first_name}.\n\n"
        f"May I check our partner network in the same city? 🤝\n\n"
        f"Every listing shows its verification details, so you can see exactly what has been recorded.\n\n"
        f"Reply *Yes* to search the wider network."
    )

    prefs["awaiting_referral_permission"] = True
    convo.data_json = json.dumps(prefs)
    convo.state = "ACTIVE"
    db.commit()
    await send_meta_message(sender_id, _referral_perm_msg, phone_number_id=platform_id, access_token=access_token)


# ================================================================
# PLATFORM CARE HANDLER (Est8Go customer-facing flow)
# ================================================================


async def _handle_platform_care(
    db, tenant_id, sender_id,
    whatsapp_name, first_name, text_body, convo,
    phone_number_id=None
):
    if not convo:
        res = start_conversation_service(
            "whatsapp", sender_id, whatsapp_name,
            tenant_id, db
        )
        convo = db.get(Conversation, res["conversation_id"])

    convo_data = json.loads(convo.data_json or "{}")

    text_lower = text_body.strip().lower()
    is_greeting = (
        any(w in text_lower.split()
            for w in ["hi", "hello", "hey", "start",
                      "menu", "help", "helo", "hy"])
        and len(text_body.strip().split()) <= 4
    ) or not convo_data.get("platform_state")

    if is_greeting:
        await send_meta_message(sender_id, get_welcome(first_name), phone_number_id=phone_number_id)
        convo_data["platform_state"] = "menu"
    else:
        response, convo_data = get_platform_care_response(
            text_body, first_name, convo_data
        )
        await send_meta_message(sender_id, response, phone_number_id=phone_number_id)

    convo.data_json = json.dumps(convo_data)
    convo.state = "ACTIVE"
    convo.last_active_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()


# ================================================================
# META WEBHOOK BRIDGE — THE MASTER ORCHESTRATOR
# ================================================================


async def handle_incoming_message(data: dict, db: Session):
    """
    EST8GO MASTER ORCHESTRATOR (v3.0)
    Complete pipeline: Resolve → Filter → Respond → Score → Advance
    """
    try:
        # --- 1. UNIFIED PARSER ---
        entry = data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})

        if "messages" not in value and "messaging" not in entry:
            return

        sender_id = None
        text_body = ""
        btn_payload = ""
        whatsapp_name = "there"
        channel = "whatsapp"

        _msg_type = "text"
        _loc_lat = None
        _loc_lng = None

        # Path A: WhatsApp
        if "messages" in value:
            msg_obj = value["messages"][0]
            sender_id = msg_obj.get("from")
            text_body = msg_obj.get("text", {}).get("body", "")
            _msg_type = msg_obj.get("type", "text")
            # Capture location pin coordinates
            if _msg_type == "location":
                _loc = msg_obj.get("location", {})
                _loc_lat = _loc.get("latitude")
                _loc_lng = _loc.get("longitude")
            btn_payload = msg_obj.get("button", {}).get("payload", "") or msg_obj.get(
                "interactive", {}
            ).get("button_reply", {}).get("id", "")
            contacts = value.get("contacts", [])
            if contacts:
                whatsapp_name = contacts[0].get("profile", {}).get("name", "there")

        # Path B: Instagram / Messenger
        elif "messaging" in entry:
            msg_event = entry["messaging"][0]
            sender_id = msg_event.get("sender", {}).get("id")
            text_body = msg_event.get("message", {}).get("text", "")
            channel = "instagram" if "instagram" in str(data).lower() else "facebook"

        if not sender_id:
            return

        # Deduplicate — ignore if we've seen this message ID before
        msg_id = None
        if "messages" in value:
            msg_id = value["messages"][0].get("id", "")

        # Store processed message IDs in a simple set (resets on restart)
        if msg_id and msg_id in _processed_messages:
            logger.info(f"⏭️ Duplicate message {msg_id} — ignored")
            return
        if msg_id:
            _processed_messages.add(msg_id)
            # Keep set small — only last 1000 messages
            if len(_processed_messages) > 1000:
                _processed_messages.clear()
                return

        # --- 2. TENANT RESOLUTION (dynamic — no hardcoded IDs) ---
        platform, platform_id = extract_platform_id_from_webhook(data)
        tenant = resolve_tenant_from_webhook(db, platform, platform_id)

        if not tenant:
            logger.warning(
                f"⚠️ UNRESOLVED TENANT: [{platform}] {platform_id} — ignored"
            )
            return

        tenant_id = tenant.id
        tenant_profile = get_tenant_profile(db, tenant_id)
        first_name = whatsapp_name.split()[0] if whatsapp_name else "there"
        biz_name = tenant_profile.get("business_name", "our firm")

        # Resolve this tenant's WhatsApp
        # credentials (per-tenant token +
        # number). Falls back to global env
        # token if tenant has none stored.
        from app.services.meta_sender_service import (
            get_tenant_whatsapp_credentials
        )
        _tenant_pid, _tenant_token, _tenant_waba = (
            get_tenant_whatsapp_credentials(db, tenant_id)
        )
        # Use resolved number if present, else
        # keep the platform_id from the webhook
        _send_pid = _tenant_pid or platform_id
        _send_token = _tenant_token  # may be None →
                                     # senders fall back to env

        # Coverage cities — used by templates to skip city question for single-city tenants
        _coverage_cities = tenant_profile.get("coverage_cities", []) or []
        _single_city = len(_coverage_cities) == 1
        _primary_city = _coverage_cities[0] if _coverage_cities else None

        # --- 3. CONVERSATION LOOKUP ---
        convo = (
            db.query(Conversation)
            .filter_by(external_user_id=sender_id, tenant_id=tenant_id)
            .order_by(Conversation.updated_at.desc())
            .first()
        )

        # ── PLATFORM TENANT (Est8Go customer care) ──────────────
        if getattr(tenant, "tenant_type", "") == "platform":
            await _handle_platform_care(
                db, tenant_id, sender_id,
                whatsapp_name, first_name, text_body, convo,
                phone_number_id=platform_id
            )
            return

        # --- 4. HUMAN-IN-THE-LOOP CHECK ---
        if convo and hasattr(convo, "is_bot_active") and not convo.is_bot_active:
            logger.info(f"👤 HITL: Bot inactive for {sender_id} — Realtor has control")
            return

        # --- 5. BUTTON HANDLER ---
        if btn_payload and "INTERESTED_IN_" in btn_payload:
            list_id = int(btn_payload.split("_")[-1])
            listing = (
                db.query(Listing)
                .filter(
                    Listing.id == list_id,
                    Listing.tenant_id == tenant_id,
                )
                .first()
            )
            if listing:
                # Resolve dedicated agent/admin for this listing
                _agent_name = None
                _agent_role = None
                _agent_phone = None
                try:
                    from app.users.models import User as _BtnUser
                    _agent_user = None
                    if listing.assigned_realtor_id:
                        _agent_user = (
                            db.query(_BtnUser)
                            .filter(
                                _BtnUser.id == listing.assigned_realtor_id,
                                _BtnUser.is_active == True,
                            )
                            .first()
                        )
                    if not _agent_user:
                        _agent_user = (
                            db.query(_BtnUser)
                            .filter(
                                _BtnUser.tenant_id == tenant_id,
                                _BtnUser.role == "admin",
                                _BtnUser.is_active == True,
                                _BtnUser.phone_number.isnot(None),
                            )
                            .first()
                        )
                    if _agent_user:
                        _agent_name = (
                            _agent_user.first_name
                            or _agent_user.email.split("@")[0]
                        )
                        _agent_role = "Lead Property Consultant"
                        _agent_phone = _agent_user.phone_number or None
                except Exception:
                    pass

                # Message 1 — inspection confirmed + agent details
                _insp_msg = (
                    f"Perfect, {first_name}! 🎯\n\n"
                    f"Your inspection request for *{listing.title}* "
                    f"has been received and logged.\n\n"
                )
                if _agent_name:
                    _insp_msg += f"*Your dedicated consultant:*\n👤 {_agent_name}\n"
                    if _agent_role:
                        _insp_msg += f"🏢 {_agent_role}\n"
                    if _agent_phone:
                        _insp_msg += f"📱 {_agent_phone}\n"
                    _insp_msg += "\n"
                _insp_msg += (
                    f"They will call you personally within *2 hours* "
                    f"to confirm your visit details.\n\n"
                    f"Please keep your phone available. 📱"
                )
                await send_meta_message(
                    sender_id, _insp_msg, phone_number_id=_send_pid, access_token=_send_token
                )

                # Message 2 — navigation + directions (if available)
                _nav_url = ""
                if listing.latitude and listing.longitude:
                    _nav_url = (
                        f"https://www.google.com/maps/dir/?api=1"
                        f"&destination={listing.latitude},{listing.longitude}"
                        f"&travelmode=driving"
                    )
                _lst_dir = getattr(listing, "directions", None)
                if _nav_url or _lst_dir:
                    _close_msg = ""
                    if _nav_url:
                        _close_msg += f"📍 *Property Location:*\n{_nav_url}\n\n"
                    if _lst_dir:
                        _close_msg += f"🗺️ *How to find us:*\n{_lst_dir}\n\n"
                    _close_msg += (
                        f"Thank you for choosing *{biz_name}*, where every "
                        f"listing shows its verification details. 🛡️"
                    )
                    await send_meta_message(
                        sender_id, _close_msg, phone_number_id=_send_pid, access_token=_send_token
                    )

                # Alert agent with full buyer brief
                _bp = listing.price or 0
                _bp_fmt = (
                    f"₦{_bp/1_000_000:.0f}M" if _bp >= 1_000_000 else f"₦{_bp:,}"
                )
                _alert = (
                    f"🔔 *NEW INSPECTION REQUEST*\n\n"
                    f"👤 *Buyer:* {first_name}\n"
                    f"📱 *WhatsApp:* wa.me/{sender_id}\n\n"
                    f"🏠 *Property:* {listing.title}\n"
                    f"📍 *Location:* {(listing.location or '').title()}\n"
                    f"💰 *Price:* {_bp_fmt}\n"
                    f"🛡️ *Trust Score:* {listing.trust_score or 0}/100\n\n"
                )
                if _lst_dir:
                    _alert += f"🗺️ *Directions:*\n{_lst_dir}\n\n"
                if listing.latitude and listing.longitude:
                    _alert += (
                        f"📍 *Google Maps:*\n"
                        f"https://www.google.com/maps/dir/?api=1"
                        f"&destination={listing.latitude},{listing.longitude}\n\n"
                    )
                _alert += (
                    f"⚡ *Please call this buyer within 2 hours.*\n\n"
                    f"Tap to open their WhatsApp:\nwa.me/{sender_id}"
                )
                _alert_ok = await alert_realtor_of_lead(
                    db,
                    list_id,
                    sender_id,
                    biz_name,
                    phone_number_id=_send_pid,
                    custom_message=_alert,
                    access_token=_send_token,
                )
                if not _alert_ok:
                    # Escalate to super-admin —
                    # buyer was promised a call
                    try:
                        from app.tenants.models import Tenant as _ET
                        _esc_msg = (
                            f"⚠️ *AGENT ALERT FAILED*\n\n"
                            f"Tenant: {biz_name} (ID {tenant_id})\n"
                            f"Buyer: {first_name} — wa.me/{sender_id}\n"
                            f"Listing ID: {list_id}\n\n"
                            f"The buyer was told an agent would "
                            f"call within 2 hours but the agent "
                            f"alert could not be delivered. "
                            f"Please follow up manually."
                        )
                        _super = os.getenv(
                            "SUPER_ADMIN_WHATSAPP", ""
                        )
                        if _super:
                            # Super-admin escalation: intentionally
                            # global number + global token (matched
                            # pair). Goes to super-admin, not buyer.
                            await send_meta_message(
                                _super, _esc_msg,
                            )
                        logger.error(
                            f"AGENT ALERT FAILED for tenant "
                            f"{tenant_id}, buyer {sender_id}, "
                            f"listing {list_id}"
                        )
                    except Exception as _esc_e:
                        logger.error(
                            f"Escalation also failed: {_esc_e}"
                        )

                # Close funnel — agent takes over
                if convo:
                    convo.funnel_stage = "closed"
                    convo.state = "CLOSED"
                    convo.lead_score = 90
                    convo.last_active_at = datetime.now(timezone.utc).replace(
                        tzinfo=None
                    )
                    db.commit()
                return
            else:
                # Listing not found or not owned by this
                # tenant — never leave the buyer in silence
                # (mirrors property_page_lead not-found path)
                await send_meta_message(
                    sender_id,
                    f"Hi {first_name}! 👋\n\n"
                    f"That listing is no longer available "
                    f"or may have been removed.\n\n"
                    f"What are you looking for? I can help "
                    f"you find options in our "
                    f"vault, just tell me the *area* and "
                    f"*budget*. 🏠",
                    phone_number_id=_send_pid,
                    access_token=_send_token,
                )
                return

        # --- 6. GREETING HANDLER WITH SESSION MEMORY ---
        is_greeting = (
            any(
                w in text_body.lower().split()
                for w in ["hi", "hello", "hey", "start", "greetings"]
            )
            and len(text_body.strip().split()) <= 3
        )

        _process_as_intent = False

        if is_greeting:
            session_state = get_session_state(convo)

            if session_state == "new" or not convo:
                if not convo:
                    res = start_conversation_service(
                        channel, sender_id, whatsapp_name, tenant_id, db
                    )
                    convo = db.get(Conversation, res["conversation_id"])

                # Check if buyer gave details in greeting (e.g. "hi apt lekki 30M")
                from app.listings.models import Listing as _LM
                _tenant_locs = [
                    r[0].lower()
                    for r in db.query(_LM.location)
                    .filter(_LM.tenant_id == tenant_id)
                    .distinct()
                    .all()
                    if r[0]
                ]
                _gr = classify_intent(text_body.lower(), {}, _tenant_locs)
                greeting_has_details = bool(
                    _gr.extracted.get("property_type") or
                    _gr.extracted.get("location") or
                    _gr.extracted.get("budget") or
                    _gr.extracted.get("budget_max")
                )

                if greeting_has_details:
                    # Skip opener — process intent directly
                    _gd = json.loads(convo.data_json or "{}")
                    _gd["purpose"] = "general"
                    if _coverage_cities:
                        _gd["coverage_cities"] = _coverage_cities
                    convo.data_json = json.dumps(_gd)
                    convo.state = "ACTIVE"
                    convo.last_active_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    db.commit()
                    _process_as_intent = True
                else:
                    # New buyer with no details — conversational opener
                    opener = get_conversational_opener(
                        first_name, biz_name,
                        tenant_profile.get("areas_covered", "Abuja"),
                    )
                    await send_meta_message(sender_id, opener, phone_number_id=_send_pid, access_token=_send_token)
                    _gd = json.loads(convo.data_json or "{}")
                    _gd["awaiting_purpose"] = True
                    if _coverage_cities:
                        _gd["coverage_cities"] = _coverage_cities
                    convo.data_json = json.dumps(_gd)
                    convo.state = "ACTIVE"
                    convo.last_active_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    db.commit()
                    return

            elif is_returning_buyer(convo):
                # Returning buyer with active search — show memory recap
                session_state = get_session_state(convo)
                convo.session_count = (convo.session_count or 1) + 1
                # Flag the next reply so Continue/Yes resumes and No/anything
                # else starts fresh — instead of falling through to the
                # pipeline and silently re-running the old search.
                _wb = json.loads(convo.data_json or "{}")
                _wb["awaiting_welcome_choice"] = True
                convo.data_json = json.dumps(_wb)
                db.commit()
                welcome_msg = build_welcome_back_message(convo, first_name, session_state, biz_name)
                await send_meta_message(sender_id, welcome_msg, phone_number_id=_send_pid, access_token=_send_token)

            else:
                # Returning user — generic resume message
                prefs = json.loads(convo.data_json or "{}")
                convo.session_count = (convo.session_count or 1) + 1
                db.commit()
                resume_msg = build_resume_message(
                    session_state, first_name, biz_name, prefs
                )
                await send_meta_message(sender_id, resume_msg, phone_number_id=_send_pid, access_token=_send_token)

            if not _process_as_intent:
                convo.state = "ACTIVE"
                convo.last_active_at = datetime.now(timezone.utc).replace(tzinfo=None)
                db.commit()
                return

        # --- 7. GUARD: Create conversation if missing ---
        if not convo:
            res = start_conversation_service(
                channel, sender_id, whatsapp_name, tenant_id, db
            )
            convo = db.get(Conversation, res["conversation_id"])

        # ── POST-BOOKING GRACE (before 7b wipe) ──────────────────────
        # After a booking the funnel is "closed". The very next message is
        # often a courtesy ("you're welcome") or a booking question — not a
        # new search. Intercept those for a warm sign-off BEFORE the 7b reset
        # wipes the completed state. Only fires for a PURE courtesy/question
        # with no property signal — a genuine new search falls through to 7b.
        if convo.funnel_stage == "closed":
            _pb = json.loads(convo.data_json or "{}")
            _pb_text = text_body.strip().lower()

            from app.conversations.intent_filter import (
                extract_property_type,
                extract_location_from_text,
                extract_budget_from_text,
            )
            _has_signal = bool(
                extract_property_type(_pb_text)
                or extract_location_from_text(_pb_text)
                or extract_budget_from_text(_pb_text)
            )
            _new_search = "new search" in re.sub(
                r"[^a-z0-9 ]", "", _pb_text
            )

            from app.conversations.templates import is_closing_phrase
            _booking_q = any(
                w in _pb_text for w in
                ("when", "what time", "call me", "they call",
                 "how long", "who will")
            ) and not _has_signal

            if not _has_signal and not _new_search:
                if is_closing_phrase(text_body):
                    if not _pb.get("post_booking_acked"):
                        _pb["post_booking_acked"] = True
                        convo.data_json = json.dumps(_pb)
                        db.commit()
                        await send_meta_message(
                            sender_id,
                            f"My pleasure, {first_name}! 🤝 "
                            f"Your consultant will be in touch "
                            f"shortly. I'm here whenever you'd "
                            f"like to explore more "
                            f"properties. 😊",
                            phone_number_id=_send_pid,
                            access_token=_send_token,
                        )
                        return
                    else:
                        return
                if _booking_q:
                    convo.data_json = json.dumps(_pb)
                    db.commit()
                    await send_meta_message(
                        sender_id,
                        f"Your dedicated consultant will call "
                        f"you within 2 hours, {first_name}, to "
                        f"confirm your inspection details. Please "
                        f"keep your phone handy. 📱",
                        phone_number_id=_send_pid,
                        access_token=_send_token,
                    )
                    return
            # else: property signal OR new search → fall through to the
            # existing 7b reset (unchanged)

        # --- 7b. CLOSED STATE RESET ---
        # If buyer sends any message after a closed funnel, start fresh
        if convo.funnel_stage == "closed":
            convo.funnel_stage = "awareness"
            convo.state = "ACTIVE"
            convo.data_json = json.dumps({})
            db.commit()
            # Continue processing as a fresh conversation

        # --- 7-COVERAGE: Ensure coverage_cities
        # is in convo data for ALL buyers ---
        # (not just greeting-first buyers; placed after
        # 7b so the closed-state reset cannot wipe it)
        _cov_data = json.loads(convo.data_json or "{}")
        _cov_changed = False
        if _coverage_cities and not _cov_data.get("coverage_cities"):
            _cov_data["coverage_cities"] = _coverage_cities
            _cov_changed = True
        if _cov_changed:
            convo.data_json = json.dumps(_cov_data)
            db.commit()

        # --- 7-MEDIA: Handle non-text
        # message types ---
        if _msg_type in (
            "audio", "voice", "image",
            "video", "document", "sticker",
            "location"
        ):
            _first = first_name

            if _msg_type == "location" and _loc_lat and _loc_lng:
                # Location pin — acknowledge and
                # ask for area + budget
                # (reverse geocoding optional later)
                await send_meta_message(
                    sender_id,
                    f"Thanks for sharing your "
                    f"location, {_first}! 📍\n\n"
                    f"To find you the best "
                    f"properties nearby, could you "
                    f"tell me:\n\n"
                    f"🏠 *Property type*: Land, "
                    f"House or Apartment\n"
                    f"💰 *Budget*: e.g. 30M, 50M\n\n"
                    f"I'll search the closest "
                    f"options.",
                    phone_number_id=_send_pid, access_token=_send_token,
                )
                return

            elif _msg_type in ("audio", "voice"):
                await send_meta_message(
                    sender_id,
                    f"I can't open voice notes "
                    f"yet, {_first}. 🎙️\n\n"
                    f"Could you type your message "
                    f"instead? Just tell me the "
                    f"*area* and *budget* you're "
                    f"looking for and I'll find "
                    f"properties for you. 😊",
                    phone_number_id=_send_pid, access_token=_send_token,
                )
                return

            elif _msg_type in ("image", "video", "sticker"):
                await send_meta_message(
                    sender_id,
                    f"Thanks, {_first}! 📷\n\n"
                    f"I can't view media yet, but "
                    f"I'd love to help you find a "
                    f"property.\n\n"
                    f"Just tell me the *type*, "
                    f"*area* and *budget* you're "
                    f"after, e.g. \"3 bed house "
                    f"in Lekki, 80M\", and I'll "
                    f"pull up listings. 😊",
                    phone_number_id=_send_pid, access_token=_send_token,
                )
                return

            elif _msg_type == "document":
                await send_meta_message(
                    sender_id,
                    f"Thanks for the document, "
                    f"{_first}. 📄\n\n"
                    f"I can't open files here, but "
                    f"our consultant can review it "
                    f"with you directly.\n\n"
                    f"In the meantime, tell me the "
                    f"*area* and *budget* you're "
                    f"looking for and I'll find "
                    f"properties. 😊",
                    phone_number_id=_send_pid, access_token=_send_token,
                )
                return

        # Guard: empty text after media
        # handling — send gentle prompt
        # (placed after 7-MEDIA so handled
        # media types are not pre-empted)
        if not text_body or not text_body.strip():
            await send_meta_message(
                sender_id,
                f"I didn't catch that, {first_name}. 😊\n\n"
                f"Tell me what you're looking for, "
                f"the *area* and *budget*, and I'll "
                f"find you properties.\n\n"
                f"Or say *New Search* to start fresh.",
                phone_number_id=_send_pid, access_token=_send_token,
            )
            return

        # ── WELCOME-BACK CHOICE HANDLER ──────────────────────────────
        # Returning buyer greeted, got "Continue or New Search?". This reply
        # decides: resume (keep prefs) vs start fresh (clear prefs). Without
        # it, "No" fell through and re-ran the old search, and bare "Yes"
        # only worked by accident. Runs BEFORE the pipeline and the
        # commitment-decline handler so it owns the welcome reply.
        _wc = json.loads(convo.data_json or "{}")
        if _wc.get("awaiting_welcome_choice"):
            _wc_reply = text_body.strip().lower()
            _wc.pop("awaiting_welcome_choice", None)

            _continue_words = {
                "continue", "yes", "yeah", "yep", "sure",
                "ok", "okay", "yes continue", "resume",
                "pick up", "carry on", "go on",
            }

            if any(w in _wc_reply for w in _continue_words):
                # Resume — keep prefs, continue funnel
                convo.data_json = json.dumps(_wc)
                db.commit()
                _wc_next = get_next_question(
                    _wc,
                    tenant_areas_by_budget=_wc.get(
                        "tenant_areas_in_budget", []
                    ),
                )
                if _wc_next:
                    await send_meta_message(
                        sender_id, _wc_next,
                        phone_number_id=_send_pid,
                        access_token=_send_token,
                    )
                    return
                # All data collected → run the search explicitly (safer than
                # falling through — the line-1451 Continue handler doesn't
                # match bare "yes", so fall-through could drop the resume).
                if _wc.get("location") and (
                    _wc.get("budget") or _wc.get("budget_max")
                ):
                    try:
                        _wsr = execute_premium_search(db, tenant_id, _wc)
                        _wms = _wsr.get("data", [])
                        if _wms:
                            _wsum = build_property_summary(
                                _wms[0], _wms,
                                _wsr.get("total_count", 0), first_name,
                            )
                            await _send_property_card(
                                db, sender_id, _wms[0], _wsum,
                                phone_number_id=_send_pid,
                                access_token=_send_token,
                            )
                            _wc["last_viewed_id"] = _wms[0].id
                            _wc["last_viewed_title"] = _wms[0].title or ""
                            convo.data_json = json.dumps(_wc)
                            convo.state = "HANDOFF"
                            convo.funnel_stage = "commitment"
                            convo.last_active_at = datetime.now(
                                timezone.utc
                            ).replace(tzinfo=None)
                            db.commit()
                        else:
                            await send_meta_message(
                                sender_id,
                                build_no_results_message(
                                    _wc.get("location", ""),
                                    _wc.get("property_type", ""),
                                    _wc.get("budget_max") or _wc.get("budget"),
                                ),
                                phone_number_id=_send_pid,
                                access_token=_send_token,
                            )
                            _wc["awaiting_no_results_choice"] = True
                            _wc["no_results_location"] = _wc.get("location", "")
                            _wc["no_results_type"] = _wc.get("property_type", "")
                            _wc["no_results_budget"] = (
                                _wc.get("budget_max") or _wc.get("budget")
                            )
                            from app.services.chatbot.message_builder import NEARBY_AREAS
                            _wnr_loc = (_wc.get("location") or "").lower().strip()
                            _wc["no_results_nearby"] = NEARBY_AREAS.get(_wnr_loc, [])[:3]
                            convo.data_json = json.dumps(_wc)
                            db.commit()
                    except Exception as _we:
                        logger.error(f"Welcome-back resume search failed: {_we}")
                return
            else:
                # "No" / anything else → clear search prefs, start fresh
                _keep = {
                    k: _wc[k] for k in (
                        "coverage_cities", "city_locked",
                        "purpose",
                    ) if k in _wc
                }
                convo.data_json = json.dumps(_keep)
                convo.funnel_stage = "awareness"
                convo.state = "ACTIVE"
                db.commit()
                await send_meta_message(
                    sender_id,
                    f"No problem, {first_name}. Let's start "
                    f"fresh. 🏡\n\nWhat type of property are "
                    f"you looking for?\n\n🌱 Land\n🏠 House\n"
                    f"🏢 Apartment",
                    phone_number_id=_send_pid,
                    access_token=_send_token,
                )
                return

        # --- 7c. COMMITMENT DECLINE ---
        # Buyer said No after inspection offer — offer soft alternative
        _decline_words = {"no", "not now", "maybe later", "not interested", "no thanks", "nope", "nah"}
        if convo.funnel_stage == "commitment" and text_body.lower().strip() in _decline_words:
            _data = json.loads(convo.data_json or "{}")
            _location = (_data.get("location") or "that area").title()
            await send_meta_message(
                sender_id,
                f"No problem at all, {first_name}. 😊\n\n"
                f"When you're ready, just say Yes and we'll arrange "
                f"the inspection immediately.\n\n"
                f"In the meantime, would you like to see other "
                f"properties in {_location}, or explore a different area?",
                phone_number_id=_send_pid, access_token=_send_token,
            )
            _data["awaiting_after_decline"] = True
            convo.data_json = json.dumps(_data)
            convo.funnel_stage = "verification"
            db.commit()
            return

        # --- 7d. CONTINUE / NEW SEARCH HANDLERS ---
        _text_lower = text_body.lower().strip()

        if _text_lower in ("continue", "yes continue", "yes, continue"):
            _current = json.loads(convo.data_json or "{}")
            _next_q = get_next_question(
                _current,
                tenant_areas_by_budget=_current.get("tenant_areas_in_budget", []),
            )
            if _next_q:
                await send_meta_message(sender_id, _next_q, phone_number_id=_send_pid, access_token=_send_token)
                return
            # All data collected — run search immediately
            if _current.get("location") and (
                _current.get("budget") or _current.get("budget_max")
            ):
                try:
                    _sr = execute_premium_search(db, tenant_id, _current)
                    _ms = _sr.get("data", [])
                    if _ms:
                        _sum = build_property_summary(
                            _ms[0], _ms, _sr.get("total_count", 0), first_name
                        )
                        await _send_property_card(
                            db, sender_id, _ms[0], _sum,
                            phone_number_id=_send_pid, access_token=_send_token,
                        )
                        _current["last_viewed_id"] = _ms[0].id
                        _current["last_viewed_title"] = _ms[0].title or ""
                        convo.data_json = json.dumps(_current)
                        convo.state = "HANDOFF"
                        convo.funnel_stage = "commitment"
                        convo.last_active_at = datetime.now(timezone.utc).replace(
                            tzinfo=None
                        )
                        db.commit()
                    else:
                        await send_meta_message(
                            sender_id,
                            build_no_results_message(
                                _current.get("location", ""),
                                _current.get("property_type", ""),
                                _current.get("budget_max") or _current.get("budget"),
                            ),
                            phone_number_id=_send_pid, access_token=_send_token,
                        )
                        # Activate no-results menu handler so
                        # "1/2/3/4" are read as menu choices not budgets
                        _nr = json.loads(convo.data_json or "{}")
                        _nr["awaiting_no_results_choice"] = True
                        _nr["no_results_location"] = _current.get("location", "")
                        _nr["no_results_type"] = _current.get("property_type", "")
                        _nr["no_results_budget"] = (
                            _current.get("budget_max") or _current.get("budget")
                        )
                        from app.services.chatbot.message_builder import NEARBY_AREAS
                        _nr_loc = (_current.get("location") or "").lower().strip()
                        _nr["no_results_nearby"] = NEARBY_AREAS.get(_nr_loc, [])[:3]
                        convo.data_json = json.dumps(_nr)
                        db.commit()
                except Exception as _e:
                    logger.error(f"Continue search failed: {_e}")
            return

        _clean_lower = re.sub(r'[^a-z0-9 ]', '', _text_lower).strip()
        if _clean_lower in ("new search", "start fresh", "fresh start"):
            convo.data_json = json.dumps({})
            convo.funnel_stage = "awareness"
            convo.state = "ACTIVE"
            convo.lead_score = 0
            db.commit()
            import random as _rand
            _fresh_variants = [
                (
                    f"Consider it done, {first_name}. 🔄\n\n"
                    f"I've cleared your previous search "
                    f"and opened a fresh connection to "
                    f"our vault.\n\n"
                    f"What are you looking for this time?\n\n"
                    f"🌱 *Land*: prime plots for "
                    f"development or investment\n"
                    f"🏠 *House*: fully detached, "
                    f"semi-detached or duplex\n"
                    f"🏢 *Apartment*: modern flats "
                    f"and studio units\n\n"
                    f"Or simply describe what you "
                    f"have in mind. 😊"
                ),
                (
                    f"Fresh start, {first_name}. ✨\n\n"
                    f"Our vault is open "
                    f"and ready.\n\n"
                    f"What type of property are you "
                    f"searching for today?\n\n"
                    f"🌱 *Land*: build or invest\n"
                    f"🏠 *House*: move-in ready "
                    f"or off-plan\n"
                    f"🏢 *Apartment*: city living "
                    f"at its finest\n\n"
                    f"Just tell me what you need."
                ),
                (
                    f"All cleared, {first_name}. "
                    f"Let's find you something "
                    f"exceptional. 🏡\n\n"
                    f"Every property I show you comes with "
                    f"its verification details on file, "
                    f"so no fake listings and no wasted trips.\n\n"
                    f"What are we searching for?\n\n"
                    f"🌱 *Land*\n"
                    f"🏠 *House*\n"
                    f"🏢 *Apartment*"
                ),
            ]
            await send_meta_message(
                sender_id,
                _rand.choice(_fresh_variants),
                phone_number_id=_send_pid, access_token=_send_token,
            )
            return

        # ── AFTER-DECLINE HANDLER ──────────
        _ad = json.loads(convo.data_json or "{}")
        if _ad.get("awaiting_after_decline"):
            _ad_reply = text_body.strip().lower()
            _ad.pop("awaiting_after_decline", None)

            _same_area_words = {
                "same", "this area", "same area",
                "yes", "show others", "other properties",
                "others here",
            }
            _diff_area_words = {
                "different", "another", "different area",
                "another area", "explore", "other area",
                "change area", "elsewhere",
            }

            # Buyer wants a DIFFERENT area → clear
            # location + last_viewed, ask which area
            if any(w in _ad_reply for w in _diff_area_words):
                _ad.pop("location", None)
                _ad.pop("last_viewed_id", None)
                _ad.pop("last_viewed_title", None)
                convo.data_json = json.dumps(_ad)
                convo.funnel_stage = "verification"
                convo.state = "ACTIVE"
                db.commit()
                await send_meta_message(
                    sender_id,
                    f"Of course, {first_name}! 📍\n\n"
                    f"Which area would you like to "
                    f"explore? Just tell me the "
                    f"neighbourhood and I'll search "
                    f"our listings there.",
                    phone_number_id=_send_pid,
                    access_token=_send_token,
                )
                return

            # Buyer wants other options in SAME area
            # → show all tenant listings of that type
            if any(w in _ad_reply for w in _same_area_words):
                # Safety net: clear the declined listing so a
                # follow-on "yes" can't fall through to handshake
                # and book the property the buyer just declined.
                _ad.pop("last_viewed_id", None)
                _ad.pop("last_viewed_title", None)
                _ad["awaiting_see_all_tenant"] = True
                convo.data_json = json.dumps(_ad)
                db.commit()
                await send_meta_message(
                    sender_id,
                    f"Let me pull up our other "
                    f"options, {first_name}.\n\n"
                    f"Reply *Yes* to see everything we "
                    f"have.",
                    phone_number_id=_send_pid,
                    access_token=_send_token,
                )
                return

            # Unexpected reply → guided menu, no loop
            _ad["awaiting_no_results_choice"] = True
            convo.data_json = json.dumps(_ad)
            db.commit()
            await send_meta_message(
                sender_id,
                f"No problem, {first_name}. 😊\n\n"
                f"1️⃣ Try a different area\n"
                f"2️⃣ Adjust my budget\n"
                f"3️⃣ Change property type\n"
                f"4️⃣ Start a new search",
                phone_number_id=_send_pid,
                access_token=_send_token,
            )
            return

        # ── SEE-ALL-TENANT HANDLER ──────────
        _sa = json.loads(convo.data_json or "{}")
        if _sa.get("awaiting_see_all_tenant"):
            _sa_reply = text_body.strip().lower()
            _sa.pop("awaiting_see_all_tenant", None)

            _sa_yes = {
                "yes", "yeah", "yep", "sure", "ok",
                "okay", "show me", "see all", "everything",
                "show everything", "yes please",
            }

            if any(w in _sa_reply for w in _sa_yes):
                _sa_ptype = _sa.get("property_type", "")
                from app.listings.models import Listing as _SAL
                _sa_q = db.query(_SAL).filter(
                    _SAL.tenant_id == tenant_id,
                    _SAL.status == "verified",
                )
                if _sa_ptype:
                    _sa_q = _sa_q.filter(
                        _SAL.property_type.ilike(f"%{_sa_ptype}%")
                    )
                _sa_listings = _sa_q.order_by(
                    _SAL.price.asc()
                ).limit(8).all()

                if _sa_listings:
                    _sa_pt = _sa_ptype.title() if _sa_ptype else "Property"
                    _sa_msg = (
                        f"Here's everything we currently "
                        f"have for *{_sa_pt}*, "
                        f"{first_name}:\n\n"
                    )
                    for _l in _sa_listings[:6]:
                        _p = _l.price or 0
                        _p_fmt = (
                            f"₦{_p/1_000_000:.0f}M"
                            if _p >= 1_000_000
                            else f"₦{_p:,}"
                        )
                        _b = _factual_badges(_l)
                        _b_line = " · ".join(_b) if _b else "Verification details on the listing"
                        _loc = (_l.location or "").title()
                        _sa_msg += (
                            f"🏠 *{_l.title}*\n"
                            f"📍 {_loc} | 💰 {_p_fmt}\n"
                            f"🛡️ {_b_line}\n\n"
                        )
                    _sa_msg += (
                        f"Which area interests you most? "
                        f"Just tell me and I'll get you "
                        f"the full details. 😊"
                    )
                    _sa["last_match_ids"] = [l.id for l in _sa_listings]
                    convo.data_json = json.dumps(_sa)
                    convo.funnel_stage = "commitment"
                    convo.state = "HANDOFF"
                    db.commit()
                    await send_meta_message(
                        sender_id, _sa_msg,
                        phone_number_id=_send_pid,
                        access_token=_send_token,
                    )
                else:
                    convo.data_json = json.dumps(_sa)
                    db.commit()
                    await send_meta_message(
                        sender_id,
                        f"We don't have other "
                        f"{_sa_ptype or 'properties'} right "
                        f"now, {first_name}. Would you like "
                        f"to try a different property type "
                        f"or area? Say *New Search* to start "
                        f"fresh.",
                        phone_number_id=_send_pid,
                        access_token=_send_token,
                    )
                return
            else:
                # Not a yes — gentle redirect, no loop
                convo.data_json = json.dumps(_sa)
                db.commit()
                await send_meta_message(
                    sender_id,
                    f"No problem, {first_name}. 😊 Tell me "
                    f"an area and budget and I'll find you "
                    f"options, or say *New Search*.",
                    phone_number_id=_send_pid,
                    access_token=_send_token,
                )
                return

        # ── PURPOSE HANDLER ──────────────────────────────────────────
        _saved = json.loads(convo.data_json or "{}")
        if _saved.get("awaiting_purpose"):
            _pt = text_body.strip().lower()
            investment_words = {
                "investment", "invest", "roi", "rental", "rent out", "resell",
                "capital", "yield", "return", "buy to let", "commercial",
                "income", "profit", "appreciation",
            }
            personal_words = {
                "personal", "myself", "family", "live in", "living", "home",
                "residential", "my own", "stay", "house for myself",
                "move in", "own use", "we want to live",
            }
            _pt_words = set(_pt.split())
            if _pt_words & investment_words or any(w in _pt for w in investment_words):
                purpose = "investment"
                followup = get_investment_followup(first_name)
            elif _pt_words & personal_words or any(w in _pt for w in personal_words):
                purpose = "personal"
                followup = get_personal_followup(first_name)
            else:
                purpose = "personal"
                followup = get_personal_followup(first_name)

            _saved["purpose"] = purpose
            _saved.pop("awaiting_purpose", None)
            convo.data_json = json.dumps(_saved)
            convo.state = "ACTIVE"
            convo.last_active_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()
            await send_meta_message(sender_id, followup, phone_number_id=_send_pid, access_token=_send_token)
            return

        # ── BEDROOMS HANDLER ──────────────────────────────────────────
        if _saved.get("awaiting_bedrooms"):
            _bt = text_body.strip().lower()
            bedroom_map = {
                "1": "1", "one": "1", "1 bed": "1",
                "2": "2", "two": "2", "2 bed": "2",
                "3": "3", "three": "3", "3 bed": "3",
                "4": "4", "four": "4", "4 bed": "4",
                "5": "5", "five": "5", "5+": "5+",
                "any": "any", "flexible": "any", "doesn't matter": "any",
            }
            bedrooms = "any"
            for key, val in bedroom_map.items():
                if key in _bt:
                    bedrooms = val
                    break
            import re as _re2
            _digit = _re2.search(r'\b(\d)\b', _bt)
            if _digit:
                bedrooms = _digit.group(1)

            _saved["bedrooms"] = bedrooms
            _saved.pop("awaiting_bedrooms", None)
            convo.data_json = json.dumps(_saved)
            db.commit()

            _prop_type = (_saved.get("property_type") or "property").title()
            _bed_str = f"{bedrooms}-bedroom " if bedrooms != "any" else ""
            await send_meta_message(
                sender_id,
                f"Perfect. What is your budget for a {_bed_str}{_prop_type}? 💰\n\n"
                f"(e.g. '30M', '20M to 80M', '₦45,000,000')",
                phone_number_id=_send_pid, access_token=_send_token,
            )
            return

        # ── STRETCH CHOICE HANDLER ────────────────────────────────────
        _saved2 = json.loads(convo.data_json or "{}")
        if _saved2.get("awaiting_stretch_choice"):
            _sc = text_body.strip().lower()
            _saved2.pop("awaiting_stretch_choice", None)
            _stretch_id = _saved2.pop("stretch_listing_id", None)

            # Look up the offered listing so NAMING its area counts as acceptance
            _lst = db.get(Listing, _stretch_id) if _stretch_id else None
            _stretch_loc = (_lst.location or "").lower() if _lst else ""

            _seeall_phrases = {
                "see all", "see everything", "show everything",
                "show all", "everything", "all options", "see all options",
            }
            _decline_w = {
                "nope", "partner", "check partner", "wider network",
                "other options", "not interested",
            }
            _yes_w = {
                "yes", "ok", "okay", "sure", "consider", "show me",
                "yes please", "i'll consider", "let me see",
                "show details", "proceed",
            }
            _accept_phrases = {
                "fine", "works", "that works", "okay", "ok",
                "good", "perfect", "go with", "take it",
                "i'll take", "ill take", "that one", "this one",
                "sounds good", "is fine", "go ahead", "alright", "sure",
            }

            _is_seeall = any(p in _sc for p in _seeall_phrases)
            # "no" matched as a whole word so "now"/"another" don't false-decline
            _is_decline = (
                bool(re.search(r"\bno\b", _sc))
                or any(w in _sc for w in _decline_w)
            )
            _named_offered_area = bool(_stretch_loc and _stretch_loc in _sc)
            _accepts = (
                _named_offered_area
                or any(p in _sc for p in _accept_phrases)
                or any(w in _sc for w in _yes_w)
            )

            # 1. Explicit "see all" → hand to the see-all-tenant flow
            if _is_seeall:
                _saved2["awaiting_see_all_tenant"] = True
                convo.data_json = json.dumps(_saved2)
                db.commit()
                await send_meta_message(
                    sender_id,
                    f"Let me pull up our other "
                    f"options, {first_name}.\n\n"
                    f"Reply *Yes* to see everything we have.",
                    phone_number_id=_send_pid, access_token=_send_token,
                )
                return

            # 2. Explicit decline → partner-network referral
            if _is_decline:
                _saved2["awaiting_referral_permission"] = True
                convo.data_json = json.dumps(_saved2)
                db.commit()
                await send_meta_message(
                    sender_id,
                    f"Understood, {first_name}. 🤝\n\n"
                    f"May I check our partner network? "
                    f"Every listing shows its verification details.\n\n"
                    f"Reply *Yes* to search the wider network.",
                    phone_number_id=_send_pid, access_token=_send_token,
                )
                return

            # 3. Acceptance (named area / natural phrase / yes-word) → show listing
            if _accepts and _lst:
                _p = _lst.price or 0
                _p_fmt = f"₦{_p/1_000_000:.0f}M" if _p >= 1_000_000 else f"₦{_p:,}"
                _b = _factual_badges(_lst)
                _b_line = " · ".join(_b) if _b else "Verification details on the listing"
                _base_url = os.getenv("BASE_URL", "https://est8go-api.onrender.com")
                await send_meta_message(
                    sender_id,
                    f"Excellent choice, {first_name}! 🎯\n\n"
                    f"*{_lst.title}*\n"
                    f"📍 {(_lst.location or '').title()}\n"
                    f"💰 *{_p_fmt}*\n"
                    f"🛡️ {_b_line}\n\n"
                    f"🔗 View full details:\n{_base_url}/public/property/{_lst.id}\n\n"
                    f"Would you like to schedule a site inspection? 📅",
                    phone_number_id=_send_pid, access_token=_send_token,
                )
                _saved2["last_viewed_id"] = _lst.id
                _saved2["last_viewed_title"] = _lst.title or ""
                # Accepting a stretch option in a DIFFERENT area must update
                # location so the consultant brief, inspection alert and any
                # re-search reflect what the buyer actually chose — not the
                # original failed-search area.
                _saved2["location"] = (_lst.location or _saved2.get("location"))
                convo.data_json = json.dumps(_saved2)
                convo.funnel_stage = "commitment"
                convo.state = "HANDOFF"
                db.commit()
                return

            # 4. Fallback → partner-network referral
            _saved2["awaiting_referral_permission"] = True
            convo.data_json = json.dumps(_saved2)
            db.commit()
            await send_meta_message(
                sender_id,
                f"Understood, {first_name}. 🤝\n\n"
                f"May I check our partner network? "
                f"Every listing shows its verification details.\n\n"
                f"Reply *Yes* to search the wider network.",
                phone_number_id=_send_pid, access_token=_send_token,
            )
            return

        # ── REFERRAL PERMISSION HANDLER ───────────────────────────────
        if _saved2.get("awaiting_referral_permission"):
            _rpc = text_body.strip().lower()
            _yes_rp = {"yes", "ok", "sure", "go ahead", "check", "search",
                       "yes please", "proceed", "absolutely"}

            if any(w in _rpc for w in _yes_rp):
                _saved2.pop("awaiting_referral_permission", None)
                _ref_ptype = _saved2.get("property_type", "")
                _ref_budget = _saved2.get("budget_max") or _saved2.get("budget")
                _ref_loc = (_saved2.get("location") or "").lower()
                _ref_city = None
                for _city_name in ["abuja", "lagos", "port harcourt", "enugu", "ibadan"]:
                    if _city_name in _ref_loc:
                        _ref_city = _city_name
                        break
                try:
                    from app.listings.models import Listing as _RL
                    _rq = db.query(_RL).filter(
                        _RL.tenant_id != tenant_id,
                        _RL.status == "verified",
                        _RL.trust_score > 30,
                    )
                    if _ref_ptype:
                        _rq = _rq.filter(_RL.property_type.ilike(f"%{_ref_ptype}%"))
                    if _ref_budget:
                        _rq = _rq.filter(_RL.price <= int(_ref_budget))
                    if _ref_city:
                        _rq = _rq.filter(_RL.location.ilike(f"%{_ref_city}%"))
                    _ref_listing = _rq.order_by(_RL.trust_score.desc()).first()

                    if _ref_listing:
                        _rp_val = _ref_listing.price or 0
                        _rp_range = (
                            f"₦{(_rp_val * 0.9)/1_000_000:.0f}M – ₦{(_rp_val * 1.1)/1_000_000:.0f}M"
                            if _rp_val >= 1_000_000 else f"₦{_rp_val:,}"
                        )
                        _city_show = _ref_city.title() if _ref_city else "same city"
                        _ref_badges = _factual_badges(_ref_listing)
                        _ref_b_line = " · ".join(_ref_badges) if _ref_badges else "Verification details on the listing"
                        _ref_msg = (
                            f"Good news, {first_name}! 🎯\n\n"
                            f"I found a match in our wider network:\n\n"
                            f"🏠 {(_ref_listing.property_type or 'Property').title()} in {_city_show}\n"
                            f"💰 Around {_rp_range}\n"
                            f"🛡️ {_ref_b_line}\n\n"
                            f"A consultant will share the full details with you directly.\n\n"
                            f"Shall I connect you now? 📞"
                        )
                        _saved2["awaiting_consultant"] = True
                        _saved2["referral_listing_id"] = _ref_listing.id
                        convo.data_json = json.dumps(_saved2)
                        convo.funnel_stage = "commitment"
                        db.commit()
                        await send_meta_message(sender_id, _ref_msg, phone_number_id=_send_pid, access_token=_send_token)
                    else:
                        _base_r = os.getenv("BASE_URL", "https://est8go-api.onrender.com")
                        _slug_r = tenant_profile.get("slug", "")
                        await send_meta_message(
                            sender_id,
                            f"I've searched our entire network, {first_name}.\n\n"
                            f"Two options:\n\n"
                            f"1️⃣ *Browse our full vault*, you may find something I missed:\n"
                            f"👉 {_base_r}/public/{_slug_r}\n\n"
                            f"2️⃣ *Speak to a consultant*, they have access to off-market "
                            f"deals not yet listed online.\n\n"
                            f"Which would you prefer?",
                            phone_number_id=_send_pid, access_token=_send_token,
                        )
                        _saved2["awaiting_last_resort"] = True
                        convo.data_json = json.dumps(_saved2)
                        db.commit()
                except Exception as _re_err:
                    logger.error(f"Referral search failed: {_re_err}")
            else:
                _saved2.pop("awaiting_referral_permission", None)
                # Route the 1-4 menu through the existing no-results handler
                # so "1" is read as a menu choice, not parsed as a ₦1M budget.
                _saved2["awaiting_no_results_choice"] = True
                _saved2["no_results_location"] = _saved2.get("location", "")
                _saved2["no_results_type"] = _saved2.get("property_type", "")
                _saved2["no_results_budget"] = (
                    _saved2.get("budget_max") or _saved2.get("budget")
                )
                convo.data_json = json.dumps(_saved2)
                db.commit()
                await send_meta_message(
                    sender_id,
                    f"No problem, {first_name}. 😊\n\n"
                    f"Would you like to:\n\n"
                    f"1️⃣ *Try a different area*, tell me another location\n"
                    f"2️⃣ *Adjust your budget*, tell me your new range\n"
                    f"3️⃣ *Change property type*: Land · House · Apartment\n"
                    f"4️⃣ *Start fresh*, say *New Search*",
                    phone_number_id=_send_pid, access_token=_send_token,
                )
            return

        # ── CONSULTANT CONNECTION HANDLER ─────────────────────────────
        if _saved2.get("awaiting_consultant"):
            _cc = text_body.strip().lower()
            _yes_cc = {"yes", "ok", "sure", "connect", "yes please",
                       "go ahead", "connect me", "absolutely"}
            if any(w in _cc for w in _yes_cc):
                _saved2.pop("awaiting_consultant", None)
                _cref_id = _saved2.pop("referral_listing_id", None)
                _cptype = (_saved2.get("property_type") or "property").title()
                _cloc = (_saved2.get("location") or "any area").title()
                _cbudget = _saved2.get("budget_max") or _saved2.get("budget")
                _cbudget_str = f"₦{int(_cbudget)/1_000_000:.0f}M" if _cbudget else "not specified"
                _cbedrooms = _saved2.get("bedrooms", "")
                _cpurpose = _saved2.get("purpose", "not specified")
                _cbed_str = f"{_cbedrooms} bedrooms" if _cbedrooms and _cbedrooms != "any" else ""

                _buyer_brief = (
                    f"🔔 *NEW LEAD — CONSULTANT REQUIRED*\n\n"
                    f"👤 Buyer: {first_name} ({whatsapp_name})\n"
                    f"📱 Contact: {sender_id}\n\n"
                    f"📋 *Search Brief:*\n"
                    f"• Purpose: {_cpurpose.title()}\n"
                    f"• Property: {_cptype}{' ' + _cbed_str if _cbed_str else ''}\n"
                    f"• Area: {_cloc}\n"
                    f"• Budget: {_cbudget_str}\n"
                )
                if _cref_id:
                    _cref_lst = db.get(Listing, _cref_id)
                    if _cref_lst:
                        _crp = _cref_lst.price or 0
                        _crp_fmt = f"₦{_crp/1_000_000:.0f}M" if _crp >= 1_000_000 else f"₦{_crp:,}"
                        _buyer_brief += (
                            f"\n🏠 *Matched Listing:*\n"
                            f"{_cref_lst.title}\n"
                            f"📍 {(_cref_lst.location or '').title()}\n"
                            f"💰 {_crp_fmt}\n"
                            f"🛡️ Trust: {_cref_lst.trust_score}/100\n"
                        )
                _buyer_brief += "\n⚡ Buyer is ready to proceed. Please reach out within 2 hours."

                try:
                    await alert_realtor_of_lead(
                        db, _cref_id or 0, sender_id, biz_name,
                        phone_number_id=_send_pid,
                        custom_message=_buyer_brief,
                        access_token=_send_token,
                    )
                except Exception as _cae:
                    logger.warning(f"Consultant alert failed: {_cae}")
                    _tenant_wa = getattr(tenant, "whatsapp_phone_number", None)
                    if _tenant_wa:
                        try:
                            await send_meta_message(
                                _tenant_wa, _buyer_brief,
                                phone_number_id=_send_pid,
                                access_token=_send_token,
                            )
                        except Exception:
                            pass

                await send_meta_message(
                    sender_id,
                    f"You're all set, {first_name}! ✅\n\n"
                    f"Your search brief has been sent to our consultant:\n\n"
                    f"📋 *{_cptype}* in *{_cloc}*\n"
                    f"💰 Budget: *{_cbudget_str}*\n\n"
                    f"They will reach out within *2 hours* with full details on the options "
                    f"that match your exact requirements.\n\n"
                    f"Please keep your phone available. 📱\n\n"
                    f"Thank you for choosing *{biz_name}*, where every listing shows its "
                    f"verification details before it reaches you. 🛡️",
                    phone_number_id=_send_pid, access_token=_send_token,
                )
                convo.data_json = json.dumps(_saved2)
                convo.funnel_stage = "closed"
                convo.state = "CLOSED"
                convo.lead_score = 90
                convo.last_active_at = datetime.now(timezone.utc).replace(tzinfo=None)
                db.commit()
            else:
                _saved2.pop("awaiting_consultant", None)
                _saved2.pop("referral_listing_id", None)
                convo.data_json = json.dumps(_saved2)
                db.commit()
                await send_meta_message(
                    sender_id,
                    f"No problem, {first_name}. 😊\n\n"
                    f"Is there anything else I can help you with?\n\n"
                    f"Say *New Search* to search for a different property, "
                    f"or *Menu* to see all options.",
                    phone_number_id=_send_pid, access_token=_send_token,
                )
            return

        # ── LAST RESORT HANDLER ───────────────────────────────────────
        if _saved2.get("awaiting_last_resort"):
            _lrc = text_body.strip().lower()
            _saved2.pop("awaiting_last_resort", None)
            if "1" in _lrc or "browse" in _lrc or "vault" in _lrc:
                _base_lr = os.getenv("BASE_URL", "https://est8go-api.onrender.com")
                _slug_lr = tenant_profile.get("slug", "")
                convo.data_json = json.dumps(_saved2)
                db.commit()
                await send_meta_message(
                    sender_id,
                    f"Here's our full property vault, {first_name}:\n\n"
                    f"👉 {_base_lr}/public/{_slug_lr}\n\n"
                    f"Every listing shows its verification details. "
                    f"Take your time browsing. 😊\n\n"
                    f"Reply *I'm interested* on any listing and I'll connect you immediately.",
                    phone_number_id=_send_pid, access_token=_send_token,
                )
            else:
                _saved2["awaiting_consultant"] = True
                convo.data_json = json.dumps(_saved2)
                db.commit()
                await send_meta_message(
                    sender_id,
                    f"Great choice, {first_name}. 📞\n\n"
                    f"Our property consultants have access to off-market deals "
                    f"not yet listed online.\n\n"
                    f"Shall I connect you now?",
                    phone_number_id=_send_pid, access_token=_send_token,
                )
            return

        # ── NO RESULTS MENU HANDLER ──────────────────────────────────
        _saved_nr = json.loads(convo.data_json or "{}")
        if _saved_nr.get("awaiting_no_results_choice"):
            _nr_choice = text_body.strip().lower()
            _nr_clean = re.sub(r'[^a-z0-9 ]', '', _nr_choice).strip()
            _nr_nearby_list = _saved_nr.get("no_results_nearby", [])
            _nr_orig_loc = _saved_nr.get("no_results_location", "")
            _nr_orig_type = _saved_nr.get("no_results_type", "")
            _nr_orig_budget = _saved_nr.get("no_results_budget")

            # Clear menu state flags
            _saved_nr.pop("awaiting_no_results_choice", None)
            _saved_nr.pop("no_results_location", None)
            _saved_nr.pop("no_results_type", None)
            _saved_nr.pop("no_results_budget", None)
            _saved_nr.pop("no_results_nearby", None)

            if _nr_choice in ("1", "search nearby", "nearby", "search a nearby area"):
                if _nr_nearby_list:
                    nearby_list_str = "\n".join(
                        f"{i + 1}. *{area.title()}*"
                        for i, area in enumerate(_nr_nearby_list)
                    )
                    await send_meta_message(
                        sender_id,
                        f"Which nearby area would you like me to search, "
                        f"{first_name}? 📍\n\n"
                        f"{nearby_list_str}\n\n"
                        f"Just reply with the area name.",
                        phone_number_id=_send_pid, access_token=_send_token,
                    )
                else:
                    await send_meta_message(
                        sender_id,
                        f"Which area would you like to search instead, "
                        f"{first_name}? Tell me the neighbourhood.",
                        phone_number_id=_send_pid, access_token=_send_token,
                    )
                _saved_nr["property_type"] = _nr_orig_type
                _saved_nr["budget"] = _nr_orig_budget
                _saved_nr["budget_max"] = _nr_orig_budget
                convo.data_json = json.dumps(_saved_nr)
                convo.state = "ACTIVE"
                db.commit()
                return

            elif _nr_choice in ("2", "adjust my budget", "adjust budget", "change budget"):
                await send_meta_message(
                    sender_id,
                    f"What is your revised budget, {first_name}? 💰\n\n"
                    f"(e.g. '40M', '50M to 80M', '₦45,000,000')",
                    phone_number_id=_send_pid, access_token=_send_token,
                )
                _saved_nr["property_type"] = _nr_orig_type
                _saved_nr["location"] = _nr_orig_loc
                _saved_nr.pop("budget", None)
                _saved_nr.pop("budget_max", None)
                convo.data_json = json.dumps(_saved_nr)
                convo.state = "ACTIVE"
                db.commit()
                return

            elif _nr_choice in ("3", "change property type", "change type"):
                await send_meta_message(
                    sender_id,
                    f"What type of property are you open to, {first_name}? 🏠\n\n"
                    f"Land · House · Apartment",
                    phone_number_id=_send_pid, access_token=_send_token,
                )
                _saved_nr["location"] = _nr_orig_loc
                _saved_nr["budget"] = _nr_orig_budget
                _saved_nr["budget_max"] = _nr_orig_budget
                _saved_nr.pop("property_type", None)
                convo.data_json = json.dumps(_saved_nr)
                convo.state = "ACTIVE"
                db.commit()
                return

            elif _nr_clean in ("4", "start a new search", "new search", "start fresh"):
                convo.data_json = json.dumps({})
                convo.funnel_stage = "awareness"
                convo.state = "ACTIVE"
                convo.lead_score = 0
                db.commit()
                import random as _rand2
                _fresh_variants2 = [
                    (
                        f"Consider it done, {first_name}. 🔄\n\n"
                        f"I've cleared your previous search "
                        f"and opened a fresh connection to "
                        f"our vault.\n\n"
                        f"What are you looking for this time?\n\n"
                        f"🌱 *Land*: prime plots for "
                        f"development or investment\n"
                        f"🏠 *House*: fully detached, "
                        f"semi-detached or duplex\n"
                        f"🏢 *Apartment*: modern flats "
                        f"and studio units\n\n"
                        f"Or simply describe what you "
                        f"have in mind. 😊"
                    ),
                    (
                        f"Fresh start, {first_name}. ✨\n\n"
                        f"Our vault is open "
                        f"and ready.\n\n"
                        f"What type of property are you "
                        f"searching for today?\n\n"
                        f"🌱 *Land*: build or invest\n"
                        f"🏠 *House*: move-in ready "
                        f"or off-plan\n"
                        f"🏢 *Apartment*: city living "
                        f"at its finest\n\n"
                        f"Just tell me what you need."
                    ),
                    (
                        f"All cleared, {first_name}. "
                        f"Let's find you something "
                        f"exceptional. 🏡\n\n"
                        f"Every property I show you comes with "
                        f"its verification details on file, "
                        f"so no fake listings and no wasted trips.\n\n"
                        f"What are we searching for?\n\n"
                        f"🌱 *Land*\n"
                        f"🏠 *House*\n"
                        f"🏢 *Apartment*"
                    ),
                ]
                await send_meta_message(
                    sender_id,
                    _rand2.choice(_fresh_variants2),
                    phone_number_id=_send_pid, access_token=_send_token,
                )
                return

            else:
                # Treat as area name — search it directly
                _saved_nr["property_type"] = _nr_orig_type
                _saved_nr["budget"] = _nr_orig_budget
                _saved_nr["budget_max"] = _nr_orig_budget
                _saved_nr["location"] = text_body.strip().lower()
                convo.data_json = json.dumps(_saved_nr)
                convo.state = "ACTIVE"
                db.commit()
                # Fall through to intent pipeline which will trigger search

        # ── PHONE NUMBER HANDLER ─────────────
        from app.conversations.intent_filter import (
            detect_phone_number
        )
        _phone = detect_phone_number(text_body)
        if _phone:
            _ph_data = json.loads(convo.data_json or "{}")
            _ph_data["buyer_phone"] = _phone
            convo.data_json = json.dumps(_ph_data)
            db.commit()

            # Check if buyer has viewed a listing
            _ph_listing_id = _ph_data.get("last_viewed_id")

            if _ph_listing_id:
                # Buyer shared number on a property
                # — alert agent to call them
                try:
                    _ph_listing = db.get(
                        Listing, _ph_listing_id
                    )
                    _ph_title = (
                        _ph_listing.title
                        if _ph_listing
                        else "the property"
                    )
                    await alert_realtor_of_lead(
                        db,
                        _ph_listing_id,
                        sender_id,
                        biz_name,
                        phone_number_id=_send_pid,
                        access_token=_send_token,
                        custom_message=(
                            f"🔔 *CALLBACK REQUEST*\n\n"
                            f"👤 Buyer: {first_name}\n"
                            f"📱 They shared: {_phone}\n"
                            f"📱 WhatsApp: wa.me/{sender_id}\n\n"
                            f"🏠 Property: {_ph_title}\n\n"
                            f"⚡ Buyer wants a callback. "
                            f"Please call within 2 hours."
                        ),
                    )
                except Exception as _phe:
                    logger.warning(
                        f"Phone callback alert failed: {_phe}"
                    )

                await send_meta_message(
                    sender_id,
                    f"Got it, {first_name}! 📱\n\n"
                    f"I've passed your number to our "
                    f"consultant. They will call you "
                    f"within *2 hours*.\n\n"
                    f"In the meantime, is there anything "
                    f"else you'd like to know about "
                    f"the property?",
                    phone_number_id=_send_pid, access_token=_send_token,
                )
                return
            else:
                # No listing viewed yet — acknowledge
                # and continue qualifying
                await send_meta_message(
                    sender_id,
                    f"Thanks, {first_name}! 📱\n\n"
                    f"I've noted your number. To help "
                    f"our consultant prepare before "
                    f"they call, let me quickly find "
                    f"you the right property.\n\n"
                    f"What type of property are you "
                    f"looking for: Land, House, "
                    f"or Apartment?",
                    phone_number_id=_send_pid, access_token=_send_token,
                )
                return

        # --- 8. INTENT PIPELINE ---
        pipe = add_message_service(convo.id, text_body, tenant_id, db)
        # Merge pipe prefs with saved conversation prefs
        # so last_viewed_id is always available

        saved_prefs = _json.loads(convo.data_json or "{}")
        pipe_prefs = pipe.get("prefs", {})
        saved_prefs.update({k: v for k, v in pipe_prefs.items() if v})
        prefs = saved_prefs
        intent = pipe.get("intent", "unknown")

        # Update lead score and funnel stage after every message
        update_conversation_intelligence(convo, prefs, intent, db)

        # --- 8b. PROPERTY PAGE LEAD FAST-TRACK ---
        if intent == "property_page_lead":
            _lid = pipe.get("listing_id")
            if _lid:
                try:
                    _lst = (
                        db.query(Listing)
                        .filter(Listing.id == _lid, Listing.tenant_id == tenant_id)
                        .first()
                    )
                    if not _lst:
                        await send_meta_message(
                            sender_id,
                            f"Hi {first_name}! 👋\n\n"
                            f"I could not find that listing. "
                            f"It may have been removed or is no longer available.\n\n"
                            f"What property are you looking for? "
                            f"I can help you find options.",
                            phone_number_id=_send_pid, access_token=_send_token,
                        )
                        return

                    # Fast-track to COMMITMENT
                    _data = json.loads(convo.data_json or "{}")
                    _data["last_viewed_id"]    = _lst.id
                    _data["last_viewed_title"] = _lst.title
                    _data["location"]          = _lst.location
                    _data["property_type"]     = _lst.property_type
                    _data["budget_max"]        = _lst.price
                    convo.data_json            = json.dumps(_data)
                    convo.funnel_stage         = "commitment"
                    convo.lead_score           = 75
                    convo.last_active_at       = datetime.now(timezone.utc).replace(tzinfo=None)
                    db.commit()

                    _price = _lst.price or 0
                    if _price >= 1_000_000_000:
                        _price_fmt = f"₦{_price/1_000_000_000:.1f}B"
                    elif _price >= 1_000_000:
                        _price_fmt = f"₦{_price/1_000_000:.0f}M"
                    else:
                        _price_fmt = f"₦{_price:,}"

                    _b = _factual_badges(_lst)
                    _b_line = " · ".join(_b) if _b else "Verification details on the listing"

                    await send_meta_message(
                        sender_id,
                        f"Hi {first_name}! 👋\n\n"
                        f"Excellent choice. You have selected an Est8Go listing:\n\n"
                        f"*{_lst.title}*\n"
                        f"📍 {(_lst.location or '').title()}\n"
                        f"💰 *{_price_fmt}*\n"
                        f"🛡️ {_b_line}\n\n"
                        f"This property's verification details are on file. Ready to arrange your inspection.\n\n"
                        f"Would you like to schedule a site visit? "
                        f"Just give me a preferred time and our agent will confirm. 📅",
                        phone_number_id=_send_pid, access_token=_send_token,
                    )

                    # Alert realtor immediately
                    try:
                        await alert_realtor_of_lead(db, _lid, sender_id, biz_name, phone_number_id=_send_pid, access_token=_send_token)
                    except Exception as _ae:
                        logger.warning(f"Property page lead realtor alert failed: {_ae}")

                except Exception as _ppe:
                    logger.error(f"Property page lead handler failed: {_ppe}")
            return

        # --- 8c. COMPARISON HANDLER ---
        if intent == "comparison":
            _data = json.loads(convo.data_json or "{}")
            _match_ids = _data.get("last_match_ids", [])
            if not _match_ids:
                await send_meta_message(
                    sender_id,
                    f"Please run a property search first, {first_name}, "
                    f"and I'll compare the results for you.",
                    phone_number_id=_send_pid, access_token=_send_token,
                )
            elif len(_match_ids) == 1:
                await send_meta_message(
                    sender_id,
                    "There is only one property in your last search. "
                    "Would you like more details about it?",
                    phone_number_id=_send_pid, access_token=_send_token,
                )
            else:
                _cmp_listings = (
                    db.query(Listing)
                    .filter(Listing.id.in_(_match_ids))
                    .all()
                )
                # Sort by trust desc so options 1-N are already ranked
                _cmp_listings.sort(key=lambda x: (x.trust_score or 0), reverse=True)
                _cmp_text = build_comparison_message(_cmp_listings, first_name)
                await send_meta_message(sender_id, _cmp_text, phone_number_id=_send_pid, access_token=_send_token)
            return

        # --- 8c.5 GPT MISS HANDLER ---
        _miss_count = prefs.get("gpt_miss_count", 0)
        if _miss_count >= 2:
            prefs["gpt_miss_count"] = 0
            convo.data_json = json.dumps(prefs)
            db.commit()
            await send_meta_message(
                sender_id,
                f"Let me make this easy, {first_name}. 😊\n\n"
                f"Just answer these two quick questions:\n\n"
                f"1️⃣ *Which area?*\n"
                f"   e.g. Lekki, Guzape, GRA, Maitama\n\n"
                f"2️⃣ *What is your budget?*\n"
                f"   e.g. 50M, 80M, 120M",
                phone_number_id=_send_pid, access_token=_send_token,
            )
            return

        # --- 8d. LOST BUYER HANDLER ---
        if intent == "lost_buyer":
            _data = json.loads(convo.data_json or "{}")
            _loc = (_data.get("location") or "").title()
            _ptype = (_data.get("property_type") or "property").title()
            _has_budget = bool(_data.get("budget") or _data.get("budget_max"))

            if _loc and not _has_budget:
                _guidance = (
                    f"No problem, {first_name}! Let me help you narrow it down. 😊\n\n"
                    f"You're looking for a *{_ptype}* in *{_loc}*.\n\n"
                    f"What is your budget? "
                    f"(e.g. '30M', '50M to 80M', '₦45,000,000')"
                )
            elif _has_budget and not _loc:
                _guidance = (
                    f"Of course, {first_name}! 😊\n\n"
                    f"Which area would you like to search? "
                    f"We cover Abuja, Lagos, Port Harcourt and more.\n\n"
                    f"Just tell me the city or specific area."
                )
            else:
                _guidance = (
                    f"Here's what you can do, {first_name}:\n\n"
                    f"1️⃣ *Try a nearby area*: e.g. Asokoro, Apo, Maitama\n"
                    f"2️⃣ *Adjust your budget*, tell me a new range\n"
                    f"3️⃣ *Change property type*: Land, House or Apartment\n"
                    f"4️⃣ *Start fresh*, say *New Search*\n\n"
                    f"What works best for you?"
                )
            await send_meta_message(sender_id, _guidance, phone_number_id=_send_pid, access_token=_send_token)
            return

        # --- 8e. AVAILABILITY QUESTION ---
        if intent == "availability":
            _av_data = json.loads(convo.data_json or "{}")
            _av_id = _av_data.get("last_viewed_id")
            if _av_id:
                _av_lst = db.get(Listing, int(_av_id)) if str(_av_id).isdigit() else None
                if _av_lst:
                    await send_meta_message(
                        sender_id,
                        f"Yes, {first_name}! *{_av_lst.title}* "
                        f"is still available. ✅\n\n"
                        f"Would you like to schedule a site "
                        f"inspection? Just say *Yes*. 📅",
                        phone_number_id=_send_pid,
                        access_token=_send_token,
                    )
                    convo.last_active_at = datetime.now(
                        timezone.utc
                    ).replace(tzinfo=None)
                    db.commit()
                    return
            # No property in view — guide them
            await send_meta_message(
                sender_id,
                f"Happy to check availability, {first_name}! "
                f"Which property are you asking about? "
                f"Tell me the area and budget and I'll "
                f"pull up options. 😊",
                phone_number_id=_send_pid,
                access_token=_send_token,
            )
            return

        # --- 8f. MEDIA REQUEST ---
        if intent == "media_request":
            _md_data = json.loads(convo.data_json or "{}")
            _md_id = _md_data.get("last_viewed_id")
            if _md_id:
                _md_lst = db.get(Listing, int(_md_id)) if str(_md_id).isdigit() else None
                if _md_lst:
                    _base = os.getenv("BASE_URL", "https://est8go-api.onrender.com")
                    _link = f"{_base}/public/property/{_md_lst.id}"
                    try:
                        from app.services.chatbot.message_builder import build_media_redirect
                        _md_msg = build_media_redirect(first_name, biz_name, _link)
                    except Exception:
                        _md_msg = (
                            f"All photos for "
                            f"*{_md_lst.title}* are here, "
                            f"{first_name}: 📸\n\n{_link}\n\n"
                            f"Would you like to schedule a "
                            f"site inspection? 📅"
                        )
                    await send_meta_message(
                        sender_id, _md_msg,
                        phone_number_id=_send_pid,
                        access_token=_send_token,
                    )
                    convo.last_active_at = datetime.now(
                        timezone.utc
                    ).replace(tzinfo=None)
                    db.commit()
                    return
            await send_meta_message(
                sender_id,
                f"I'd love to show you photos, {first_name}! "
                f"Which property? Tell me the area and budget "
                f"and I'll find listings with full "
                f"photos. 😊",
                phone_number_id=_send_pid,
                access_token=_send_token,
            )
            return

        # --- 9. OBJECTION HANDLER ---
        if intent == "objection":
            objection_key = pipe.get("objection_key", "objection_stalling")

            if objection_key == "objection_budget_mismatch":
                from app.conversations.intent_filter import extract_budget_from_text
                new_budget = extract_budget_from_text(text_body)
                _data = json.loads(convo.data_json or "{}")

                if new_budget:
                    _data["budget"] = new_budget
                    _data["budget_max"] = new_budget
                    convo.data_json = json.dumps(_data)
                    convo.state = "ACTIVE"
                    db.commit()

                    budget_fmt = f"₦{new_budget / 1_000_000:.0f}M"
                    _bm_location = (_data.get("location") or "").title()

                    await send_meta_message(
                        sender_id,
                        f"Understood, {first_name}. "
                        f"Let me search within *{budget_fmt}* "
                        f"for you in *{_bm_location}*. 🔍",
                        phone_number_id=_send_pid, access_token=_send_token,
                    )

                    search_result = execute_premium_search(db, tenant_id, _data)
                    matches = search_result.get("data", [])

                    if matches:
                        summary = build_property_summary(
                            matches[0], matches,
                            search_result.get("total_count", 0),
                            first_name,
                        )
                        await _send_property_card(
                            db, sender_id, matches[0], summary,
                            phone_number_id=_send_pid, access_token=_send_token,
                        )
                        _data["last_viewed_id"] = matches[0].id
                        _data["last_viewed_title"] = matches[0].title
                        _data["last_match_ids"] = [m.id for m in matches]
                        convo.data_json = json.dumps(_data)
                        convo.state = "HANDOFF"
                        convo.funnel_stage = "commitment"
                        convo.last_active_at = datetime.now(timezone.utc).replace(
                            tzinfo=None
                        )
                        db.commit()
                    else:
                        await send_meta_message(
                            sender_id,
                            f"I searched thoroughly, {first_name}, "
                            f"but there are no listings "
                            f"in *{_bm_location}* within *{budget_fmt}* "
                            f"right now.\n\n"
                            f"A few options:\n\n"
                            f"1️⃣ *Expand your search area*, "
                            f"nearby areas may have options\n"
                            f"2️⃣ *Adjust your budget slightly*, "
                            f"tell me your maximum stretch\n"
                            f"3️⃣ *Change property type*, "
                            f"Land is often more affordable\n\n"
                            f"What would you prefer?",
                            phone_number_id=_send_pid, access_token=_send_token,
                        )
                        _data.pop("location", None)
                        convo.data_json = json.dumps(_data)
                        convo.state = "ACTIVE"
                        convo.funnel_stage = "verification"
                        db.commit()
                else:
                    current_price = 0
                    _last_id = _data.get("last_viewed_id")
                    if _last_id:
                        _viewed = db.get(Listing, _last_id)
                        if _viewed:
                            current_price = _viewed.price or 0

                    price_fmt = (
                        f"₦{current_price / 1_000_000:.0f}M"
                        if current_price >= 1_000_000
                        else "this property"
                    )

                    await send_meta_message(
                        sender_id,
                        f"I understand, {first_name}. "
                        f"{price_fmt} may be above your range.\n\n"
                        f"What is your maximum budget? "
                        f"I'll find you the best options "
                        f"within that figure. 💰\n\n"
                        f"(e.g. '30M', '₦45,000,000', '20M to 50M')",
                        phone_number_id=_send_pid, access_token=_send_token,
                    )
                    _data.pop("budget", None)
                    _data.pop("budget_max", None)
                    convo.data_json = json.dumps(_data)
                    convo.state = "ACTIVE"
                    db.commit()
                return

            last_id = prefs.get("last_viewed_id")
            trust_grade = "Verified"
            if last_id:
                viewed = db.get(Listing, last_id)
                grade_raw = (viewed.trust_grade or "") if viewed else ""
                if grade_raw and grade_raw != "ungraded":
                    trust_grade = grade_raw.title()
            response = get_objection_response(objection_key, first_name, biz_name, trust_grade)
            await send_meta_message(sender_id, response, phone_number_id=_send_pid, access_token=_send_token)
            return

        # Also trigger search if intent is search_ready
        if intent == "search_ready" and prefs.get("location") and prefs.get("budget"):
            pass  # falls through to search block below

        # --- 10. SEARCH TRIGGER ---
        # Only trigger search if intent is search_ready or unknown
        # Never re-trigger if buyer is objecting or agreeing
        if (
            prefs.get("location")
            and prefs.get("budget")
            and convo.state != "HANDOFF"
            and intent
            not in (
                "objection",
                "agreement",
                "filler",
                "greeting",
                "restart",
                "location_query",
                "property_type_query",
                "search_ready",
                "media_request",
                "availability",
                "property_page_lead",
            )
        ):
            try:
                # Acknowledge budget when it was just captured in this message
                budget_just_captured = (
                    pipe.get("intent") in ("price_query", "search_ready")
                    and pipe.get("prefs", {}).get("budget")
                    and not json.loads(convo.data_json or "{}").get("budget")
                )
                if budget_just_captured and prefs.get("location"):
                    _bval = prefs.get("budget", 0)
                    _bfmt = f"₦{_bval / 1_000_000:.0f}M"
                    _bloc = (prefs.get("location") or "").title()
                    _btype = (prefs.get("property_type") or "property").title()
                    await send_meta_message(
                        sender_id,
                        f"Perfect, {first_name}. "
                        f"Searching for *{_btype}* in "
                        f"*{_bloc}* within *{_bfmt}*. 🔍",
                        phone_number_id=_send_pid, access_token=_send_token,
                    )

                search_result = execute_premium_search(db, tenant_id, prefs)
                matches = search_result.get("data", [])
                total = search_result.get("total_count", 0)
                source = search_result.get("source", "none")

                # Auto-expand: if no results, silently search nearby areas
                if not matches:
                    location_lower = (prefs.get("location") or "").lower().strip()
                    from app.services.chatbot.message_builder import NEARBY_AREAS
                    nearby_areas = NEARBY_AREAS.get(location_lower, [])
                    for nearby_loc in nearby_areas[:3]:
                        expanded_prefs = {**prefs, "location": nearby_loc}
                        try:
                            expanded_result = execute_premium_search(db, tenant_id, expanded_prefs)
                            expanded_matches = expanded_result.get("data", [])
                            if expanded_matches:
                                matches = expanded_matches
                                total = expanded_result.get("total_count", 0)
                                source = expanded_result.get("source", "none")
                                prefs["_expanded_from"] = prefs.get("location", "")
                                prefs["_expanded_to"] = nearby_loc
                                break
                        except Exception:
                            continue

                if matches:
                    if source == "referral":
                        summary = build_referral_summary(matches[0], biz_name)
                    else:
                        summary = build_property_summary(
                            matches[0], matches, total, first_name
                        )
                    # Prepend expansion note if we searched a nearby area
                    if prefs.get("_expanded_from") and prefs.get("_expanded_to"):
                        expansion_note = (
                            f"No listings found in "
                            f"*{prefs['_expanded_from'].title()}* right now, "
                            f"but I found options in nearby "
                            f"*{prefs['_expanded_to'].title()}*:\n\n"
                        )
                        summary = expansion_note + summary
                        prefs.pop("_expanded_from", None)
                        prefs.pop("_expanded_to", None)

                    # Append negotiation context (days on market + price position)
                    _neg_note = _get_negotiation_note(matches[0], db)
                    if _neg_note:
                        summary += f"\n\n{_neg_note}"

                    await _send_property_card(
                        db, sender_id, matches[0], summary,
                        phone_number_id=_send_pid, access_token=_send_token,
                    )
                    # Lock state to HANDOFF — prevents search re-triggering
                    prefs["last_viewed_id"] = matches[0].id
                    prefs["last_viewed_title"] = matches[0].title or ""
                    prefs["last_match_ids"] = [m.id for m in matches]
                    convo.data_json = json.dumps(prefs)
                    convo.state = "HANDOFF"
                    convo.funnel_stage = "commitment"
                    convo.last_active_at = datetime.now(timezone.utc).replace(
                        tzinfo=None
                    )
                    db.commit()
                    logger.info(f"Saved last_viewed_id: {matches[0].id}")
                    return

                else:
                    await _no_results_cascade(
                        prefs, first_name, sender_id,
                        tenant_id, db, convo, platform_id,
                        tenant_profile, biz_name,
                        access_token=_send_token,
                    )
                    return

            except Exception as e:
                logger.error(f"Search Block Failure: {e}")
                await send_meta_message(sender_id, handle_logic_error("search_failure"), phone_number_id=_send_pid, access_token=_send_token)
                return
        # --- 11. KORA PERSONALITY & HANDSHAKE ---
        try:
            raw_reply = pipe.get("reply", "")
            final_reply = determine_bot_voice(
                raw_reply, text_body, first_name, tenant_profile
            )

            # Intercept completed_flag — trigger search instead of sending raw text
            if final_reply == "completed_flag" or raw_reply == "completed_flag":

                # GUARD: If buyer is in handshake stage,
                # they are confirming inspection time — do NOT re-trigger search
                if convo.funnel_stage == "handshake":
                    msg_lower = text_body.lower()
                    time_keywords = [
                        "tomorrow", "today", "monday", "tuesday",
                        "wednesday", "thursday", "friday", "saturday",
                        "sunday", "next week", "morning", "afternoon",
                        "evening", "noon", "weekend", "prompt", "sharp",
                        "o'clock", "oclock", "by", "around",
                        "january", "february", "march", "april", "may",
                        "june", "july", "august", "september", "october",
                        "november", "december",
                        "6am", "7am", "8am", "9am", "10am", "11am", "12pm",
                        "1pm", "2pm", "3pm", "4pm", "5pm", "6pm", "7pm",
                        "8pm", "9pm",
                    ]
                    has_time = any(kw in msg_lower for kw in time_keywords)
                    has_time_pattern = (
                        bool(re.search(r"\b\d{1,2}(:\d{2})?\s*(am|pm)\b", msg_lower, re.IGNORECASE))
                        or bool(re.search(r"\b\d{1,2}:\d{2}\b", msg_lower))
                        or bool(re.search(r"\b\d{1,2}\s*(am|pm)\b", msg_lower, re.IGNORECASE))
                        or bool(re.search(r"\b\d{1,2}\s*o'?clock\b", msg_lower, re.IGNORECASE))
                    )

                    if has_time or has_time_pattern:
                        convo.funnel_stage = "closed"
                        convo.state = "CLOSED"
                        db.commit()
                        data = json.loads(convo.data_json or "{}")
                        last_id = data.get("last_viewed_id")
                        listing_title = data.get("last_viewed_title") or "the property"
                        if last_id:
                            try:
                                lst = (
                                    db.query(Listing)
                                    .filter(Listing.id == int(last_id))
                                    .first()
                                )
                                if lst and lst.title:
                                    listing_title = lst.title
                            except Exception as e:
                                logger.error(f"Listing lookup failed: {e}")
                        confirmation = (
                            f"Perfect, {first_name}! ✅\n\n"
                            f"Your inspection for *{listing_title}* "
                            f"has been noted.\n\n"
                            f"Our lead agent will reach out shortly "
                            f"to confirm the exact time and meeting point. "
                            f"Please keep your phone available. 📱\n\n"
                            f"Thank you for choosing *{biz_name}*, "
                            f"where every listing shows its verification "
                            f"details before it reaches you. 🏠"
                        )
                        await send_meta_message(sender_id, confirmation, phone_number_id=_send_pid, access_token=_send_token)
                        return

                    else:
                        await send_meta_message(
                            sender_id,
                            f"What time works best for your inspection, "
                            f"{first_name}? "
                            f"(e.g. Tomorrow 10am, Friday afternoon) 📅",
                            phone_number_id=_send_pid, access_token=_send_token,
                        )
                        return

                if prefs.get("location") and prefs.get("budget"):
                    try:
                        search_result = execute_premium_search(db, tenant_id, prefs)
                        matches = search_result.get("data", [])
                        total = search_result.get("total_count", 0)
                        source = search_result.get("source", "none")
                        # Auto-expand: if no results, silently search nearby areas
                        if not matches:
                            location_lower = (prefs.get("location") or "").lower().strip()
                            from app.services.chatbot.message_builder import NEARBY_AREAS
                            nearby_areas = NEARBY_AREAS.get(location_lower, [])
                            for nearby_loc in nearby_areas[:3]:
                                expanded_prefs = {**prefs, "location": nearby_loc}
                                try:
                                    expanded_result = execute_premium_search(db, tenant_id, expanded_prefs)
                                    expanded_matches = expanded_result.get("data", [])
                                    if expanded_matches:
                                        matches = expanded_matches
                                        total = expanded_result.get("total_count", 0)
                                        source = expanded_result.get("source", "none")
                                        prefs["_expanded_from"] = prefs.get("location", "")
                                        prefs["_expanded_to"] = nearby_loc
                                        break
                                except Exception:
                                    continue
                        if matches:
                            if source == "referral":
                                summary = build_referral_summary(matches[0], biz_name)
                            else:
                                summary = build_property_summary(
                                    matches[0], matches, total, first_name
                                )
                            # Prepend expansion note if we searched a nearby area
                            if prefs.get("_expanded_from") and prefs.get("_expanded_to"):
                                expansion_note = (
                                    f"No listings found in "
                                    f"*{prefs['_expanded_from'].title()}* right now, "
                                    f"but I found options in nearby "
                                    f"*{prefs['_expanded_to'].title()}*:\n\n"
                                )
                                summary = expansion_note + summary
                                prefs.pop("_expanded_from", None)
                                prefs.pop("_expanded_to", None)
                            # Append negotiation context
                            _neg_note2 = _get_negotiation_note(matches[0], db)
                            if _neg_note2:
                                summary += f"\n\n{_neg_note2}"
                            await _send_property_card(
                                db, sender_id, matches[0], summary,
                                phone_number_id=_send_pid, access_token=_send_token,
                            )
                            prefs["last_viewed_id"] = matches[0].id
                            prefs["last_viewed_title"] = matches[0].title or ""
                            prefs["last_match_ids"] = [m.id for m in matches]
                            convo.data_json = json.dumps(prefs)
                            convo.state = "HANDOFF"
                            convo.funnel_stage = "commitment"
                            convo.last_active_at = datetime.now(timezone.utc).replace(
                                tzinfo=None
                            )
                            db.commit()
                            logger.info(f"Saved last_viewed_id: {matches[0].id}")
                        else:
                            await _no_results_cascade(
                                prefs, first_name, sender_id,
                                tenant_id, db, convo, platform_id,
                                tenant_profile, biz_name,
                                access_token=_send_token,
                            )
                    except Exception as e:
                        logger.error(f"Search from completed_flag failed: {e}")
                        await send_meta_message(
                            sender_id, handle_logic_error("search_failure"),
                            phone_number_id=_send_pid, access_token=_send_token,
                        )
                    return

                elif not (
                    prefs.get("location")
                    and prefs.get("budget")
                ):
                    # Funnel incomplete — ask next question
                    # instead of sending raw completed_flag
                    _fb = universal_fallback(
                        prefs, first_name, biz_name
                    )
                    await send_meta_message(
                        sender_id, _fb,
                        phone_number_id=_send_pid, access_token=_send_token,
                    )
                    return

            # Handshake trigger
            if raw_reply == "handshake_flag" and not prefs.get("last_viewed_id"):
                await send_meta_message(
                    sender_id,
                    get_executive_response("intent_location", first_name, biz_name),
                    phone_number_id=_send_pid, access_token=_send_token,
                )
                return
            if final_reply == "handshake_flag" or intent == "agreement":
                last_id = prefs.get("last_viewed_id")
                listing = db.get(Listing, last_id) if last_id else None
                if listing:
                    # Get agent details
                    _hs_agent_name = None
                    _hs_agent_role = None
                    _hs_agent_phone = None
                    try:
                        from app.users.models import User as _HsUser
                        _hs_agent = None
                        if listing.assigned_realtor_id:
                            _hs_agent = (
                                db.query(_HsUser)
                                .filter(
                                    _HsUser.id == listing.assigned_realtor_id,
                                    _HsUser.is_active == True,
                                )
                                .first()
                            )
                        if not _hs_agent:
                            _hs_agent = (
                                db.query(_HsUser)
                                .filter(
                                    _HsUser.tenant_id == tenant_id,
                                    _HsUser.role == "admin",
                                    _HsUser.is_active == True,
                                    _HsUser.phone_number.isnot(None),
                                )
                                .first()
                            )
                        if _hs_agent:
                            _hs_agent_name = (
                                _hs_agent.first_name
                                or _hs_agent.email.split("@")[0]
                            )
                            _hs_agent_role = "Lead Property Consultant"
                            _hs_agent_phone = _hs_agent.phone_number or None
                    except Exception:
                        pass

                    # Message 1 — inspection confirmed + agent details
                    _hs_msg = (
                        f"Perfect, {first_name}! 🎯\n\n"
                        f"Your inspection request for "
                        f"*{listing.title}* has been "
                        f"received and logged.\n\n"
                    )
                    if _hs_agent_name:
                        _hs_msg += (
                            f"*Your dedicated consultant:*\n"
                            f"👤 {_hs_agent_name}\n"
                        )
                        if _hs_agent_role:
                            _hs_msg += f"🏢 {_hs_agent_role}\n"
                        if _hs_agent_phone:
                            _hs_msg += f"📱 {_hs_agent_phone}\n"
                        _hs_msg += "\n"
                    _hs_msg += (
                        f"They will call you personally "
                        f"within *2 hours* to confirm "
                        f"your visit details.\n\n"
                        f"Please keep your phone "
                        f"available. 📱"
                    )
                    await send_meta_message(
                        sender_id, _hs_msg,
                        phone_number_id=_send_pid, access_token=_send_token,
                    )

                    # Message 2 — navigation + directions
                    _hs_nav = ""
                    if listing.latitude and listing.longitude:
                        _hs_nav = (
                            f"https://www.google.com/maps"
                            f"/dir/?api=1&destination="
                            f"{listing.latitude},"
                            f"{listing.longitude}"
                            f"&travelmode=driving"
                        )
                    _hs_dir = getattr(listing, "directions", None)
                    if _hs_nav or _hs_dir:
                        _hs_close = ""
                        if _hs_nav:
                            _hs_close += (
                                f"📍 *Property Location:*\n"
                                f"{_hs_nav}\n\n"
                            )
                        if _hs_dir:
                            _hs_close += (
                                f"🗺️ *How to find us:*\n"
                                f"{_hs_dir}\n\n"
                            )
                        _hs_close += (
                            f"Thank you for choosing "
                            f"*{biz_name}*, where every "
                            f"listing shows its "
                            f"verification details. 🛡️"
                        )
                        await send_meta_message(
                            sender_id, _hs_close,
                            phone_number_id=_send_pid, access_token=_send_token,
                        )

                    # Alert agent with full buyer brief
                    _hs_p = listing.price or 0
                    _hs_p_fmt = (
                        f"₦{_hs_p/1_000_000:.0f}M"
                        if _hs_p >= 1_000_000
                        else f"₦{_hs_p:,}"
                    )
                    _hs_alert = (
                        f"🔔 *NEW INSPECTION REQUEST*\n\n"
                        f"👤 *Buyer:* {first_name}\n"
                        f"📱 *WhatsApp:* wa.me/{sender_id}\n\n"
                        f"🏠 *Property:* {listing.title}\n"
                        f"📍 *Location:* "
                        f"{(listing.location or '').title()}\n"
                        f"💰 *Price:* {_hs_p_fmt}\n"
                        f"🛡️ *Trust Score:* "
                        f"{listing.trust_score or 0}/100\n\n"
                    )
                    if _hs_dir:
                        _hs_alert += (
                            f"🗺️ *Directions:*\n{_hs_dir}\n\n"
                        )
                    if listing.latitude and listing.longitude:
                        _hs_alert += (
                            f"📍 *Google Maps:*\n"
                            f"https://www.google.com/maps"
                            f"/dir/?api=1&destination="
                            f"{listing.latitude},"
                            f"{listing.longitude}\n\n"
                        )
                    _hs_alert += (
                        f"⚡ *Please call this buyer "
                        f"within 2 hours.*\n\n"
                        f"Tap to open their WhatsApp:\n"
                        f"wa.me/{sender_id}"
                    )
                    _hs_alert_ok = await alert_realtor_of_lead(
                        db,
                        last_id,
                        sender_id,
                        biz_name,
                        phone_number_id=_send_pid,
                        custom_message=_hs_alert,
                        access_token=_send_token,
                    )
                    if not _hs_alert_ok:
                        # Escalate to super-admin —
                        # buyer was promised a call
                        try:
                            from app.tenants.models import Tenant as _ET
                            _esc_msg = (
                                f"⚠️ *AGENT ALERT FAILED*\n\n"
                                f"Tenant: {biz_name} (ID {tenant_id})\n"
                                f"Buyer: {first_name} — wa.me/{sender_id}\n"
                                f"Listing ID: {last_id}\n\n"
                                f"The buyer was told an agent would "
                                f"call within 2 hours but the agent "
                                f"alert could not be delivered. "
                                f"Please follow up manually."
                            )
                            _super = os.getenv(
                                "SUPER_ADMIN_WHATSAPP", ""
                            )
                            if _super:
                                # Super-admin escalation: intentionally
                                # global number + global token (matched
                                # pair). Goes to super-admin, not buyer.
                                await send_meta_message(
                                    _super, _esc_msg,
                                )
                            logger.error(
                                f"AGENT ALERT FAILED for tenant "
                                f"{tenant_id}, buyer {sender_id}, "
                                f"listing {last_id}"
                            )
                        except Exception as _esc_e:
                            logger.error(
                                f"Escalation also failed: {_esc_e}"
                            )

                    # Close funnel — agent takes over
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
                    await send_meta_message(
                        sender_id,
                        get_executive_response(
                            "intent_location",
                            first_name,
                            biz_name,
                        ),
                        phone_number_id=_send_pid, access_token=_send_token,
                    )
                    return

            # Media request — include showroom link
            if intent == "media_request" and prefs.get("last_viewed_id"):
                listing = db.get(Listing, prefs.get("last_viewed_id"))
                if listing:
                    showroom_link = (
                        f"https://est8go-api.onrender.com/public/property/{listing.id}"
                    )
                    response = build_media_redirect(first_name, biz_name, showroom_link)
                    await send_meta_message(sender_id, response, phone_number_id=_send_pid, access_token=_send_token)
                    return

            # Never send raw flag strings or generic fallback
            if final_reply in ("I am here to assist you.", "filler_flag", ""):
                next_q = get_next_question(
                    prefs,
                    tenant_areas_by_budget=prefs.get("tenant_areas_in_budget", []),
                )
                if next_q:
                    await send_meta_message(sender_id, next_q, phone_number_id=_send_pid, access_token=_send_token)
                return

            # Detect bedrooms question and set flag
            # so the buyer's reply ("3") is captured as
            # bedrooms by the awaiting_bedrooms handler,
            # not mis-parsed as a ₦3M budget
            if final_reply and "how many bedrooms" in final_reply.lower():
                _bd = json.loads(convo.data_json or "{}")
                _bd["awaiting_bedrooms"] = True
                convo.data_json = json.dumps(_bd)
                db.commit()

            # Default voice deliver —
            # NEVER send raw flag strings
            if (
                not final_reply
                or final_reply.endswith("_flag")
                or final_reply.strip() in (
                    "completed_flag",
                    "handshake_flag",
                    "fresh_start_flag",
                    "filler_flag",
                    "resume_flag",
                    "trigger_global_search",
                    "property_page_lead_flag",
                )
            ):
                # Send universal fallback
                # instead of broken flag text
                _fb = universal_fallback(
                    prefs, first_name, biz_name
                )
                await send_meta_message(
                    sender_id, _fb,
                    phone_number_id=_send_pid, access_token=_send_token,
                )
            else:
                await send_meta_message(
                    sender_id, final_reply,
                    phone_number_id=_send_pid, access_token=_send_token,
                )

        except Exception as e:
            logger.error(f"❌ PERSONALITY ERROR: {e}")
            await send_meta_message(
                sender_id,
                "I'm still here! I had a small glitch, could you please "
                "say that again? 🙏",
                phone_number_id=_send_pid, access_token=_send_token,
            )

    except Exception as e:
        logger.error(f"❌ CRITICAL MASTER ERROR: {e}", exc_info=True)
        # Best-effort fallback — never
        # leave the buyer in silence
        try:
            _fb_sender = None
            _fb_pid = None
            # Recover sender_id and platform_id
            # if they were resolved
            try:
                _fb_sender = sender_id
            except Exception:
                _fb_sender = None
            try:
                _fb_pid = platform_id
            except Exception:
                _fb_pid = None
            try:
                _fb_name = first_name
            except Exception:
                _fb_name = "there"

            if _fb_sender:
                await send_meta_message(
                    _fb_sender,
                    f"I'm still here, {_fb_name}! 🙏\n\n"
                    f"I had a brief glitch. "
                    f"Could you tell me again what "
                    f"you're looking for?\n\n"
                    f"Just share the *area* and "
                    f"*budget* and I'll find you "
                    f"options.",
                    phone_number_id=_fb_pid,
                )
        except Exception as _fb_err:
            logger.error(
                f"Fallback send also failed: "
                f"{_fb_err}"
            )
