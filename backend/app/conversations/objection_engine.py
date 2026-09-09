"""
EST8GO KORA OBJECTION ENGINE
==============================
Standard Nigerian Real Estate objections mapped to short, honest,
forward-moving replies.

Rules-First: Pure Python — zero GPT cost.
Every objection advances the sale, never just answers it.

Voice:
    Kora speaks AS THE AGENCY, on the agency's own number. The buyer
    is talking to their estate agency, not to a platform. Nothing here
    ever mentions Est8Go, the platform, or any verification policy.

Position:
    We hold what the agency gives us and show it to buyers. Nothing in
    this file asserts that a document is genuine, a photo original, a
    location confirmed or a property real. State what is on record,
    then offer the next step.

Style:
    WhatsApp, not web copy. Two or three lines, then a forward step.
"""

import random

# ================================================================
# WHAT WE HOLD ON A LISTING
# ================================================================


def _format_day(value) -> str:
    """'12 January' — no leading zero, no year for a recent record."""
    try:
        return f"{value.day} {value.strftime('%B')}"
    except Exception:
        return ""


def _document_names(listing) -> list:
    """
    Human names of the documents on file.
    Strips the parenthetical: "Certificate of Occupancy (C of O)" reads
    as "Certificate of Occupancy" in a chat message.
    """
    names = []
    for doc in (getattr(listing, "documents", None) or []):
        label = (getattr(doc, "label", "") or "").split("(")[0].strip()
        if label and label not in names:
            names.append(label)
    if names:
        return names

    # Fall back to the per-type flags when no document rows exist.
    for flag, label in (
        ("cof_uploaded", "Certificate of Occupancy"),
        ("deed_uploaded", "Deed of Assignment"),
        ("survey_uploaded", "Survey Plan"),
    ):
        if getattr(listing, flag, False):
            names.append(label)
    return names


def _join_naturally(items: list) -> str:
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])} and {items[-1]}"


def build_agency_record(listing) -> str:
    """
    One sentence naming what we hold on this listing — coordinates,
    photos, documents on file.

    States only what exists and when it was recorded. Never asserts
    that any of it was checked, authenticated or found genuine, and
    never reports a trust grade: a score reads as a verification
    claim, and that is not a claim we are in a position to make.

    witness_count is deliberately not used.

    Returns a complete sentence in every case, so it drops straight
    into a template with no branching at the call site.
    """
    nothing_yet = "Let me pull the full file on this one for you."

    if listing is None:
        return nothing_yet

    parts = []

    if getattr(listing, "latitude", None) and getattr(listing, "longitude", None):
        day = _format_day(getattr(listing, "gps_verified_at", None))
        parts.append(
            f"coordinates recorded on {day}" if day else "coordinates on file"
        )

    photo_count = len(getattr(listing, "images", None) or [])
    if photo_count:
        parts.append(f"{photo_count} photo{'s' if photo_count != 1 else ''}")

    documents = _document_names(listing)
    if documents:
        parts.append(f"the {_join_naturally(documents)} on file")

    if not parts:
        return nothing_yet

    if len(parts) > 1:
        body = f"{', '.join(parts[:-1])}, plus {parts[-1]}"
    else:
        body = parts[0]

    return f"Here's what we have on this one: {body}."


# ================================================================
# THE OBJECTION RESPONSES
# ================================================================

