"""Tests for data access control middleware.

Validates:
- Unauthenticated requests are rejected with 401
- Requests with expired/invalid tokens are rejected
- Users cannot access other users' resources (403)
- User-scoped queries only return the user's own data

Requirements: 8.17-8.23
"""

import uuid
from datetime import timedelta

import pytest
from fastapi import Depends, FastAPI, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.middleware import get_current_user, get_user_scoped_query, verify_resource_ownership
from app.middleware.access_control import get_resource_or_deny
from app.models.base import Base
from app.models.data import DataFile
from app.models.user import User


@pytest.fixture
def db_engine():
    """Create an in-memory SQLite database engine for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(db_engine):
    """Create a database session for testing."""
    TestingSessionLocal = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    """Create a test client with overridden database dependency."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def user_a(db_session):
    """Create test user A."""
    from app.core.security import hash_password

    user = User(
        email="user_a@example.com",
        password_hash=hash_password("StrongPass1!"),
        is_verified=True,
        is_locked=False,
        failed_login_count=0,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def user_b(db_session):
    """Create test user B."""
    from app.core.security import hash_password

    user = User(
        email="user_b@example.com",
        password_hash=hash_password("StrongPass2!"),
        is_verified=True,
        is_locked=False,
        failed_login_count=0,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def user_a_token(user_a):
    """Create a valid JWT token for user A."""
    return create_access_token(str(user_a.id))


@pytest.fixture
def user_b_token(user_b):
    """Create a valid JWT token for user B."""
    return create_access_token(str(user_b.id))


@pytest.fixture
def user_a_file(db_session, user_a):
    """Create a data file owned by user A."""
    file = DataFile(
        user_id=user_a.id,
        filename="test_file_a.csv",
        original_filename="test_file_a.csv",
        file_size=1024,
        file_format="csv",
        s3_key="uploads/user_a/test_file_a.csv",
        status="uploaded",
    )
    db_session.add(file)
    db_session.commit()
    db_session.refresh(file)
    return file


@pytest.fixture
def user_b_file(db_session, user_b):
    """Create a data file owned by user B."""
    file = DataFile(
        user_id=user_b.id,
        filename="test_file_b.csv",
        original_filename="test_file_b.csv",
        file_size=2048,
        file_format="csv",
        s3_key="uploads/user_b/test_file_b.csv",
        status="uploaded",
    )
    db_session.add(file)
    db_session.commit()
    db_session.refresh(file)
    return file


# --- Test: Unauthenticated requests rejected with 401 ---


class TestAuthentication:
    """Test JWT authentication dependency (Req 8.23)."""

    def test_no_token_returns_401(self, client, db_session):
        """Request without any token should be rejected."""
        test_app = FastAPI()

        def override_get_db():
            try:
                yield db_session
            finally:
                pass

        test_app.dependency_overrides[get_db] = override_get_db

        @test_app.get("/protected")
        def protected_endpoint(current_user: User = Depends(get_current_user)):
            return {"user_id": str(current_user.id)}

        with TestClient(test_app) as tc:
            response = tc.get("/protected")
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_invalid_token_returns_401(self, client, db_session):
        """Request with an invalid token should be rejected."""
        test_app = FastAPI()

        def override_get_db():
            try:
                yield db_session
            finally:
                pass

        test_app.dependency_overrides[get_db] = override_get_db

        @test_app.get("/protected")
        def protected_endpoint(current_user: User = Depends(get_current_user)):
            return {"user_id": str(current_user.id)}

        with TestClient(test_app) as tc:
            response = tc.get(
                "/protected",
                headers={"Authorization": "Bearer invalid.token.here"},
            )
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_expired_token_returns_401(self, client, db_session, user_a):
        """Request with an expired token should be rejected."""
        # Create a token that's already expired
        expired_token = create_access_token(str(user_a.id), expires_delta=timedelta(seconds=-1))

        test_app = FastAPI()

        def override_get_db():
            try:
                yield db_session
            finally:
                pass

        test_app.dependency_overrides[get_db] = override_get_db

        @test_app.get("/protected")
        def protected_endpoint(current_user: User = Depends(get_current_user)):
            return {"user_id": str(current_user.id)}

        with TestClient(test_app) as tc:
            response = tc.get(
                "/protected",
                headers={"Authorization": f"Bearer {expired_token}"},
            )
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_valid_token_returns_user(self, db_session, user_a, user_a_token):
        """Request with a valid token should return the user."""
        test_app = FastAPI()

        def override_get_db():
            try:
                yield db_session
            finally:
                pass

        test_app.dependency_overrides[get_db] = override_get_db

        @test_app.get("/protected")
        def protected_endpoint(current_user: User = Depends(get_current_user)):
            return {"user_id": str(current_user.id), "email": current_user.email}

        with TestClient(test_app) as tc:
            response = tc.get(
                "/protected",
                headers={"Authorization": f"Bearer {user_a_token}"},
            )
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["user_id"] == str(user_a.id)
            assert data["email"] == "user_a@example.com"

    def test_token_for_nonexistent_user_returns_401(self, db_session):
        """Token referencing a non-existent user should be rejected."""
        fake_user_id = str(uuid.uuid4())
        token = create_access_token(fake_user_id)

        test_app = FastAPI()

        def override_get_db():
            try:
                yield db_session
            finally:
                pass

        test_app.dependency_overrides[get_db] = override_get_db

        @test_app.get("/protected")
        def protected_endpoint(current_user: User = Depends(get_current_user)):
            return {"user_id": str(current_user.id)}

        with TestClient(test_app) as tc:
            response = tc.get(
                "/protected",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_locked_user_returns_401(self, db_session, user_a, user_a_token):
        """Token for a locked user should be rejected."""
        user_a.is_locked = True
        db_session.commit()

        test_app = FastAPI()

        def override_get_db():
            try:
                yield db_session
            finally:
                pass

        test_app.dependency_overrides[get_db] = override_get_db

        @test_app.get("/protected")
        def protected_endpoint(current_user: User = Depends(get_current_user)):
            return {"user_id": str(current_user.id)}

        with TestClient(test_app) as tc:
            response = tc.get(
                "/protected",
                headers={"Authorization": f"Bearer {user_a_token}"},
            )
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_token_from_cookie(self, db_session, user_a, user_a_token):
        """Token provided via cookie should be accepted."""
        test_app = FastAPI()

        def override_get_db():
            try:
                yield db_session
            finally:
                pass

        test_app.dependency_overrides[get_db] = override_get_db

        @test_app.get("/protected")
        def protected_endpoint(current_user: User = Depends(get_current_user)):
            return {"user_id": str(current_user.id)}

        with TestClient(test_app, cookies={"access_token": user_a_token}) as tc:
            response = tc.get("/protected")
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["user_id"] == str(user_a.id)


# --- Test: User-scoped queries (Req 8.18, 8.22) ---


class TestUserScopedQuery:
    """Test that get_user_scoped_query filters data by user_id."""

    def test_scoped_query_returns_only_own_data(self, db_session, user_a, user_b, user_a_file, user_b_file):
        """User A's scoped query should only return user A's files (Req 8.18)."""
        query = select(DataFile)
        scoped_query = get_user_scoped_query(query, DataFile, user_a.id)
        results = db_session.execute(scoped_query).scalars().all()

        assert len(results) == 1
        assert results[0].id == user_a_file.id
        assert results[0].user_id == user_a.id

    def test_scoped_query_excludes_other_users_data(self, db_session, user_a, user_b, user_a_file, user_b_file):
        """User B's scoped query should not include user A's files (Req 8.22)."""
        query = select(DataFile)
        scoped_query = get_user_scoped_query(query, DataFile, user_b.id)
        results = db_session.execute(scoped_query).scalars().all()

        assert len(results) == 1
        assert results[0].id == user_b_file.id
        assert results[0].user_id == user_b.id

    def test_scoped_query_returns_empty_for_user_with_no_data(self, db_session, user_a, user_b_file):
        """User with no files should get empty results."""
        query = select(DataFile)
        scoped_query = get_user_scoped_query(query, DataFile, user_a.id)
        results = db_session.execute(scoped_query).scalars().all()

        assert len(results) == 0


# --- Test: Resource ownership verification (Req 8.20, 8.21) ---


class TestResourceOwnership:
    """Test verify_resource_ownership and get_resource_or_deny."""

    def test_verify_ownership_passes_for_owner(self, user_a, user_a_file):
        """Owner should pass ownership verification."""
        # Should not raise
        verify_resource_ownership(user_a_file, user_a.id, "file")

    def test_verify_ownership_raises_403_for_non_owner(self, user_b, user_a_file):
        """Non-owner should get 403 Forbidden (Req 8.21)."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            verify_resource_ownership(user_a_file, user_b.id, "file")

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    def test_verify_ownership_raises_404_for_none(self, user_a):
        """None resource should raise 404."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            verify_resource_ownership(None, user_a.id, "file")

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    def test_get_resource_or_deny_returns_owned_resource(self, db_session, user_a, user_a_file):
        """get_resource_or_deny should return the resource for the owner."""
        result = get_resource_or_deny(db_session, DataFile, user_a_file.id, user_a.id, "file")
        assert result.id == user_a_file.id

    def test_get_resource_or_deny_raises_403_for_non_owner(self, db_session, user_b, user_a_file):
        """get_resource_or_deny should raise 403 for non-owner (Req 8.21)."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            get_resource_or_deny(db_session, DataFile, user_a_file.id, user_b.id, "file")

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    def test_get_resource_or_deny_raises_404_for_nonexistent(self, db_session, user_a):
        """get_resource_or_deny should raise 404 for non-existent resource."""
        from fastapi import HTTPException

        fake_id = uuid.uuid4()
        with pytest.raises(HTTPException) as exc_info:
            get_resource_or_deny(db_session, DataFile, fake_id, user_a.id, "file")

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


# --- Test: Cross-user access denied (Req 8.21) via API endpoint ---


class TestCrossUserAccessDenied:
    """Integration test: cross-user access is denied at the API level."""

    def test_user_b_cannot_access_user_a_file_via_api(self, db_session, user_a, user_b, user_a_file, user_b_token):
        """User B should get 403 when trying to access user A's file (Req 8.21)."""
        test_app = FastAPI()

        def override_get_db():
            try:
                yield db_session
            finally:
                pass

        test_app.dependency_overrides[get_db] = override_get_db

        @test_app.get("/files/{file_id}")
        def get_file(file_id: uuid.UUID, current_user: User = Depends(get_current_user)):
            resource = get_resource_or_deny(db_session, DataFile, file_id, current_user.id, "file")
            return {"file_id": str(resource.id), "filename": resource.filename}

        with TestClient(test_app) as tc:
            response = tc.get(
                f"/files/{user_a_file.id}",
                headers={"Authorization": f"Bearer {user_b_token}"},
            )
            assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_owner_can_access_own_file_via_api(self, db_session, user_a, user_a_file, user_a_token):
        """Owner should be able to access their own file (Req 8.17)."""
        test_app = FastAPI()

        def override_get_db():
            try:
                yield db_session
            finally:
                pass

        test_app.dependency_overrides[get_db] = override_get_db

        @test_app.get("/files/{file_id}")
        def get_file(file_id: uuid.UUID, current_user: User = Depends(get_current_user)):
            resource = get_resource_or_deny(db_session, DataFile, file_id, current_user.id, "file")
            return {"file_id": str(resource.id), "filename": resource.filename}

        with TestClient(test_app) as tc:
            response = tc.get(
                f"/files/{user_a_file.id}",
                headers={"Authorization": f"Bearer {user_a_token}"},
            )
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["filename"] == "test_file_a.csv"
