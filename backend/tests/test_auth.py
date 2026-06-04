"""Tests for authentication API endpoints.

Validates Requirements 8.1-8.16.
"""

import pytest
from unittest.mock import patch


class TestRegister:
    """Tests for POST /api/v1/auth/register."""

    def test_register_success(self, client, valid_user_data):
        """Req 8.1: Registration with valid email and password succeeds."""
        response = client.post("/api/v1/auth/register", json=valid_user_data)
        assert response.status_code == 201
        data = response.json()
        assert "message" in data

    def test_register_invalid_email_format(self, client):
        """Req 8.2: Invalid email format is rejected."""
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "password": "StrongPass1!"},
        )
        assert response.status_code == 422

    def test_register_duplicate_email(self, client, valid_user_data):
        """Req 8.3: Duplicate email registration is rejected."""
        client.post("/api/v1/auth/register", json=valid_user_data)
        response = client.post("/api/v1/auth/register", json=valid_user_data)
        assert response.status_code == 409

    def test_register_weak_password_no_uppercase(self, client):
        """Req 8.4: Password without uppercase is rejected."""
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "weakpass1!"},
        )
        assert response.status_code == 422

    def test_register_weak_password_no_digit(self, client):
        """Req 8.4: Password without digit is rejected."""
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "WeakPass!!"},
        )
        assert response.status_code == 422

    def test_register_weak_password_no_special(self, client):
        """Req 8.4: Password without special character is rejected."""
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "WeakPass11"},
        )
        assert response.status_code == 422

    def test_register_weak_password_too_short(self, client):
        """Req 8.4: Password shorter than 8 characters is rejected."""
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "Sh1!"},
        )
        assert response.status_code == 422

    def test_register_password_hashed_with_bcrypt(self, client, db_session, valid_user_data):
        """Req 8.6: Password is stored with bcrypt hash."""
        client.post("/api/v1/auth/register", json=valid_user_data)
        from app.models.user import User

        user = db_session.query(User).filter_by(email=valid_user_data["email"]).first()
        assert user is not None
        # bcrypt hashes start with $2b$
        assert user.password_hash.startswith("$2b$")
        # Verify cost factor >= 12
        cost_factor = int(user.password_hash.split("$")[2])
        assert cost_factor >= 12


class TestLogin:
    """Tests for POST /api/v1/auth/login."""

    def test_login_success(self, client, registered_user):
        """Req 8.8: Valid credentials return JWT token."""
        response = client.post("/api/v1/auth/login", json=registered_user)
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 24 * 3600

    def test_login_sets_httponly_cookie(self, client, registered_user):
        """Req 8.13: Login sets HTTP-only secure cookie."""
        response = client.post("/api/v1/auth/login", json=registered_user)
        assert response.status_code == 200
        # Check that cookie is set
        cookies = response.cookies
        assert "access_token" in cookies

    def test_login_invalid_email(self, client, registered_user):
        """Req 8.9: Invalid email returns generic error."""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "wrong@example.com", "password": registered_user["password"]},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password"

    def test_login_invalid_password(self, client, registered_user):
        """Req 8.9: Invalid password returns same generic error as invalid email."""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": registered_user["email"], "password": "WrongPass1!"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password"

    def test_login_account_lockout_after_5_failures(self, client, registered_user):
        """Req 8.10: Account locks after 5 consecutive failed attempts."""
        for i in range(5):
            response = client.post(
                "/api/v1/auth/login",
                json={"email": registered_user["email"], "password": "WrongPass1!"},
            )
            assert response.status_code == 401

        # 6th attempt should get locked response
        response = client.post(
            "/api/v1/auth/login",
            json={"email": registered_user["email"], "password": registered_user["password"]},
        )
        assert response.status_code == 423

    def test_login_success_resets_failed_count(self, client, registered_user):
        """Successful login resets the failed login counter."""
        # Fail 3 times
        for _ in range(3):
            client.post(
                "/api/v1/auth/login",
                json={"email": registered_user["email"], "password": "WrongPass1!"},
            )

        # Succeed
        response = client.post("/api/v1/auth/login", json=registered_user)
        assert response.status_code == 200

        # Fail 4 more times (should not lock since counter was reset)
        for _ in range(4):
            client.post(
                "/api/v1/auth/login",
                json={"email": registered_user["email"], "password": "WrongPass1!"},
            )

        # Should still be able to login (not locked yet, only 4 failures)
        response = client.post("/api/v1/auth/login", json=registered_user)
        assert response.status_code == 200


