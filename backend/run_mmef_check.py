"""
EST8GO MMEF COMPLIANCE CHECK
Runs daily at 01:00 UTC via Render cron.
Checks all Core and Growth tenants for monthly minimum engagement floor compliance.
Sends warning emails at 7 days and 3 days before month end if not yet compliant.
"""
import os
from dotenv import load_dotenv
load_dotenv()

from app.models_registry import register_all_models
register_all_models()

import logging
import calendar
from datetime import datetime
from sqlalchemy import func

from app.database.db import SessionLocal
from app.tenants.models import Tenant
from app.credits.models import CreditTransaction, MmefTracking
from app.users.models import User

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

MMEF_THRESHOLDS = {"core": 2500, "growth": 6000}


def run_mmef_check():
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        current_month = now.strftime("%Y-%m")
        days_in_month = calendar.monthrange(now.year, now.month)[1]
        days_left = days_in_month - now.day

        logger.info(f"MMEF CHECK: {current_month} | {days_left} days left")

        tenants = db.query(Tenant).filter(
            Tenant.plan.in_(["core", "growth"]),
            Tenant.is_active == True,
        ).all()

        warned = 0
        compliant = 0
        at_risk = 0

        for tenant in tenants:
            threshold = MMEF_THRESHOLDS.get(tenant.plan, 0)

            purchased = db.query(
                func.sum(CreditTransaction.amount_ngn)
            ).filter(
                CreditTransaction.tenant_id == tenant.id,
                CreditTransaction.status == "completed",
                CreditTransaction.month_year == current_month,
            ).scalar() or 0

            pct = (purchased / threshold * 100) if threshold > 0 else 100
            shortfall = threshold - purchased

            # Upsert MMEF tracking row
            mmef = db.query(MmefTracking).filter(
                MmefTracking.tenant_id == tenant.id,
                MmefTracking.month_year == current_month,
            ).first()

            if not mmef:
                mmef = MmefTracking(
                    tenant_id=tenant.id,
                    month_year=current_month,
                    tier=tenant.plan,
                    required_ngn=threshold,
                )
                db.add(mmef)

            mmef.purchased_ngn = purchased
            mmef.met = purchased >= threshold

            if purchased >= threshold:
                compliant += 1
                logger.info(
                    f"COMPLIANT: {tenant.business_name} "
                    f"₦{purchased:,}/₦{threshold:,}"
                )
                continue

            at_risk += 1

            # Send warning emails at 7 and 3 days left
            if days_left in [7, 3]:
                user = db.query(User).filter(
                    User.tenant_id == tenant.id,
                    User.is_active == True,
                ).first()

                if user:
                    try:
                        from app.services.email_service import _send, _base_template
                        base_url = os.getenv(
                            "BASE_URL", "https://est8go-api.onrender.com"
                        )
                        body = f"""
                        <p>Hi {user.email.split('@')[0].title()},</p>
                        <p>Your <strong>{tenant.plan.title()} plan</strong>
                        requires a minimum of
                        <strong>₦{threshold:,}</strong> in
                        Est8 Credits this month.</p>
                        <p>
                          <strong>Purchased so far:</strong>
                          ₦{purchased:,} ({pct:.0f}%)<br/>
                          <strong>Shortfall:</strong>
                          ₦{shortfall:,}<br/>
                          <strong>Days left:</strong> {days_left}
                        </p>
                        <p>Top up your credits to maintain your
                        plan level and keep all features active.</p>
                        <a href="{base_url}/public/realtor-portal"
                           style="display:inline-block;
                                  background:#4338CA;color:white;
                                  text-decoration:none;padding:14px 28px;
                                  border-radius:12px;font-weight:700;
                                  font-size:14px;margin:8px 0 20px">
                          Buy Credits Now
                        </a>"""

                        _send(
                            user.email,
                            f"Action needed: Top up credits to maintain "
                            f"your {tenant.plan.title()} plan",
                            _base_template("Credits Top-Up Reminder", body),
                        )
                        warned += 1
                        logger.info(
                            f"WARNING EMAIL: {user.email} | "
                            f"{days_left} days left | shortfall ₦{shortfall:,}"
                        )
                    except Exception as e:
                        logger.error(f"MMEF email failed for {tenant.business_name}: {e}")

        db.commit()
        logger.info(
            f"MMEF COMPLETE: {compliant} compliant | "
            f"{at_risk} at risk | {warned} warned"
        )

    except Exception as e:
        logger.error(f"MMEF CHECK ERROR: {e}", exc_info=True)
    finally:
        db.close()


if __name__ == "__main__":
    run_mmef_check()
