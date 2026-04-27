# ruff: noqa: E402
import os
import logging
from sqlalchemy.orm import Session
from dotenv import load_dotenv

load_dotenv()

from app.models_registry import register_all_models

register_all_models()

from app.database.db import SessionLocal
from app.tenants.models import Tenant
from app.listings.models import Listing
from app.services.tenant_service import get_tenant_profile
from app.conversations.responses import get_response
from app.services.trust_engine import calculate_confidence_score, verify_gps_proximity
from app.services.conversation_service import add_message_service

logging.getLogger("sqlalchemy").setLevel(logging.WARNING)


def run_stage_a_test():
    db: Session = SessionLocal()
    print("\n" + "=" * 50)
    print("        EST8GO STAGE A: THE TRUTH-TEST")
    print("=" * 50)

    try:
        # TEST 0-2 (Your working tests)
        print(f"TEST 0: Found {db.query(Tenant).count()} Tenants.")
        t101 = get_tenant_profile(db, 101)
        print(f"TEST 1: Voice -> {get_response('greeting', 'Tunde', t101)[:40]}...")
        print(
            f"TEST 2: GPS Proximity -> {verify_gps_proximity('Maitama', 9.0775, 7.5028)}/100"
        )

        # FIX: LegacyAPIWarning resolved using modern Session.get()
        list_truth = db.get(Listing, 991)
        if list_truth:
            print(f"TEST 3: Confidence -> {calculate_confidence_score(list_truth)}%")

        # TEST 4: The Logic Finale
        print("\nTEST 4: Rules-First Extraction Check")
        logic_result = add_message_service(1, "I want land in Maitama", 101, db)

        # Smart Data Extraction (Handles both flat and nested AI responses)
        prefs = logic_result.get("prefs", {})
        if "current_data" in prefs:
            prefs = prefs["current_data"]

        extracted_loc = prefs.get("location")

        if extracted_loc and "maitama" in extracted_loc.lower():
            print(f"  ✅ SUCCESS: Extracted Location: {extracted_loc}")
            print("  ✅ STAGE A COMPLETE: The Engine is officially Truth-Verified.")
        else:
            print(f"  ❌ FAILED: Received structure: {logic_result.get('prefs')}")

    except Exception as e:
        print(f"❌ TEST ERROR: {e}")
    finally:
        db.close()
        print("\n" + "=" * 50)


if __name__ == "__main__":
    run_stage_a_test()
