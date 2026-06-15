import os
import logging
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_KEY = os.getenv("ENCRYPTION_KEY")
_fernet = None

if _KEY:
    try:
        _fernet = Fernet(
            _KEY.encode() if isinstance(_KEY, str) else _KEY
        )
    except Exception as e:
        logger.error(f"Invalid ENCRYPTION_KEY: {e}")
        _fernet = None
else:
    logger.warning(
        "ENCRYPTION_KEY not set — token "
        "encryption disabled"
    )


def encrypt_secret(plaintext: str) -> str | None:
    """Encrypt a secret for storage. Returns
    None if input is empty or encryption
    unavailable."""
    if not plaintext:
        return None
    if not _fernet:
        raise RuntimeError(
            "ENCRYPTION_KEY not configured — "
            "cannot encrypt secret"
        )
    return _fernet.encrypt(
        plaintext.encode()
    ).decode()


def decrypt_secret(ciphertext: str) -> str | None:
    """Decrypt a stored secret. Returns None
    if input empty. Raises on tamper/wrong
    key."""
    if not ciphertext:
        return None
    if not _fernet:
        raise RuntimeError(
            "ENCRYPTION_KEY not configured — "
            "cannot decrypt secret"
        )
    try:
        return _fernet.decrypt(
            ciphertext.encode()
        ).decode()
    except InvalidToken:
        logger.error(
            "Failed to decrypt secret — "
            "wrong key or tampered data"
        )
        raise


def is_encryption_ready() -> bool:
    """True if encryption is configured
    and usable."""
    return _fernet is not None
