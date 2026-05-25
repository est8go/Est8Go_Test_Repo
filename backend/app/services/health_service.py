"""
Platform Health Monitor
=======================
Checks: database, whatsapp, openai, paystack, conversations, security.
Persists results in health_checks table.
Escalates CRITICAL issues via email and auto-creates PlatformIssue records.
"""
import os
import time
import logging
import requests
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.database.base import Base

logger = logging.getLogger(__name__)

SUPERADMIN_EMAIL = os.getenv("SUPERADMIN_EMAIL", "est8go@gmail.com")
BASE_URL = os.getenv("BASE_URL", "https://est8go-api.onrender.com")


# ════════════════════════════════════════════════════════════════
# MODELS
# ════════════════════════════════════════════════════════════════

class HealthCheck(Base):
    __tablename__ = "health_checks"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    system = Column(String(50), nullable=False)
    # ok | warning | critical | grey
    status = Column(String(20), nullable=False)
    detail = Column(Text, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    checked_at = Column(DateTime, default=func.now(), nullable=False)


class PlatformIssue(Base):
    __tablename__ = "platform_issues"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String(20), nullable=False, default="high")
    # open | in_progress | resolved
    status = Column(String(20), nullable=False, default="open")
    affected_area = Column(String(100), nullable=True)
    tenant_id = Column(Integer, nullable=True)
    assigned_to = Column(String(255), nullable=True)
    diagnosis = Column(Text, nullable=True)
    fix_applied = Column(Text, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )


# ════════════════════════════════════════════════════════════════
# CHECK FUNCTIONS — each returns a result dict
# ════════════════════════════════════════════════════════════════

def check_database(db: Session) -> dict:
    from sqlalchemy import text
    start = time.time()
    try:
        db.execute(text("SELECT 1"))
        ms = int((time.time() - start) * 1000)
        if ms > 2000:
            return {
                "system": "database", "status": "warning",
                "detail": f"Slow response: {ms}ms (threshold 2000ms)",
                "response_time_ms": ms,
            }
        return {
            "system": "database", "status": "ok",
            "detail": f"Healthy — {ms}ms", "response_time_ms": ms,
        }
    except Exception as e:
        return {
            "system": "database", "status": "critical",
            "detail": f"Unreachable: {e}", "response_time_ms": None,
        }


def check_whatsapp() -> dict:
    token = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
    phone_id = os.getenv("WHATSAPP_PHONE_ID", "")
    if not token or not phone_id:
        return {
            "system": "whatsapp", "status": "warning",
            "detail": "Credentials not configured", "response_time_ms": None,
        }
    try:
        start = time.time()
        resp = requests.get(
            f"https://graph.facebook.com/v18.0/{phone_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        ms = int((time.time() - start) * 1000)
        if resp.status_code == 401:
            return {
                "system": "whatsapp", "status": "critical",
                "detail": "Token expired — all tenant automations are offline",
                "response_time_ms": ms,
            }
        if resp.status_code != 200:
            return {
                "system": "whatsapp", "status": "warning",
                "detail": f"HTTP {resp.status_code}", "response_time_ms": ms,
            }
        return {
            "system": "whatsapp", "status": "ok",
            "detail": f"Healthy — {ms}ms", "response_time_ms": ms,
        }
    except Exception as e:
        return {
            "system": "whatsapp", "status": "critical",
            "detail": f"Unreachable: {e}", "response_time_ms": None,
        }


def check_paystack() -> dict:
    key = os.getenv("PAYSTACK_SECRET_KEY", "")
    if not key:
        return {
            "system": "paystack", "status": "warning",
            "detail": "Not configured", "response_time_ms": None,
        }
    try:
        start = time.time()
        resp = requests.get(
            "https://api.paystack.co/bank?perPage=1",
            headers={"Authorization": f"Bearer {key}"},
            timeout=10,
        )
        ms = int((time.time() - start) * 1000)
        if resp.status_code == 401:
            return {
                "system": "paystack", "status": "critical",
                "detail": "Invalid API key", "response_time_ms": ms,
            }
        if resp.status_code != 200:
            return {
                "system": "paystack", "status": "warning",
                "detail": f"HTTP {resp.status_code}", "response_time_ms": ms,
            }
        return {
            "system": "paystack", "status": "ok",
            "detail": f"Healthy — {ms}ms", "response_time_ms": ms,
        }
    except Exception as e:
        return {
            "system": "paystack", "status": "critical",
            "detail": f"Unreachable: {e}", "response_time_ms": None,
        }


def check_openai() -> dict:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return {
            "system": "openai", "status": "warning",
            "detail": "API key not configured", "response_time_ms": None,
        }
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        start = time.time()
        client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=3,
        )
        ms = int((time.time() - start) * 1000)
        if ms > 8000:
            return {
                "system": "openai", "status": "warning",
                "detail": f"Slow: {ms}ms (threshold 8000ms)", "response_time_ms": ms,
            }
        return {
            "system": "openai", "status": "ok",
            "detail": f"Healthy — {ms}ms", "response_time_ms": ms,
        }
    except Exception as e:
        return {
            "system": "openai", "status": "critical",
            "detail": f"Unreachable: {e}", "response_time_ms": None,
        }


