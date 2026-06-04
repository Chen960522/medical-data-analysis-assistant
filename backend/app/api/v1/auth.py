"""Authentication API routes.

Implements user registration, login, logout, and password reset.
Requirements: 8.1-8.16
"""

import uuid as uuid_mod
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.database import get_db
from ...core.security import (
    create_access_token,
    create_reset_token,
    decode_access_token,
    decode_reset_token,
    hash_password,
    validate_email_format,
    validate_password_complexity,
    verify_password,
)
from ...models.user import User
from ...schemas.auth import (
    AuthResponse,
    LoginRequest,
    LoginResponse,
    PasswordReset,
    PasswordResetRequest,
    RegisterRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Generic error message to avoid revealing specific failure reasons (Req 8.9)
GENERIC_AUTH_ERROR = "Invalid email or password"
GENERIC_REGISTER_SUCCESS = "Registration successful. Please check your email to verify your account."
GENERIC_RESET_REQUEST_SUCCESS = "If the email is registered, a password reset link has been sent."
GENERIC_RESET_SUCCESS = "Password has been reset successfully."


def _get_redis_client():
    """Get Redis client for token blacklist and session management.

    Returns None if Redis is not available (graceful degradation).
    """
    try:
        import redis

        client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        client.ping()  # Test connection
        return client
    except Exception:
        return None


def _extract_token(
    authorization: str | None = Header(None),
    access_token: str | None = Cookie(None),
) -> str | None:
    """Extract token from Authorization header or cookie."""
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:]
    return access_token


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    """Register a new user account.

    - Validates email format and uniqueness
    - Validates password complexity
    - Stores password with bcrypt hash (cost factor >= 12)
    - Sends verification email (placeholder)
    """
    # Validate email format (Req 8.2)
    if not validate_email_format(request.email):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid email format",
        )

    # Validate password complexity (Req 8.4)
    is_valid, error_msg = validate_password_complexity(request.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error_msg,
        )

    # Check email uniqueness (Req 8.2, 8.3)
    existing_user = db.execute(select(User).where(User.email == request.email.lower())).scalar_one_or_none()
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered",
        )

    # Create user with hashed password (Req 8.6)
    user = User(
        email=request.email.lower(),
        password_hash=hash_password(request.password),
        is_verified=False,
        is_locked=False,
        failed_login_count=0,
    )
    db.add(user)
    db.commit()

    # Send verification email (Req 8.5) - placeholder
    _send_verification_email(user.email, str(user.id))

    return AuthResponse(message=GENERIC_REGISTER_SUCCESS)


@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, response: Response, db: Session = Depends(get_db)) -> LoginResponse:
    """Authenticate user and issue JWT token.

    - Validates credentials
    - Tracks failed login attempts
    - Locks account after 5 consecutive failures for 15 minutes (Req 8.10)
    - Issues JWT with 24-hour expiration (Req 8.12)
    - Sets HTTP-only secure cookie (Req 8.13)
    - Enforces single active session (Req 8.16)
    """
    # Find user by email
    user = db.execute(select(User).where(User.email == request.email.lower())).scalar_one_or_none()

    if user is None:
        # Generic error - don't reveal that email doesn't exist (Req 8.9)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=GENERIC_AUTH_ERROR,
        )

    # Check if account is locked (Req 8.10)
    if user.is_locked and user.locked_until:
        locked_until = user.locked_until
        # Ensure timezone-aware comparison
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) < locked_until:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account is temporarily locked. Please try again later.",
            )
        else:
            # Lock period expired, unlock the account
            user.is_locked = False
            user.failed_login_count = 0
            user.locked_until = None
            db.commit()

    # Verify password
    if not verify_password(request.password, user.password_hash):
        # Increment failed login count (Req 8.10)
        user.failed_login_count += 1
        if user.failed_login_count >= settings.max_login_attempts:
            user.is_locked = True
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=settings.account_lockout_minutes)
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=GENERIC_AUTH_ERROR,
        )

    # Successful login - reset failed count
    user.failed_login_count = 0
    user.is_locked = False
    user.locked_until = None
    db.commit()

    # Invalidate previous sessions (Req 8.16 - single active session)
    redis_client = _get_redis_client()
    if redis_client:
        # Invalidate old session token
        old_token_key = f"user_session:{user.id}"
        old_token = redis_client.get(old_token_key)
        if old_token:
            redis_client.setex(f"blacklist:{old_token}", settings.jwt_access_token_expire_hours * 3600, "1")

    # Create new JWT token (Req 8.12)
    access_token = create_access_token(str(user.id))
    expires_in = settings.jwt_access_token_expire_hours * 3600

    # Store current session in Redis (Req 8.16)
    if redis_client:
        redis_client.setex(f"user_session:{user.id}", expires_in, access_token)

    # Set HTTP-only secure cookie (Req 8.13)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=expires_in,
    )

    return LoginResponse(access_token=access_token, expires_in=expires_in)