class TestLogout:
    """Tests for POST /api/v1/auth/logout."""

    def test_logout_success(self, client, registered_user):
        """Req 8.15: Logout invalidates session."""
        # Login first
        login_response = client.post("/api/v1/auth/login", json=registered_user)
        token = login_response.json()["access_token"]

        # Logout
        response = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Logged out successfully"

    def test_logout_without_token(self, client):
        """Logout without token still returns success (graceful)."""
        response = client.post("/api/v1/auth/logout")
        assert response.status_code == 200


class TestPasswordReset:
    """Tests for password reset endpoints."""

    def test_reset_request_registered_email(self, client, registered_user):
        """Req 8.11: Reset request for registered email returns success."""
        response = client.post(
            "/api/v1/auth/password/reset-request",
            json={"email": registered_user["email"]},
        )
        assert response.status_code == 200

    def test_reset_request_unregistered_email(self, client):
        """Req 8.9: Reset request for unregistered email also returns success (no info leak)."""
        response = client.post(
            "/api/v1/auth/password/reset-request",
            json={"email": "nonexistent@example.com"},
        )
        assert response.status_code == 200

    def test_password_reset_with_valid_token(self, client, registered_user, db_session):
        """Req 8.11: Password reset with valid token succeeds."""
        from app.core.security import create_reset_token
        from app.models.user import User

        user = db_session.query(User).filter_by(email=registered_user["email"]).first()
        token = create_reset_token(str(user.id))

        response = client.post(
            "/api/v1/auth/password/reset",
            json={"token": token, "new_password": "NewStrong1!"},
        )
        assert response.status_code == 200

        # Verify can login with new password
        response = client.post(
            "/api/v1/auth/login",
            json={"email": registered_user["email"], "password": "NewStrong1!"},
        )
        assert response.status_code == 200

    def test_password_reset_invalid_token(self, client):
        """Invalid reset token is rejected."""
        response = client.post(
            "/api/v1/auth/password/reset",
            json={"token": "invalid-token", "new_password": "NewStrong1!"},
        )
        assert response.status_code == 400

    def test_password_reset_weak_new_password(self, client, registered_user, db_session):
        """Req 8.4: New password must meet complexity requirements."""
        from app.core.security import create_reset_token
        from app.models.user import User

        user = db_session.query(User).filter_by(email=registered_user["email"]).first()
        token = create_reset_token(str(user.id))

        response = client.post(
            "/api/v1/auth/password/reset",
            json={"token": token, "new_password": "weak"},
        )
        assert response.status_code == 422


class TestJWTToken:
    """Tests for JWT token behavior."""

    def test_token_contains_user_id(self, client, registered_user):
        """Req 8.12: Token contains user identity."""
        from app.core.security import decode_access_token

        response = client.post("/api/v1/auth/login", json=registered_user)
        token = response.json()["access_token"]
        payload = decode_access_token(token)
        assert payload is not None
        assert "sub" in payload
        assert "exp" in payload

    def test_token_expires_in_24_hours(self, client, registered_user):
        """Req 8.12: Token has 24-hour expiration."""
        from app.core.security import decode_access_token

        response = client.post("/api/v1/auth/login", json=registered_user)
        token = response.json()["access_token"]
        payload = decode_access_token(token)
        # Check expiration is approximately 24 hours from now
        import time

        exp = payload["exp"]
        iat = payload["iat"]
        assert (exp - iat) == 24 * 3600
