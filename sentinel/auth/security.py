"""Maintained password hashing and standard opaque-token digests."""
import hashlib
import secrets
from argon2 import PasswordHasher, Type
from argon2.exceptions import VerificationError, InvalidHashError
from email_validator import validate_email, EmailNotValidError

HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, type=Type.ID)
# Equal-cost verification for unknown and external-only identities. Not a login credential.
DUMMY_HASH = HASHER.hash(secrets.token_urlsafe(32))


def normalize_email(value):
    try:
        # Product policy: case-insensitive ASCII mailbox identity; no provider-specific dot/plus rewriting.
        return validate_email(value.strip(), check_deliverability=False, allow_smtputf8=False).ascii_email.lower()
    except (EmailNotValidError, AttributeError):
        raise ValueError('Invalid email address') from None


def hash_password(value):
    if not isinstance(value, str) or not 12 <= len(value) <= 128:
        raise ValueError('Password must contain 12 to 128 characters')
    return HASHER.hash(value)


def verify_password(stored, password):
    try:
        return HASHER.verify(stored or DUMMY_HASH, password) and stored is not None
    except (VerificationError, InvalidHashError):
        return False


def digest(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def new_token():
    return secrets.token_urlsafe(32)
