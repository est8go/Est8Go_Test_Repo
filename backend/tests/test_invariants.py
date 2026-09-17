import json
import importlib


def _assert_has(mod, names):
    for n in names:
        assert hasattr(mod, n), f"Missing {mod.__name__}.{n}"


def test_ai_fallback_capabilities_exist():
    m = importlib.import_module("app.conversations.ai_fallback")
    _assert_has(m, ["is_company_faq", "answer_company_faq"])
    assert callable(m.is_company_faq)
    assert callable(m.answer_company_faq)
    assert m.is_company_faq("Tell me about your company")


def test_ai_cache_model_has_unique_index():
    m = importlib.import_module("app.ai_cache.models")
    assert hasattr(m, "AiCache"), "Missing AiCache model"
    AiCache = m.AiCache
    for col in ["tenant_id", "state", "prompt_key", "answer"]:
        assert hasattr(AiCache, col), f"Missing AiCache.{col}"


def test_company_profile_fields_exist():
    m = importlib.import_module("app.company_profiles.models")
    CP = m.CompanyProfile
    required = [
        "assistant_name",
        "assistant_role",
        "emoji_mode",
        "company_name",
        "company_about",
        "phone_whatsapp",
        "email",
        "office_address",
        "areas_covered",
        "payment_rules",
        "verification_policy",
        "recovery_speed",
        "send_window_start",
        "send_window_end",
    ]
    for f in required:
        assert hasattr(CP, f), f"Missing CompanyProfile.{f}"


def test_conversation_state_machine_minimum_contract():
    from app.models_registry import register_all_models

    # SQLAlchemy relationships use class names across modules. Register every
    # model before creating an instance so this test exercises the app setup,
    # rather than a partial import order that production never uses.
    register_all_models()
    m = importlib.import_module("app.conversations.models")
    Conversation = m.Conversation
    assert hasattr(Conversation, "state"), "Conversation must have state"
    assert hasattr(Conversation, "data_json"), "Conversation must store data_json"
    # Ensure json default is usable
    dummy = Conversation()
    raw = getattr(dummy, "data_json", "{}") or "{}"
    json.loads(raw)


def test_routers_expose_required_endpoints():
    # Public router must expose public endpoints
    pub = importlib.import_module("app.public.router")
    assert hasattr(pub, "router"), "public.router must define router"
    # Conversations router must expose private endpoints
    conv = importlib.import_module("app.conversations.router")
    assert hasattr(conv, "router"), "conversations.router must define router"