@router.post("/logout", response_model=AuthResponse)
def logout(response: Response, token: str = Depends(_extract_token)) -> AuthResponse:
    """Logout user and invalidate token.

    - Invalidates current session immediately (Req 8.15)
    - Clears session cookie
    """
    if token:
        payload = decode_access_token(token)
        if payload:
            redis_client = _get_redis_client()
            if redis_client:
                # Add token to blacklist
                exp = payload.get("exp", 0)
                now = int(datetime.now(timezone.utc).timestamp())
                ttl = max(exp - now, 0)
                if ttl > 0:
                    redis_client.setex(f"blacklist:{token}", ttl, "1")
                # Remove user session
                user_id = payload.get("sub")
                if user_id:
                    redis_client.delete(f"user_session:{user_id}")

    # Clear cookie
    response.delete_cookie(key="access_token", httponly=True, secure=True, samesite="lax")

    return AuthResponse(message="Logged out successfully")


@router.post("/password/reset-request", response_model=AuthResponse)
def password_reset_request(request: PasswordResetRequest, db: Session = Depends(get_db)) -> AuthResponse:
    """Request a password reset email.

    - Always returns success to avoid revealing registered emails (Req 8.9)
    - Sends reset link if email exists (Req 8.11)
    """
    user = db.execute(select(User).where(User.email == request.email.lower())).scalar_one_or_none()

    if user is not None:
        # Generate reset token and send email
        reset_token = create_reset_token(str(user.id))
        _send_password_reset_email(user.email, reset_token)

    # Always return success (Req 8.9 - don't reveal if email exists)
    return AuthResponse(message=GENERIC_RESET_REQUEST_SUCCESS)


@router.post("/password/reset", response_model=AuthResponse)
def password_reset(request: PasswordReset, db: Session = Depends(get_db)) -> AuthResponse:
    """Reset password using a valid reset token.

    - Validates reset token
    - Validates new password complexity
    - Updates password hash
    """
    # Validate new password complexity
    is_valid, error_msg = validate_password_complexity(request.new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error_msg,
        )

    # Decode and validate reset token
    payload = decode_reset_token(request.token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    user_id = payload.get("sub")
    try:
        user_id_uuid = uuid_mod.UUID(user_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )
    user = db.execute(select(User).where(User.id == user_id_uuid)).scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    # Update password
    user.password_hash = hash_password(request.new_password)
    user.failed_login_count = 0
    user.is_locked = False
    user.locked_until = None
    db.commit()

    # Invalidate all existing sessions
    redis_client = _get_redis_client()
    if redis_client:
        old_token = redis_client.get(f"user_session:{user.id}")
        if old_token:
            redis_client.setex(f"blacklist:{old_token}", settings.jwt_access_token_expire_hours * 3600, "1")
        redis_client.delete(f"user_session:{user.id}")

    return AuthResponse(message=GENERIC_RESET_SUCCESS)


def _send_verification_email(email: str, user_id: str) -> None:
    """Send verification email (placeholder implementation).

    In production, this would use SMTP or SES to send the email.
    """
    # TODO: Implement actual email sending
    pass


def _send_password_reset_email(email: str, reset_token: str) -> None:
    """Send password reset email (placeholder implementation).

    In production, this would use SMTP or SES to send the email.
    """
    # TODO: Implement actual email sending
    pass
