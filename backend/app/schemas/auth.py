"""Authentication request/response schemas."""

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """User registration request."""

    email: str = Field(..., max_length=255, description="User email address")
    password: str = Field(..., min_length=8, max_length=128, description="User password")


class LoginRequest(BaseModel):
    """User login request."""

    email: str = Field(..., max_length=255, description="User email address")
    password: str = Field(..., max_length=128, description="User password")


class PasswordResetRequest(BaseModel):
    """Password reset request (send email)."""

    email: str = Field(..., max_length=255, description="User email address")


class PasswordReset(BaseModel):
    """Password reset execution."""

    token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")


class AuthResponse(BaseModel):
    """Generic auth response."""

    message: str


class LoginResponse(BaseModel):
    """Login success response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Token expiration time in seconds")


class ErrorResponse(BaseModel):
    """Error response."""

    detail: str