OBJECTION_RESPONSES = {
    # --- 1. STALLING ("let me think", "I'll get back to you") ---
    "objection_stalling": [
        (
            "Of course, {name}. A decision like this deserves time. 🧠\n\n"
            "Tell me what you'd want settled first — the documents, the "
            "location, the price — and I'll get it for you.\n\n"
            "What's on your mind?"
        ),
        (
            "That's fair, {name}. 🏠\n\n"
            "{record}\n\n"
            "Anything you'd like me to send across while you think it over?"
        ),
    ],
    # --- 2. MEDIA REQUEST ("send me the video", "WhatsApp video") ---
    "objection_media": [
        (
            "Of course, {name}! 📸\n\n"
            "Every photo we have on this property is at the link I shared.\n\n"
            "For the full walkthrough our professionals take you round the "
            "site itself — shall I book that in?"
        ),
        (
            "Happy to, {name}. 🎥\n\n"
            "Photos only show so much, which is why we walk buyers round the "
            "property in person.\n\n"
            "Shall I arrange that with our professionals this week?"
        ),
    ],
    # --- 3. AVAILABILITY ("is it still available?", "still there?") ---
    # The realtor alert is wired into this path in conversation_service —
    # the copy offers a confirmation, so someone has to actually hear
    # about it.
    "objection_availability": [
        (
            "Still available, {name}. ✅\n\n"
            "I'll have our professionals confirm the current position before "
            "you travel.\n\n"
            "Shall I book you in for a viewing?"
        ),
        (
            "Yes, still on our list, {name}. 🔒\n\n"
            "Let me get our professionals to confirm it's not under offer and "
            "hold a date for you at the same time.\n\n"
            "What day suits?"
        ),
    ],
    # --- 4. PRICE NEGOTIATION ("last price?", "can owner reduce?") ---
    "objection_price": [
        (
            "Fair point, {name}. 💰\n\n"
            "Let me see what else we have:\n\n"
            "1️⃣ *A lower-priced option* in the same area\n"
            "2️⃣ *A nearby area* within your budget\n"
            "3️⃣ *Speak to our professionals* about payment structure\n\n"
            "Which would you prefer? "
            "Or tell me your maximum and I'll search now."
        ),
    ],
    # --- 5. BUDGET MISMATCH ---
    # Handled end-to-end in conversation_service (re-search / budget
    # prompt) and never reaches this file. Noted here so the numbering
    # matches the objection set.
    # --- 6. THIRD PARTY ("my wife", "my husband", "my partner") ---
    "objection_third_party": [
        (
            "That's wise, {name} — a decision like this belongs to both of "
            "you. 👨‍👩‍👧\n\n"
            "Send them the property link: the photos, location and documents "
            "on file are all in one place.\n\n"
            "Shall I resend it so you can forward it?"
        ),
        (
            "Absolutely the right call, {name}. 🤝\n\n"
            "If there's anything specific they'd want — a document, the exact "
            "address, a viewing date — tell me and I'll sort it.\n\n"
            "What would they want to see first?"
        ),
    ],
    # --- 7. MORE OPTIONS ("show me others", "any other options?") ---
    "objection_more_options": [
        (
            "Of course, {name}! Worth comparing. 🔍\n\n"
            "Tell me what to change — a different area, a higher or lower "
            "budget, another property type — and I'll pull a fresh set.\n\n"
            "What should I adjust?"
        ),
        (
            "Let me widen it for you, {name}. 📋\n\n"
            "Give me an area and a maximum figure and I'll show you "
            "everything we have in range.\n\n"
            "What are we working with?"
        ),
    ],
    # --- 8. COLD DISENGAGEMENT ("not interested", "forget it") ---
    "objection_cold": [
        (
            "Understood, {name}. No pressure at all. 🙏\n\n"
            "If your plans change — buying, selling or just looking — message "
            "this number any time.\n\n"
            "If something specific put you off, I'd genuinely like to know."
        ),
        (
            "That's perfectly fine, {name}. 👍\n\n"
            "Message this number whenever you'd like to look again.\n\n"
            "Anything I could have done better?"
        ),
    ],
    # --- 9. NIGERIAN CASUAL ("abeg", "e don do") ---
    "objection_nigerian_casual": [
        (
            "Ha {name}, I hear you! 😄\n\n"
            "{record} Our professionals fit carry you go the site make you "
            "see am yourself.\n\n"
            "Make I arrange am for you? 🤝"
        ),
        (
            "Lol {name}, I feel you! 😂\n\n"
            "Best thing na to go see the place with your own eyes — na there "
            "everything dey clear.\n\n"
            "Make I book am for you? ✅"
        ),
    ],
    # --- 10. INSPECTION OBJECTION ("I can't come now", "too far") ---
    "objection_inspection": [
        (
            "No problem at all, {name}. 📅\n\n"
            "Our professionals work weekdays, weekends and early mornings — "
            "whatever suits you.\n\n"
            "What day works best?"
        ),
        (
            "Understood, {name}. 🚗\n\n"
            "If distance is the issue, many of our buyers send a relative or "
            "their surveyor to view on their behalf.\n\n"
            "Shall I hold a date for whoever can make it?"
        ),
    ],
    # --- 11. TRUST / LEGITIMACY ("how do I know it's real?") ---
    "objection_trust": [
        (
            "Good question, {name}. 🔍\n\n"
            "{record} Our professionals can take you through it "
            "themselves.\n\n"
            "The surest way is to see it in person — shall I arrange an "
            "inspection?"
        ),
    ],
    # --- 12. AGENT QUALITY ("is the agent reliable?") ---
    "objection_agent": [
        (
            "Happy to introduce you, {name}. 🤝\n\n"
            "Our professionals handle this listing directly and can answer "
            "anything the file doesn't cover.\n\n"
            "Shall I connect you with them, or arrange a site visit first?"
        ),
    ],
}


# ================================================================
# RESPONSE GETTER
# ================================================================


def get_objection_response(
    response_key: str, name: str, biz_name: str, listing=None
) -> str:
    """
    Returns a randomised objection response.

    Args:
        response_key: The objection key from OBJECTION_RESPONSES
        name:         Buyer's first name
        biz_name:     The agency's business name
        listing:      The Listing in view, if any. Copy is built from
                      what is actually on record for it — never from a
                      trust grade, which reads as a verification claim.

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
    return template.format(
        name=name,
        biz_name=biz_name,
        record=build_agency_record(listing),
    )


# ================================================================
# MEDIA REDIRECT BUILDER
# ================================================================


def build_media_redirect(name: str, biz_name: str, showroom_link: str) -> str:
    """
    Media request handler that includes the property link.
    Called when a buyer asks for video/photos.
    """
    return (
        f"Of course, {name}! 📸\n\n"
        f"Every photo we have on this property is here:\n"
        f"{showroom_link}\n\n"
        f"For the full walkthrough our professionals take you round the site "
        f"itself. Shall I book that in? 📅"
    )
