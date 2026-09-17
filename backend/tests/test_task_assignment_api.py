"""PostgreSQL integration tests for follow-up task ownership.

Run only with a disposable PostgreSQL database:
    TEST_DATABASE_URL=postgresql://.../est8go_test pytest tests/test_task_assignment_api.py

The database name must include "test". This guard prevents accidental use
of a tenant, staging, or production database.
"""

import os
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")


def _require_test_database() -> None:
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL is not configured")
    if not TEST_DATABASE_URL.startswith(("postgresql://", "postgres://")):
        pytest.skip("Task assignment integration tests require PostgreSQL")
    database_name = TEST_DATABASE_URL.rsplit("/", 1)[-1].split("?", 1)[0].lower()
    if "test" not in database_name:
        raise RuntimeError("Refusing to run against a database whose name lacks 'test'.")


@pytest.fixture(scope="session")
def runtime():
    _require_test_database()
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL

    from app.models_registry import register_all_models
    from app.database.base import Base
    from app.database.db import engine, SessionLocal

    register_all_models()
    Base.metadata.create_all(bind=engine)
    yield SessionLocal
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def seeded(runtime):
    from app.conversations.models import Conversation
    from app.operations.models import FollowUpTask
    from app.tenants.models import Tenant
    from app.users.models import User

    db = runtime()
    suffix = uuid4().hex[:10]
    tenant = Tenant(name=f"Amber Shelter {suffix}", slug=f"amber-{suffix}")
    other_tenant = Tenant(name=f"Other Agency {suffix}", slug=f"other-{suffix}")
    db.add_all([tenant, other_tenant])
    db.flush()

    admin = User(
        tenant_id=tenant.id,
        email=f"admin-{suffix}@example.com",
        hashed_password="test",
        role="admin",
        first_name="Amina",
        is_active=True,
    )
    staff = User(
        tenant_id=tenant.id,
        email=f"staff-{suffix}@example.com",
        hashed_password="test",
        role="staff",
        first_name="Bola",
        is_active=True,
    )
    inactive_staff = User(
        tenant_id=tenant.id,
        email=f"inactive-{suffix}@example.com",
        hashed_password="test",
        role="staff",
        first_name="Chidi",
        is_active=False,
    )
    foreign_staff = User(
        tenant_id=other_tenant.id,
        email=f"foreign-{suffix}@example.com",
        hashed_password="test",
        role="staff",
        first_name="Dami",
        is_active=True,
    )
    db.add_all([admin, staff, inactive_staff, foreign_staff])
    db.flush()

    conversation = Conversation(
        tenant_id=tenant.id,
        channel="whatsapp",
        external_user_id=f"23480{suffix[:8]}",
        state="ACTIVE",
    )
    db.add(conversation)
    db.flush()

    task = FollowUpTask(
        tenant_id=tenant.id,
        conversation_id=conversation.id,
        tier=1,
        kind="lead_quiet",
        status="open",
        quiet_since=datetime.now(timezone.utc).replace(tzinfo=None),
        due_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(task)
    db.commit()

    yield {
        "db": db,
        "tenant": tenant,
        "admin": admin,
        "staff": staff,
        "inactive_staff": inactive_staff,
        "foreign_staff": foreign_staff,
        "task": task,
    }
    db.rollback()
    db.close()


def _client_for(db, user):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.auth.deps import get_current_user
    from app.database.db import get_db
    from app.operations.tasks_router import router

    app = FastAPI()
    app.include_router(router)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_admin_assigns_same_tenant_staff_and_creates_audit_event(seeded):
    from app.database.audit import AuditLog
    from app.operations.models import FollowUpTask

    client = _client_for(seeded["db"], seeded["admin"])
    response = client.post(
        f"/tasks/{seeded['task'].id}/assign",
        json={"assignee_id": seeded["staff"].id},
    )

    assert response.status_code == 200
    assert response.json()["assigned_to"]["id"] == seeded["staff"].id
    task = seeded["db"].get(FollowUpTask, seeded["task"].id)
    assert task.assigned_user_id == seeded["staff"].id
    audit = seeded["db"].query(AuditLog).filter_by(
        target_table="followup_tasks", target_id=task.id, action="task_assigned"
    ).one()
    assert audit.actor_id == seeded["admin"].id
    assert audit.new_value["assignee"]["id"] == seeded["staff"].id


@pytest.mark.parametrize("staff_key", ["inactive_staff", "foreign_staff"])
def test_admin_cannot_assign_inactive_or_foreign_staff(seeded, staff_key):
    client = _client_for(seeded["db"], seeded["admin"])
    response = client.post(
        f"/tasks/{seeded['task'].id}/assign",
        json={"assignee_id": seeded[staff_key].id},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Choose an active staff member from your agency."


def test_second_staff_cannot_claim_an_already_claimed_task(seeded):
    from app.users.models import User

    second_staff = User(
        tenant_id=seeded["tenant"].id,
        email=f"second-{uuid4().hex[:10]}@example.com",
        hashed_password="test",
        role="staff",
        is_active=True,
    )
    seeded["db"].add(second_staff)
    seeded["db"].commit()

    first = _client_for(seeded["db"], seeded["staff"])
    second = _client_for(seeded["db"], second_staff)
    assert first.post(f"/tasks/{seeded['task'].id}/claim").status_code == 200
    assert second.post(f"/tasks/{seeded['task'].id}/claim").status_code == 409


def test_temperature_always_explains_the_colour(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-only-secret-key")
    from app.conversations.pipeline_router import classify_lead

    conversation = SimpleNamespace(
        id=1,
        data_json="{}",
        funnel_stage="commitment",
        lead_score=75,
        last_active_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        display_name="Test Buyer",
        external_user_id="2348000000000",
        channel="whatsapp",
        is_bot_active=True,
        session_count=1,
        buyer_role="buyer",
        reminder_count=0,
        assigned_realtor_id=None,
    )
    lead = classify_lead(conversation)
    assert lead["temp_code"] == "hot"
    assert lead["temperature_reason"]
