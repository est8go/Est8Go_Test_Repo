"""
EST8GO SHARED VALIDATORS
========================
Validation used by more than one router. Kept out of the routers so the
same rule cannot drift between the admin path and the self-service path.
"""

import re

# A Meta WhatsApp phone_number_id is an opaque numeric string, currently
# 15-16 digits (e.g. 1138633615995344). It is NOT a phone number.
#
# This matters because Tenant.whatsapp_phone_number_id is unique=True and
# is a webhook ROUTING KEY: resolve_tenant_from_webhook matches an
# incoming payload's metadata.phone_number_id against it. A local phone
# number in that column is dead weight that can never match — and worse,
# it occupies a unique slot, so a genuine Meta id typed into the wrong
# field silently misroutes another tenant's messages.
#
# Range is deliberately wider than today's 15-16 digits: Meta has never
# published a fixed length, so this rejects obvious junk (phone numbers,
# names, tokens) without guessing at a ceiling that may move.
_META_ID_RE = re.compile(r"^\d{12,20}$")

# Nigerian local formats we specifically want to name in the error, since
# pasting the WhatsApp phone number into the phone-number-ID field is the
# mistake that actually happened in production (tenants 3-6).
_LOCAL_PHONE_RE = re.compile(r"^(?:\+?234|0)\d{7,11}$")


def validate_meta_phone_number_id(value: str) -> tuple[bool, str]:
    """
    Validates a Meta WhatsApp phone_number_id.

    Returns (True, "") when valid, else (False, <reason for the user>).
    Callers decide how to surface the failure — HTTPException in the
    routers, a printed message in scripts.

    Empty/None is INVALID here. A caller that treats "not supplied" as
    acceptable must check that before calling.
    """
    if value is None:
        return False, "WhatsApp Phone Number ID is required."

    _v = str(value).strip()
    if not _v:
        return False, "WhatsApp Phone Number ID is required."

    if _META_ID_RE.match(_v):
        return True, ""

    # Name the specific mistake rather than a generic format error.
    if _LOCAL_PHONE_RE.match(_v):
        return False, (
            "That looks like a phone number, not a WhatsApp Phone Number ID. "
            "The ID is a long numeric value (about 15 digits) from Meta "
            "Business Suite → WhatsApp → API Setup — not the +234 number "
            "buyers dial."
        )

    if not _v.isdigit():
        return False, (
            "WhatsApp Phone Number ID must contain digits only. Copy it from "
            "Meta Business Suite → WhatsApp → API Setup."
        )

    return False, (
        f"WhatsApp Phone Number ID looks wrong ({len(_v)} digits). Expected "
        "roughly 15 digits, e.g. 1138633615995344."
    )
