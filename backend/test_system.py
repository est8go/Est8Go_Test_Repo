from app.main import app
from app.services.conversation_service import handle_incoming_message
from app.services.tenant_resolver import resolve_tenant_from_webhook
from app.conversations.intent_filter import classify_intent
from app.conversations.objection_engine import get_objection_response
from app.services.ai_vision_service import audit_and_update_listing
from app.services.document_trust_engine import calculate_full_trust_score
from app.services.trust_engine import calculate_confidence_score
from app.services.recovery_engine import run_dropoff_recovery
from app.listings.document_router import router as document_router
from app.conversations.pipeline_router import router as pipeline_router
from app.services.reel_engine import generate_property_reel, check_ffmpeg_available
from app.services.reel_router import router as reel_router

print("✅ EST8GO FULL SYSTEM CHECK PASSED")
print(f"   Routes registered: {len(app.routes)}")
print(f"   FFmpeg available:  {check_ffmpeg_available()}")
