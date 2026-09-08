"""
EST8GO SECURITY ENGINE v3.0
============================
Fort-Knox grade security for a platform fighting real estate fraud in Africa.

Token expiry tiers:
  superuser   → 1 hour   (re-auth required for destructive actions)
  super_staff → 8 hours
  admin       → 7 days
  realtor     → 7 days
  staff/etc   → 7 days

Additional protections:
  - IP binding on superuser tokens
  - Account lockout after 5 failed attempts (30 min)
  - Suspicious login detection
  - All security events written to audit log
"""

import os
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from dotenv import load_dotenv
from jose import jwt
from passlib.context import CryptContext

# Entrypoints other than app.main (scripts, workers) may import this module
# before any dotenv call. Load here so the check below sees backend/.env.
load_dotenv()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── JWT SIGNING KEY — NO FALLBACK ────────────────────────────────
# A hardcoded default silently signs every token in production with a
# value that is in the git history. Fail loudly at import time instead:
# app.main imports this module at startup, so an unset SECRET_KEY stops
# the deploy rather than shipping forgeable tokens.
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY is not set. Est8Go will not start without a JWT signing "
        "key. Set SECRET_KEY in the environment (Render -> Environment) "
        "or in backend/.env for local development."
    )

ALGORITHM = "HS256"

# ── TOKEN EXPIRY TIERS ───────────────────────────────────────────
TOKEN_EXPIRY = {
    "superuser": 60 * 1,  # 1 hour  — highest privilege
    "super_staff": 60 * 8,  # 8 hours — platform staff
    "admin": 60 * 24 * 7,  # 7 days  — tenant owner
    "realtor": 60 * 24 * 7,  # 7 days  — agent
    "staff": 60 * 24 * 7,  # 7 days
    "support": 60 * 24 * 7,
    "marketing": 60 * 24 * 7,
}

# ── LOCKOUT SETTINGS ─────────────────────────────────────────────
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 30

# In-memory lockout store
# In production: replace with Redis for persistence across server restarts
_failed_attempts: dict = {}  # email → {"count": int, "locked_until": datetime}


# ================================================================
# PASSWORD FUNCTIONS
# ================================================================


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password[:72])


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password[:72], hashed_password)
    except Exception:
        return False


hash_password = get_password_hash


# ================================================================
# ACCOUNT LOCKOUT
# ================================================================


def is_account_locked(email: str) -> bool:
    """Returns True if this account is currently locked out."""
    record = _failed_attempts.get(email)
    if not record:
        return False
    if record.get("locked_until") and datetime.utcnow() < record["locked_until"]:
        return True
    return False


def get_lockout_remaining(email: str) -> int:
    """Returns seconds remaining on lockout. 0 if not locked."""
    record = _failed_attempts.get(email)
    if not record or not record.get("locked_until"):
        return 0
    remaining = (record["locked_until"] - datetime.utcnow()).total_seconds()
    return max(0, int(remaining))


def record_failed_attempt(email: str) -> int:
    """
    Record a failed login attempt.
    Returns the number of attempts so far.
    Locks the account after MAX_FAILED_ATTEMPTS.
    """
    record = _failed_attempts.get(email, {"count": 0, "locked_until": None})

    # Reset if previous lockout has expired
    if record.get("locked_until") and datetime.utcnow() >= record["locked_until"]:
        record = {"count": 0, "locked_until": None}

    record["count"] += 1

    if record["count"] >= MAX_FAILED_ATTEMPTS:
        record["locked_until"] = datetime.utcnow() + timedelta(minutes=LOCKOUT_MINUTES)

    _failed_attempts[email] = record
    return record["count"]


def clear_failed_attempts(email: str):
    """Clear lockout record on successful login."""
    _failed_attempts.pop(email, None)


# ================================================================
# IP FINGERPRINTING
# ================================================================


def hash_ip(ip: str) -> str:
    """
    One-way hash of IP address for token binding.
    We store the hash, not the raw IP, for privacy compliance.
    """
    return hashlib.sha256(f"{ip}{SECRET_KEY}".encode()).hexdigest()[:16]


# ================================================================
# TOKEN CREATION
# ================================================================


def create_access_token(
    email: str,
    role: str,
    tenant_id: Optional[int] = None,
    ip_address: Optional[str] = None,
) -> str:
    """
    Create a signed JWT token with role-based expiry and optional IP binding.

    Superuser tokens are IP-bound — if the IP changes mid-session,
    the token is rejected. This prevents stolen token replay attacks.
    """
    expiry_minutes = TOKEN_EXPIRY.get(role, 60 * 24 * 7)
    expire = datetime.utcnow() + timedelta(minutes=expiry_minutes)

    payload = {
        "exp": expire,
        "sub": email,
        "role": role,
        "tenant_id": tenant_id,
        "iat": datetime.utcnow(),  # issued-at for audit
    }

    # IP bind superuser and super_staff tokens
    if role in ("superuser", "super_staff") and ip_address:
        payload["ip_hash"] = hash_ip(ip_address)

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# ================================================================
# TOKEN VERIFICATION
# ================================================================


def decode_token(token: str) -> dict:
    """Decode and return token payload. Raises JWTError if invalid."""
    from jose import jwt as _jwt

    return _jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


def verify_ip_binding(payload: dict, current_ip: str) -> bool:
    """
    For superuser/super_staff tokens: verify IP hasn't changed.
    Returns True if IP matches or token has no IP binding.
    """
    stored_hash = payload.get("ip_hash")
    if not stored_hash:
        return True  # Token has no IP binding — allow
    return stored_hash == hash_ip(current_ip)


# ================================================================
# RE-AUTHENTICATION FOR DESTRUCTIVE ACTIONS
# ================================================================


def create_reauth_token(email: str, action: str, ip_address: str) -> str:
    """
    Create a short-lived token (5 minutes) that authorises ONE specific
    destructive action. Required for:
      - Deleting a tenant
      - Overriding a trust grade
      - Deactivating a staff member
      - Changing billing plans
      - Any action flagged as destructive

    The action name is embedded in the token so it can only be used
    for the exact action it was issued for.
    """
    expire = datetime.utcnow() + timedelta(minutes=5)
    payload = {
        "exp": expire,
        "sub": email,
        "action": action,  # e.g. "delete_tenant", "trust_override"
        "ip_hash": hash_ip(ip_address),
        "type": "reauth",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_reauth_token(token: str, expected_action: str, current_ip: str) -> bool:
    """
    Verify a re-auth token for a specific destructive action.
    Returns True only if:
      1. Token is valid and not expired
      2. Token type is "reauth"
      3. Action matches exactly
      4. IP matches
    """
    try:
        payload = decode_token(token)
        if payload.get("type") != "reauth":
            return False
        if payload.get("action") != expected_action:
            return False
        if not verify_ip_binding(payload, current_ip):
            return False
        return True
    except Exception:
        return False