def check_conversations(db: Session) -> dict:
    try:
        from app.conversations.models import Conversation
        cutoff = datetime.utcnow() - timedelta(hours=24)
        stuck = db.query(Conversation).filter(
            Conversation.state == "HANDOFF",
            Conversation.updated_at <= cutoff,
        ).count()
        if stuck > 0:
            return {
                "system": "conversations", "status": "warning",
                "detail": f"{stuck} conversation(s) stuck in HANDOFF > 24hrs",
                "response_time_ms": None,
            }
        return {
            "system": "conversations", "status": "ok",
            "detail": "No stuck conversations", "response_time_ms": None,
        }
    except Exception as e:
        return {
            "system": "conversations", "status": "warning",
            "detail": f"Check failed: {e}", "response_time_ms": None,
        }


def check_security(db: Session) -> dict:
    try:
        from app.database.audit import AuditLog
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        failed = db.query(AuditLog).filter(
            AuditLog.action == "login_failed",
            AuditLog.created_at >= one_hour_ago,
        ).count()
        if failed >= 10:
            return {
                "system": "security", "status": "critical",
                "detail": f"{failed} failed login attempts in last hour — possible brute force",
                "response_time_ms": None,
            }
        if failed >= 5:
            return {
                "system": "security", "status": "warning",
                "detail": f"{failed} failed login attempts in last hour",
                "response_time_ms": None,
            }
        return {
            "system": "security", "status": "ok",
            "detail": f"{failed} failed logins in last hour", "response_time_ms": None,
        }
    except Exception as e:
        return {
            "system": "security", "status": "ok",
            "detail": "Security audit unavailable", "response_time_ms": None,
        }


# ════════════════════════════════════════════════════════════════
# PERSIST + ESCALATE
# ════════════════════════════════════════════════════════════════

def save_check(db: Session, result: dict) -> None:
    try:
        db.add(HealthCheck(
            system=result["system"],
            status=result["status"],
            detail=result.get("detail"),
            response_time_ms=result.get("response_time_ms"),
        ))
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Health: failed to save result for {result.get('system')}: {e}")


def _create_issue_if_new(db: Session, system: str, detail: str) -> None:
    try:
        existing = db.query(PlatformIssue).filter(
            PlatformIssue.affected_area == system,
            PlatformIssue.status.in_(["open", "in_progress"]),
            PlatformIssue.severity == "critical",
        ).first()
        if existing:
            return
        db.add(PlatformIssue(
            title=f"{system.upper()} — critical alert auto-raised",
            description=detail,
            severity="critical",
            status="open",
            affected_area=system,
        ))
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Health: failed to auto-create issue: {e}")


def escalate_critical(system: str, detail: str, db: Optional[Session] = None) -> None:
    try:
        from app.services.email_service import _send, _base_template, _BTN, _P, _WN
        now_str = datetime.utcnow().strftime("%H:%M UTC %d %b %Y")
        body = f"""
        <p {_P}>A critical system alert has been detected on the Est8Go platform.</p>
        <p {_P}>
          <strong>System:</strong>
          <span style="color:#F43F5E;font-weight:700">{system.upper()}</span><br/>
          <strong>Status:</strong> <span {_WN}>CRITICAL</span><br/>
          <strong>Detail:</strong> {detail}<br/>
          <strong>Time:</strong> {now_str}
        </p>
        <p {_P}>Immediate action is required. Log in to your Super Admin dashboard.</p>
        <a href="{BASE_URL}/public/super-admin-portal" {_BTN}>View Dashboard</a>
        """
        _send(
            SUPERADMIN_EMAIL,
            f"EST8GO ALERT: {system.upper()} is down",
            _base_template(f"Critical Alert — {system.upper()}", body),
        )
        logger.warning(f"Health CRITICAL email sent — {system}: {detail}")
    except Exception as e:
        logger.error(f"Health: escalation email failed: {e}")

    if db:
        _create_issue_if_new(db, system, detail)


# ════════════════════════════════════════════════════════════════
# ORCHESTRATOR
# ════════════════════════════════════════════════════════════════

def run_all_checks(db: Session, include_openai: bool = False) -> list:
    """
    Run all 15-minute checks (plus optional OpenAI check).
    Saves each result to DB and escalates CRITICALs.
    """
    checks = [
        check_database(db),
        check_whatsapp(),
        check_paystack(),
        check_conversations(db),
        check_security(db),
    ]
    if include_openai:
        checks.append(check_openai())

    for result in checks:
        save_check(db, result)
        if result["status"] == "critical":
            escalate_critical(result["system"], result.get("detail", ""), db)
            logger.error(f"Health CRITICAL: {result['system']} — {result['detail']}")
        elif result["status"] == "warning":
            logger.warning(f"Health WARNING: {result['system']} — {result['detail']}")
        else:
            logger.info(f"Health OK: {result['system']} — {result['detail']}")

    return checks


def get_latest_statuses(db: Session) -> list:
    """Return the most-recent check result per system."""
    systems = ["database", "whatsapp", "openai", "paystack", "conversations", "security"]
    out = []
    for system in systems:
        latest = (
            db.query(HealthCheck)
            .filter(HealthCheck.system == system)
            .order_by(HealthCheck.checked_at.desc())
            .first()
        )
        if latest:
            out.append({
                "system": system,
                "status": latest.status,
                "detail": latest.detail,
                "response_time_ms": latest.response_time_ms,
                "checked_at": str(latest.checked_at),
            })
        else:
            out.append({
                "system": system,
                "status": "grey",
                "detail": "Not yet checked",
                "response_time_ms": None,
                "checked_at": None,
            })
    return out
