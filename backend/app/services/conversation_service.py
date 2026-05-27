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
    send_meta_carousel,
    prepare_meta_carousel,
)

# Logic Engines
from app.conversations.templates import is_filler, get_next_question
from app.conversations.brain import extract_preferences
from app.conversations.ai_fallback import is_company_faq, answer_company_faq
from app.company_profiles.models import CompanyProfile

# Intent Pre-Filter & Lead Scorer
from app.conversations.intent_filter import (
    classify_intent,
    calculate_lead_score,
    determine_funnel_stage,
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
    build_no_match_message,
    build_referral_summary,
    build_inspection_confirmation,
)
from app.services.chatbot.kora_behavior import determine_bot_voice
from app.services.chatbot.fallback_engine import handle_logic_error

# Tenant Resolver
from app.services.tenant_resolver import (
    resolve_tenant_from_webhook,
    extract_platform_id_from_webhook,
)

# In-memory deduplication set
_processed_messages: set = set()
logger = logging.getLogger(__name__)


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
        from datetime import timezone

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
            f"The verified inventory at *{biz_name}* has been updated since then.\n\n"
            f"Would you like to continue your previous search or explore fresh options?"
        )

    else:
        # Cold — near full re-qualify
        return (
            f"Welcome back to *{biz_name}*, {name}! 🏠\n\n"
            f"It's been a while — the market has moved and we have "
            f"exciting new verified listings available.\n\n"
            f"Shall we start fresh, or would you like me to recall your "
            f"previous preferences?"
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

    # ALWAYS merge extracted data immediately — before get_next_question
    if intent_result.extracted:
        for k, v in intent_result.extracted.items():
            if v:  # only update if value is not None/empty
                current_data[k] = v
        convo.data_json = json.dumps(current_data)
        db.commit()

    # If intent is known — return immediately without GPT
    if not intent_result.needs_gpt:
        next_q = (
            get_next_question(current_data) if not intent_result.extracted else None
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
            next_q = get_next_question(current_data)
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

    # Unknown intent — escalate to GPT
    updated_data = extract_preferences(text_clean, current_data)
    convo.data_json = json.dumps(updated_data)
    next_q = get_next_question(updated_data)

    if not next_q:
        convo.state = "HANDOFF"
        next_q = "completed_flag"

    db.commit()
    return {"reply": next_q, "prefs": updated_data, "intent": "gpt_extracted"}


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

        # Path A: WhatsApp
        if "messages" in value:
            msg_obj = value["messages"][0]
            sender_id = msg_obj.get("from")
            text_body = msg_obj.get("text", {}).get("body", "")
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

        # --- 3. CONVERSATION LOOKUP ---
        convo = (
            db.query(Conversation)
            .filter_by(external_user_id=sender_id, tenant_id=tenant_id)
            .order_by(Conversation.updated_at.desc())
            .first()
        )

        # --- 4. HUMAN-IN-THE-LOOP CHECK ---
        if convo and hasattr(convo, "is_bot_active") and not convo.is_bot_active:
            logger.info(f"👤 HITL: Bot inactive for {sender_id} — Realtor has control")
            return

        # --- 5. BUTTON HANDLER ---
        if btn_payload and "INTERESTED_IN_" in btn_payload:
            list_id = int(btn_payload.split("_")[-1])
            listing = db.get(Listing, list_id)
            if listing:
                await send_meta_message(
                    sender_id,
                    f"✅ *Interest Verified, {first_name}* \n\n"
                    f"Establishing a direct satellite link to the site... 🛰️",
                )
                nav_msg = build_inspection_confirmation(
                    first_name, listing.title, listing.latitude, listing.longitude
                )
                await send_meta_message(sender_id, nav_msg)
                await alert_realtor_of_lead(db, list_id, sender_id, biz_name)

                # Update funnel to handshake
                if convo:
                    convo.funnel_stage = "handshake"
                    convo.lead_score = 85
                    convo.last_active_at = datetime.now(timezone.utc).replace(
                        tzinfo=None
                    )
                    db.commit()
                return

        # --- 6. GREETING HANDLER WITH SESSION MEMORY ---
        is_greeting = (
            any(
                w in text_body.lower().split()
                for w in ["hi", "hello", "hey", "start", "greetings"]
            )
            and len(text_body.strip().split()) <= 3
        )

        if is_greeting:
            session_state = get_session_state(convo)

            if session_state == "new" or not convo:
                if not convo:
                    res = start_conversation_service(
                        channel, sender_id, whatsapp_name, tenant_id, db
                    )
                    convo = db.get(Conversation, res["conversation_id"])

                intro = get_executive_response("intro", first_name, biz_name)
                await send_meta_message(sender_id, intro)

                areas = tenant_profile.get("areas_covered", "Abuja")
                emoji = tenant_profile.get("emoji", "🏠")
                question = get_executive_response(
                    "intent_location", first_name, biz_name
                )
                await send_meta_message(
                    sender_id,
                    f"I am currently monitoring verified deals in "
                    f"*{areas}* {emoji}. {question}",
                )

            else:
                # Returning user — ONE resume message only
                prefs = json.loads(convo.data_json or "{}")
                convo.session_count = (convo.session_count or 1) + 1
                db.commit()

                resume_msg = build_resume_message(
                    session_state, first_name, biz_name, prefs
                )
                await send_meta_message(sender_id, resume_msg)

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

        # --- 9. OBJECTION HANDLER ---
        if intent == "objection":
            objection_key = pipe.get("objection_key", "objection_stalling")
            last_id = prefs.get("last_viewed_id")
            trust_grade = "Verified"
            if last_id:
                viewed = db.get(Listing, last_id)
                grade_raw = (viewed.trust_grade or "") if viewed else ""
                if grade_raw and grade_raw != "ungraded":
                    trust_grade = grade_raw.title()
            response = get_objection_response(objection_key, first_name, biz_name, trust_grade)
            await send_meta_message(sender_id, response)
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
            )
        ):
            try:
                search_result = execute_premium_search(db, tenant_id, prefs)
                matches = search_result.get("data", [])
                total = search_result.get("total_count", 0)
                source = search_result.get("source", "none")

                if matches:
                    if source == "referral":
                        summary = build_referral_summary(matches[0], biz_name)
                    else:
                        summary = build_property_summary(
                            matches[0], matches, total, first_name
                        )

                    await send_meta_message(sender_id, summary)
                    # Lock state to HANDOFF — prevents search re-triggering
                    prefs["last_viewed_id"] = matches[0].id
                    prefs["last_viewed_title"] = matches[0].title or ""
                    convo.data_json = json.dumps(prefs)
                    convo.state = "HANDOFF"
                    convo.funnel_stage = "commitment"
                    convo.last_active_at = datetime.now(timezone.utc).replace(
                        tzinfo=None
                    )
                    db.commit()
                    logger.info(f"Saved last_viewed_id: {matches[0].id}")

                    # Save last viewed listing ID so handshake works
                    prefs["last_viewed_id"] = matches[0].id
                    prefs["last_viewed_title"] = matches[0].title or ""
                    convo.data_json = json.dumps(prefs)
                    convo.funnel_stage = "commitment"
                    convo.last_active_at = datetime.now(timezone.utc).replace(
                        tzinfo=None
                    )
                    db.commit()
                    carousel_data = prepare_meta_carousel(matches)
                    await send_meta_carousel(sender_id, carousel_data)

                    # Advance funnel
                    convo.funnel_stage = "commitment"
                    convo.last_active_at = datetime.now(timezone.utc).replace(
                        tzinfo=None
                    )
                    db.commit()
                    return

                else:
                    await send_meta_message(
                        sender_id, build_no_match_message(prefs.get("location"))
                    )
                    # Keep state active so buyer can refine search
                    convo.state = "ACTIVE"
                    convo.last_active_at = datetime.now(timezone.utc).replace(
                        tzinfo=None
                    )
                    db.commit()
                    return

            except Exception as e:
                logger.error(f"Search Block Failure: {e}")
                await send_meta_message(sender_id, handle_logic_error("search_failure"))
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
                        "evening", "am", "pm", "noon", "weekend",
                        "january", "february", "march", "april", "may",
                        "june", "july", "august", "september", "october",
                        "november", "december",
                    ]
                    has_time = any(kw in msg_lower for kw in time_keywords)
                    has_time_pattern = bool(
                        re.search(r"\d{1,2}(:\d{2})?\s*(am|pm)?", msg_lower)
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
                            f"Thank you for choosing *{biz_name}* — "
                            f"where every property is verified before "
                            f"it reaches you. 🏠"
                        )
                        await send_meta_message(sender_id, confirmation)
                        return

                    else:
                        await send_meta_message(
                            sender_id,
                            f"What time works best for your inspection, "
                            f"{first_name}? "
                            f"(e.g. Tomorrow 10am, Friday afternoon) 📅",
                        )
                        return

                if prefs.get("location") and prefs.get("budget"):
                    try:
                        search_result = execute_premium_search(db, tenant_id, prefs)
                        matches = search_result.get("data", [])
                        total = search_result.get("total_count", 0)
                        source = search_result.get("source", "none")
                        if matches:
                            if source == "referral":
                                summary = build_referral_summary(matches[0], biz_name)
                            else:
                                summary = build_property_summary(
                                    matches[0], matches, total, first_name
                                )
                            await send_meta_message(sender_id, summary)
                            carousel_data = prepare_meta_carousel(matches)
                            await send_meta_carousel(sender_id, carousel_data)
                            prefs["last_viewed_id"] = matches[0].id
                            prefs["last_viewed_title"] = matches[0].title or ""
                            convo.data_json = json.dumps(prefs)
                            convo.state = "HANDOFF"
                            convo.funnel_stage = "commitment"
                            convo.last_active_at = datetime.now(timezone.utc).replace(
                                tzinfo=None
                            )
                            db.commit()
                            logger.info(f"Saved last_viewed_id: {matches[0].id}")
                        else:
                            await send_meta_message(
                                sender_id, build_no_match_message(prefs.get("location"))
                            )
                    except Exception as e:
                        logger.error(f"Search from completed_flag failed: {e}")
                        await send_meta_message(
                            sender_id, handle_logic_error("search_failure")
                        )
                    return

            # Global search trigger
            if final_reply == "trigger_global_search":
                search_result = execute_premium_search(
                    db, tenant_id, {"location": "Abuja"}
                )
                matches = search_result.get("data", [])
                if matches:
                    summary = (
                        f"I've pulled our Top {len(matches)} most trusted "
                        f"deals in Abuja for you, {first_name}. 🔄\n\n"
                    )
                    summary += build_property_summary(
                        matches[0],
                        matches,
                        search_result.get("total_count"),
                        first_name,
                    )
                    await send_meta_message(sender_id, summary)
                    await send_meta_carousel(sender_id, prepare_meta_carousel(matches))
                return

            # Handshake trigger
            if raw_reply == "handshake_flag" and not prefs.get("last_viewed_id"):
                await send_meta_message(
                    sender_id,
                    get_executive_response("intent_location", first_name, biz_name),
                )
                return
            if final_reply == "handshake_flag" or intent == "agreement":
                last_id = prefs.get("last_viewed_id")
                listing = db.get(Listing, last_id) if last_id else None
                if listing:
                    connection_msg = build_inspection_confirmation(
                        first_name, listing.title, listing.latitude, listing.longitude
                    )
                    await send_meta_message(sender_id, connection_msg)
                    await alert_realtor_of_lead(db, last_id, sender_id, biz_name)
                    convo.funnel_stage = "handshake"
                    convo.lead_score = min((convo.lead_score or 0) + 20, 100)
                    convo.last_active_at = datetime.now(timezone.utc).replace(
                        tzinfo=None
                    )
                    db.commit()
                    return
                else:
                    # No listing viewed yet — ask what they want
                    await send_meta_message(
                        sender_id,
                        get_executive_response("intent_location", first_name, biz_name),
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
                    await send_meta_message(sender_id, response)
                    return

            # Never send raw flag strings or generic fallback
            if final_reply in ("I am here to assist you.", "filler_flag", ""):
                next_q = get_next_question(prefs)
                if next_q:
                    await send_meta_message(sender_id, next_q)
                return

            # Default voice deliver
            await send_meta_message(sender_id, final_reply)

        except Exception as e:
            logger.error(f"❌ PERSONALITY ERROR: {e}")
            await send_meta_message(
                sender_id,
                "I'm still here! I had a small glitch — could you please "
                "say that again? 🙏",
            )

    except Exception as e:
        logger.error(f"❌ CRITICAL MASTER ERROR: {e}", exc_info=True)
