"""JWT authentication dependency.

Extracts and validates JWT tokens from requests, returning the authenticated user.
Requirements: 8.17, 8.23
"""

import uuid

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.database import get_db
from ..core.security import decode_access_token
from ..models.user import User


def _get_redis_client():
    """Get Redis client for token blacklist checks.

    Returns None if Redis is not available (graceful degradation).
    """
    try:
        import redis

        client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        client.ping()
        return client
    except Exception:
        return None


def _extract_token(
    authorization: str | None = Header(None),
    access_token: str | None = Cookie(None),
) -> str | None:
    """Extract JWT token from Authorization header or cookie."""
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:]
    return access_token


def get_current_user(
    token: str | None = Depends(_extract_token),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency that authenticates the request and returns the current user.

    Validates the JWT token by:
    1. Checking the token is present
    2. Decoding and verifying signature/expiry
    3. Checking the token is not blacklisted (via Redis)
    4. Loading the user from the database

    Raises:
        HTTPException 401: If token is missing, invalid, expired, or blacklisted
        HTTPException 401: If the user referenced by the token does not exist

    Returns:
        The authenticated User model instance.
    """
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Decode and validate token (checks signature and expiry)
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check token blacklist via Redis
    redis_client = _get_redis_client()
    if redis_client:
        is_blacklisted = redis_client.get(f"blacklist:{token}")
        if is_blacklisted:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Extract user ID from token
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = uuid.UUID(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Load user from database
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if account is locked
    if user.is_locked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is locked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
