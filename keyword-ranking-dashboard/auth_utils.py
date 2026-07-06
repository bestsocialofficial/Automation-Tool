"""Password hashing helpers shared by dashboard.py and manage_users.py."""

import hashlib
import hmac
import secrets

ITERATIONS = 200_000


def hash_password(password, salt=None):
    """Return (salt_hex, digest_hex) for the given password."""
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), ITERATIONS
    ).hex()
    return salt, digest


def verify_password(password, salt, expected_digest):
    _, digest = hash_password(password, salt)
    return hmac.compare_digest(digest, expected_digest)
