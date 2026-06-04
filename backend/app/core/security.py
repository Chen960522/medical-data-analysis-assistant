"""Security utilities: password hashing, JWT token management."""

import re
import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import settings

# Configure bcrypt with cost factor >= 12
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=settings.bcrypt_cost_factor,
    bcrypt__ident="2b",
)

# Email regex pattern (RFC 5322 simplified)
EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"
)

# Password complexity pattern
PASSWORD_MIN_LENGTH = 8
PASSWORD_UPPERCASE = re.compile(r"[A-Z]")
PASSWORD_LOWERCASE = re.compile(r"[a-z]")
PASSWORD_DIGIT = re.compile(r"\d")
PASSWORD_SPECIAL = re.compile(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?~`]")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt with configured cost factor."""
    return pwd_context.hash(password)


def validate_email_format(email: str) -> bool:
    """Validate email format."""
    if not email or len(email) > 255:
        return False
    return bool(EMAIL_REGEX.match(email))


def validate_password_complexity(password: str) -> tuple[bool, str]:
    """Validate password meets complexity requirements.

    Returns:
        Tuple of (is_valid, error_message).
    """
    if len(password) < PASSWORD_MIN_LENGTH:
        return False, f"Password must be at least {PASSWORD_MIN_LENGTH} characters long"
    if not PASSWORD_UPPERCASE.search(password):
        return False, "Password must contain at least one uppercase letter"
    if not PASSWORD_LOWERCASE.search(password):
        return False, "Password must contain at least one lowercase letter"
    if not PASSWORD_DIGIT.search(password):
        return False, "Password must contain at least one digit"
    if not PASSWORD_SPECIAL.search(password):
        return False, "Password must contain at least one special character"
    return True, ""


def create_access_token(user_id: str, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token."""
    if expires_delta is None:
        expires_delta = timedelta(hours=settings.jwt_access_token_expire_hours)

    now = datetime.now(timezone.utc)
    expire = now + expires_delta
    to_encode = {
        "sub": user_id,
        "exp": expire,
        "iat": now,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    """Decode and validate a JWT access token.

    Returns:
        Token payload dict if valid, None otherwise.
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        return None


def create_reset_token(user_id: str) -> str:
    """Create a password reset token (short-lived, 1 hour)."""
    expires_delta = timedelta(hours=1)
    now = datetime.now(timezone.utc)
    expire = now + expires_delta
    to_encode = {
        "sub": user_id,
        "exp": expire,
        "iat": now,
        "type": "password_reset",
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_reset_token(token: str) -> dict | None:
    """Decode and validate a password reset token.

    Returns:
        Token payload dict if valid and type is password_reset, None otherwise.
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "password_reset":
            return None
        return payload
    except JWTError:
        return None
