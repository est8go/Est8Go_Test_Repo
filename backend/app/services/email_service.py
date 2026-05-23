import resend
import os
from typing import Optional

resend.api_key = os.getenv("RESEND_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "Est8Go <onboarding@resend.dev>")
BASE_URL = os.getenv("BASE_URL", "https://est8go-api.onrender.com")


def _send(to: str, subject: str, html: str) -> bool:
    try:
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": to,
            "subject": subject,
            "html": html,
        })
        return True
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Email failed: {e}")
        return False


def _base_template(title: str, body: str) -> str:
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8"/>
      <meta name="viewport" content="width=device-width,initial-scale=1"/>
      <style>
        body{{margin:0;padding:0;background:#0F172A;font-family:'Inter',Arial,sans-serif;color:#F8FAFC}}
        .wrap{{max-width:520px;margin:40px auto;padding:0 20px}}
        .card{{background:#111827;border:1px solid rgba(255,255,255,0.07);
               border-radius:20px;padding:36px 32px}}
        .logo{{font-size:24px;font-weight:800;letter-spacing:-1px;margin-bottom:28px}}
        .logo span{{color:#10B981}}
        h2{{font-size:20px;font-weight:700;margin:0 0 12px}}
        p{{font-size:14px;line-height:1.6;color:#94A3B8;margin:0 0 16px}}
        .btn{{display:inline-block;background:#4338CA;color:white;
              text-decoration:none;padding:14px 28px;border-radius:12px;
              font-weight:700;font-size:14px;margin:8px 0 20px}}
        .note{{font-size:12px;color:#475569;margin-top:24px;
               padding-top:20px;border-top:1px solid rgba(255,255,255,0.07)}}
        .em{{color:#10B981;font-weight:600}}
        .warn{{color:#F59E0B;font-weight:600}}
      </style>
    </head>
    <body>
      <div class="wrap">
        <div class="card">
          <div class="logo">Est<span>8</span>Go</div>
          <h2>{title}</h2>
          {body}
          <div class="note">
            Est8Go Service Limited · Trust Infrastructure for African Real Estate<br/>
            If you did not request this, ignore this email or contact support.
          </div>
        </div>
      </div>
    </body>
    </html>"""


def send_password_reset(to_email: str, reset_url: str, name: str = "") -> bool:
    body = f"""
    <p>Hi {name or 'there'},</p>
    <p>We received a request to reset your Est8Go password.
       Click the button below to create a new password.</p>
    <a href="{reset_url}" class="btn">Reset My Password</a>
    <p>This link expires in <span class="warn">1 hour</span>.
       If you did not request this, your account is safe —
       simply ignore this email.</p>"""
    return _send(to_email, "Reset your Est8Go password",
                 _base_template("Password Reset Request", body))


def send_role_change_request(
    admin_email: str,
    requester_name: str,
    requester_email: str,
    requested_role: str,
    approve_url: str,
    reject_url: str,
) -> bool:
    body = f"""
    <p>A staff member has requested a role elevation on Est8Go.</p>
    <p>
      <strong>Requester:</strong> {requester_name} ({requester_email})<br/>
      <strong>Requested Role:</strong> <span class="em">{requested_role}</span>
    </p>
    <p>Log in to your Super Admin dashboard to review and approve or reject
       this request. You will be asked to confirm with your password.</p>
    <a href="{approve_url}" class="btn">Review Request</a>
    <p>This request will expire in <span class="warn">24 hours</span>
       if not actioned.</p>"""
    return _send(admin_email,
                 f"Role elevation request from {requester_name}",
                 _base_template("Role Elevation Request", body))


def send_role_change_approved(
    to_email: str,
    name: str,
    new_role: str,
    expiry_hours: int,
) -> bool:
    body = f"""
    <p>Hi {name},</p>
    <p>Your role elevation request has been
       <span class="em">approved</span>.</p>
    <p>
      <strong>New Role:</strong> <span class="em">{new_role}</span><br/>
      <strong>Duration:</strong> <span class="warn">{expiry_hours} hours</span>
    </p>
    <p>Your role will automatically revert after this period.
       Please use elevated permissions responsibly —
       all actions are logged.</p>
    <a href="{BASE_URL}/public/login" class="btn">Login to Dashboard</a>"""
    return _send(to_email, "Role elevation approved",
                 _base_template("Role Elevation Approved", body))


def send_role_change_rejected(
    to_email: str,
    name: str,
    requested_role: str,
) -> bool:
    body = f"""
    <p>Hi {name},</p>
    <p>Your request for <span class="warn">{requested_role}</span>
       elevation has been reviewed and was not approved at this time.</p>
    <p>If you believe this was an error, please contact your
       platform administrator directly.</p>"""
    return _send(to_email, "Role elevation not approved",
                 _base_template("Role Request Update", body))


def send_role_reverted(to_email: str, name: str, reverted_role: str) -> bool:
    body = f"""
    <p>Hi {name},</p>
    <p>Your temporary role elevation has expired and your role
       has been automatically reverted to
       <span class="em">{reverted_role}</span>.</p>
    <p>Contact your platform administrator if you need
       continued elevated access.</p>"""
    return _send(to_email, "Role elevation expired",
                 _base_template("Role Elevation Expired", body))


def send_tenant_signup_link(
    to_email: str,
    signup_url: str,
    plan: str,
    expiry_hours: int,
    invited_by: str = "Est8Go Team",
) -> bool:
    body = f"""
    <p>You have been invited to join Est8Go —
       Nigeria's verified real estate trust platform.</p>
    <p>
      <strong>Plan:</strong> <span class="em">{plan}</span><br/>
      <strong>Invited by:</strong> {invited_by}<br/>
      <strong>Link expires:</strong> <span class="warn">
        {expiry_hours} hours</span>
    </p>
    <p>Click below to set up your account and start verifying
       properties with GPS, AI audits, and document scoring.</p>
    <a href="{signup_url}" class="btn">Complete My Setup →</a>"""
    return _send(to_email, "Your Est8Go invitation is ready",
                 _base_template("You're Invited to Est8Go", body))


def send_onboarding_complete(
    admin_email: str,
    tenant_name: str,
    tenant_email: str,
    plan: str,
) -> bool:
    body = f"""
    <p>A new tenant has completed onboarding on Est8Go.</p>
    <p>
      <strong>Business:</strong> {tenant_name}<br/>
      <strong>Email:</strong> {tenant_email}<br/>
      <strong>Plan:</strong> <span class="em">{plan}</span>
    </p>
    <p>Their account is now active. You can manage them from
       the Tenants tab in your Super Admin dashboard.</p>
    <a href="{BASE_URL}/public/super-admin-portal" class="btn">
      View in Dashboard
    </a>"""
    return _send(admin_email, f"New tenant onboarded: {tenant_name}",
                 _base_template("New Tenant Onboarded", body))
