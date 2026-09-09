from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional

from app.database.db import get_db
from app.auth.deps import require_superuser, require_platform_user
from app.users.models import User
from app.services.health_service import run_all_checks, get_latest_statuses, HealthCheck

router = APIRouter(prefix="/admin/health", tags=["Health Monitor"])


@router.get("/status")
async def get_health_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superuser),
):
    """Latest status for every system. Superuser only."""
    statuses = get_latest_statuses(db)
    overall = "ok"
    for s in statuses:
        if s["status"] == "critical":
            overall = "critical"
            break
        if s["status"] == "warning":
            overall = "warning"
    return {"overall": overall, "systems": statuses}


@router.get("/history")
async def get_health_history(
    days: int = Query(default=7, ge=1, le=30),
    system: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_platform_user),
):
    """Health check history for the last N days. Platform staff only."""
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(days=days)
    query = (
        db.query(HealthCheck)
        .filter(HealthCheck.checked_at >= cutoff)
        .order_by(desc(HealthCheck.checked_at))
    )
    if system:
        query = query.filter(HealthCheck.system == system)
    logs = query.limit(200).all()
    return [
        {
            "id": l.id,
            "system": l.system,
            "status": l.status,
            "detail": l.detail,
            "response_time_ms": l.response_time_ms,
            "checked_at": str(l.checked_at),
        }
        for l in logs
    ]


@router.post("/run")
def run_health_check_now(
    include_openai: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superuser),
):
    """
    Manually trigger a full health check. Superuser only.

    Deliberately sync `def`, not `async def`. run_all_checks makes blocking
    calls — requests to Meta / Paystack / OpenAI, and on a CRITICAL result
    a blocking Resend send through escalate_critical. As `async def` all of
    that ran on the event loop and stalled every other request for its
    duration. A sync def hands the whole endpoint to FastAPI's threadpool,
    which is the pattern every other blocking caller in this codebase
    already uses, and it avoids passing the request's SQLAlchemy Session
    across a thread boundary the way an explicit to_thread would.
    """
    results = run_all_checks(db, include_openai=include_openai)
    return {"status": "complete", "checks": results}
