"""Password hashing utilities using bcrypt.

Uses SHA256 pre-hashing for passwords to handle bcrypt's 72-byte limit.
This is the recommended approach from bcrypt documentation.
"""

import base64
import hashlib

import bcrypt


def _prepare_password(plain_password: str) -> bytes:
    """Prepare password for bcrypt by SHA256 hashing + base64 encoding.

    bcrypt has a 72-byte limit. SHA256+base64 produces consistent 44-byte output,
    ensuring any password length works safely.

    :param plain_password: Plain text password
    :return: Prepared password bytes
    """
    password_bytes = plain_password.encode("utf-8")
    sha256_hash = hashlib.sha256(password_bytes).digest()
    return base64.b64encode(sha256_hash)


def hash_password(plain_password: str) -> str:
    """Hash a plain text password using bcrypt.

    :param plain_password: Plain text password
    :return: Hashed password string
    """
    prepared = _prepare_password(plain_password)
    hashed = bcrypt.hashpw(prepared, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain text password against a hashed password.

    :param plain_password: Plain text password to verify
    :param hashed_password: Stored hashed password
    :return: True if password matches, False otherwise
    """
    prepared = _prepare_password(plain_password)
    return bcrypt.checkpw(prepared, hashed_password.encode("utf-8"))
