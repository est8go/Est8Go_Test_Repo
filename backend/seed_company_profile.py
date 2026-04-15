from __future__ import annotations

import app.models_registry  # noqa: F401

from app.database.db import SessionLocal

# ✅ IMPORTANT: import BOTH models so SQLAlchemy registers them
from app.tenants.models import Tenant  # noqa: F401
from app.company_profiles.models import CompanyProfile

TENANT_ID = 1

# ✅ Assistant branding (default)
ASSISTANT_NAME = "Aor"
ASSISTANT_ROLE = "Real Estate Assistant"
EMOJI_MODE = "minimal"  # "off" | "minimal" | "friendly"

COMPANY_NAME = "Bravies Homz Limited"
SHORT_ABOUT = (
    "Bravieshomz Limited is a leading real estate development and marketing company "
    "headquartered in Abuja, Nigeria. We are a technology driven firm focused on delivering "
    "innovative housing solutions to help bridge the housing deficit in Nigeria and across Africa. "
    "Our core mission is to make homeownership and real estate investment accessible, seamless, and rewarding. "
    "In addition to developing quality residential projects, we connect property sellers with buyers, providing "
    "expert guidance to secure profitable investments and ideal living spaces. At Bravieshomz, we are committed "
    "to excellence, integrity, and customer satisfaction in every transaction."
)

OFFICE_ADDRESS = "Area 11, Suit C201, 11 Dunukofia St, Garki, Abuja 900122"
PHONE = "0706 252 8151"
WHATSAPP = "0706 252 8151"
EMAIL = "customercare@bravieshomz.com"
AREAS_COVERED = "Federal Capital Territory Abuja Nigeria"
PAYMENT_OPTIONS = "Outright and Installment - 3 months, 6 months and 12 months"
INSPECTION_POLICY = "The company takes care of logistics and all other expenditures"
HANDOFF_MESSAGE = "Please our consultant will be with you shortly. Thank you for your patience."


def main() -> None:
    db = SessionLocal()
    try:
        # ensure tenant exists
        tenant = db.query(Tenant).filter(Tenant.id == TENANT_ID).first()
        if not tenant:
            raise SystemExit(f"[ERROR] Tenant id={TENANT_ID} not found. Create tenant first.")

        prof = db.query(CompanyProfile).filter(CompanyProfile.tenant_id == TENANT_ID).first()

        if not prof:
            prof = CompanyProfile(tenant_id=TENANT_ID)
            db.add(prof)

        # ✅ New fields
        prof.assistant_name = ASSISTANT_NAME
        prof.assistant_role = ASSISTANT_ROLE
        prof.emoji_mode = EMOJI_MODE

        # existing fields
        prof.company_name = COMPANY_NAME
        prof.short_about = SHORT_ABOUT
        prof.office_address = OFFICE_ADDRESS
        prof.phone = PHONE
        prof.whatsapp = WHATSAPP
        prof.email = EMAIL
        prof.areas_covered = AREAS_COVERED
        prof.payment_options = PAYMENT_OPTIONS
        prof.inspection_policy = INSPECTION_POLICY
        prof.handoff_message = HANDOFF_MESSAGE

        db.commit()
        print("[OK] CompanyProfile seeded/updated for tenant_id =", TENANT_ID)

    finally:
        db.close()


if __name__ == "__main__":
    main()