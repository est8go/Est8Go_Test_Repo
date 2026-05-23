import resend
import os

resend.api_key = os.getenv("RESEND_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "Est8Go <onboarding@resend.dev>")
BASE_URL = os.getenv("BASE_URL", "https://est8go-api.onrender.com")

# Inline style constants — email clients strip CSS classes
_P  = 'style="font-size:14px;line-height:1.6;color:#475569;margin:0 0 16px;font-family:Arial,sans-serif"'
_EM = 'style="color:#10B981;font-weight:600"'
_WN = 'style="color:#F59E0B;font-weight:700"'
_BTN = (
    'style="display:inline-block;background:#4338CA;color:#ffffff;'
    'text-decoration:none;padding:14px 28px;border-radius:12px;'
    'font-weight:700;font-size:14px;margin:8px 0 20px;'
    'font-family:Arial,sans-serif"'
)


def _send(to: str, subject: str, html: str) -> bool:
    try:
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to":   to,
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
    </head>
    <body style="margin:0;padding:0;background:#F4F6FF;
                 font-family:Arial,sans-serif;color:#0A0F2C">
      <table width="100%" cellpadding="0" cellspacing="0"
             style="background:#F4F6FF;padding:40px 20px">
        <tr><td align="center">
          <table width="100%" style="max-width:520px;background:#ffffff;
                 border-radius:20px;overflow:hidden;
                 box-shadow:0 4px 24px rgba(14,27,64,0.08)">

            <!-- HEADER -->
            <tr>
              <td style="background:#0E1B40;padding:28px 32px">
                <div style="font-size:26px;font-weight:800;
                            letter-spacing:-1px;color:#ffffff;
                            font-family:Arial,sans-serif">
                  Est<span style="color:#10B981">8</span>Go
                </div>
                <div style="font-size:10px;color:rgba(255,255,255,0.5);
                            letter-spacing:0.2em;text-transform:uppercase;
                            margin-top:4px">
                  Truth as a Service
                </div>
              </td>
            </tr>

            <!-- BODY -->
            <tr>
              <td style="padding:32px 32px 24px">
                <h2 style="font-size:20px;font-weight:700;
                           color:#0A0F2C;margin:0 0 16px;
                           font-family:Arial,sans-serif">
                  {title}
                </h2>
                {body}
              </td>
            </tr>

            <!-- FOOTER -->
            <tr>
              <td style="background:#F8FAFC;padding:20px 32px;
                         border-top:1px solid #E2E8F0">
                <p style="font-size:11px;color:#94A3B8;margin:0;
                          line-height:1.5;font-family:Arial,sans-serif">
                  Est8Go Service Limited &middot;
                  Trust Infrastructure for African Real Estate<br/>
                  If you did not request this, ignore this email
                  or contact support.
                </p>
              </td>
            </tr>

          </table>
        </td></tr>
      </table>
    </body>
    </html>"""


def send_password_reset(to_email: str, reset_url: str, name: str = "") -> bool:
    body = f"""
    <p {_P}>Hi {name or 'there'},</p>
    <p {_P}>We received a request to reset your Est8Go password.
       Click the button below to create a new password.</p>
    <a href="{reset_url}" {_BTN}>Reset My Password</a>
    <p {_P}>This link expires in <span {_WN}>1 hour</span>.
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
    <p {_P}>A staff member has requested a role elevation on Est8Go.</p>
    <p {_P}>
      <strong>Requester:</strong> {requester_name} ({requester_email})<br/>
      <strong>Requested Role:</strong> <span {_EM}>{requested_role}</span>
    </p>
    <p {_P}>Log in to your Super Admin dashboard to review and approve or reject
       this request. You will be asked to confirm with your password.</p>
    <a href="{approve_url}" {_BTN}>Review Request</a>
    <p {_P}>This request will expire in <span {_WN}>24 hours</span>
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
    <p {_P}>Hi {name},</p>
    <p {_P}>Your role elevation request has been
       <span {_EM}>approved</span>.</p>
    <p {_P}>
      <strong>New Role:</strong> <span {_EM}>{new_role}</span><br/>
      <strong>Duration:</strong> <span {_WN}>{expiry_hours} hours</span>
    </p>
    <p {_P}>Your role will automatically revert after this period.
       Please use elevated permissions responsibly —
       all actions are logged.</p>
    <a href="{BASE_URL}/public/login" {_BTN}>Login to Dashboard</a>"""
    return _send(to_email, "Role elevation approved",
                 _base_template("Role Elevation Approved", body))


def send_role_change_rejected(
    to_email: str,
    name: str,
    requested_role: str,
) -> bool:
    body = f"""
    <p {_P}>Hi {name},</p>
    <p {_P}>Your request for <span {_WN}>{requested_role}</span>
       elevation has been reviewed and was not approved at this time.</p>
    <p {_P}>If you believe this was an error, please contact your
       platform administrator directly.</p>"""
    return _send(to_email, "Role elevation not approved",
                 _base_template("Role Request Update", body))


def send_role_reverted(to_email: str, name: str, reverted_role: str) -> bool:
    body = f"""
    <p {_P}>Hi {name},</p>
    <p {_P}>Your temporary role elevation has expired and your role
       has been automatically reverted to
       <span {_EM}>{reverted_role}</span>.</p>
    <p {_P}>Contact your platform administrator if you need
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
    <p {_P}>You have been invited to join Est8Go —
       Nigeria's verified real estate trust platform.</p>
    <p {_P}>
      <strong>Plan:</strong> <span {_EM}>{plan}</span><br/>
      <strong>Invited by:</strong> {invited_by}<br/>
      <strong>Link expires:</strong> <span {_WN}>{expiry_hours} hours</span>
    </p>
    <p {_P}>Click below to set up your account and start verifying
       properties with GPS, AI audits, and document scoring.</p>
    <a href="{signup_url}" {_BTN}>Complete My Setup &rarr;</a>"""
    return _send(to_email, "Your Est8Go invitation is ready",
                 _base_template("You're Invited to Est8Go", body))


def send_onboarding_complete(
    admin_email: str,
    tenant_name: str,
    tenant_email: str,
    plan: str,
) -> bool:
    body = f"""
    <p {_P}>A new tenant has completed onboarding on Est8Go.</p>
    <p {_P}>
      <strong>Business:</strong> {tenant_name}<br/>
      <strong>Email:</strong> {tenant_email}<br/>
      <strong>Plan:</strong> <span {_EM}>{plan}</span>
    </p>
    <p {_P}>Their account is now active. You can manage them from
       the Tenants tab in your Super Admin dashboard.</p>
    <a href="{BASE_URL}/public/super-admin-portal" {_BTN}>
      View in Dashboard
    </a>"""
    return _send(admin_email, f"New tenant onboarded: {tenant_name}",
                 _base_template("New Tenant Onboarded", body))
