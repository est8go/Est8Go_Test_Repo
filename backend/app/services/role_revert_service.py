from datetime import datetime
from app.database.db import SessionLocal
from app.auth.models import RoleChangeRequest
from app.users.models import User
from app.services.email_service import send_role_reverted
import logging

logger = logging.getLogger(__name__)


def revert_expired_roles():
    """
    Called periodically (e.g. scheduled task or startup hook).
    Reverts any temporary role elevations that have expired.
    """
    db = SessionLocal()
    try:
        expired = db.query(RoleChangeRequest).filter(
            RoleChangeRequest.status     == "approved",
            RoleChangeRequest.expires_at <= datetime.utcnow(),
            RoleChangeRequest.expires_at  != None,
        ).all()

        for req in expired:
            user = db.query(User).filter(User.id == req.requester_id).first()
            if user and user.previous_role:
                original_role = user.previous_role
                user.role             = original_role
                user.role_expires_at  = None
                user.previous_role    = None
                req.status            = "reverted"
                db.commit()

                name = user.email.split("@")[0].title()
                send_role_reverted(user.email, name, original_role)
                logger.info(f"Reverted {user.email} from {req.requested_role} to {original_role}")
    except Exception as e:
        logger.error(f"Role revert error: {e}")
    finally:
        db.close()
