"""Tests for data file upload and management API.

Tests cover: upload, list, preview, quality, and delete endpoints.
Requirements: 1.1-1.7, 2.1-2.6
"""

import io
import json
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.main import app
from app.middleware.auth import get_current_user
from app.models.base import Base
from app.models.user import User


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database session for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_user(db_session):
    """Create a test user in the database."""
    user = User(
        id=uuid.uuid4(),
        email="testuser@example.com",
        password_hash="$2b$12$fakehash",
        is_verified=True,
        is_locked=False,
        failed_login_count=0,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def other_user(db_session):
    """Create another test user for isolation tests."""
    user = User(
        id=uuid.uuid4(),
        email="otheruser@example.com",
        password_hash="$2b$12$fakehash",
        is_verified=True,
        is_locked=False,
        failed_login_count=0,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def client(db_session, test_user):
    """Create a test client with overridden dependencies."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_get_current_user():
        return test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _make_client_for_user(db_session, user):
    """Create a test client authenticated as a specific user."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_get_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    return TestClient(app)


def _make_csv_content(rows=5) -> bytes:
    """Generate sample CSV content."""
    lines = ["name,age,score"]
    for i in range(rows):
        lines.append(f"patient_{i},{20 + i},{80 + i}")
    return "\n".join(lines).encode("utf-8")


def _make_json_content(rows=5) -> bytes:
    """Generate sample JSON content."""
    data = [{"name": f"patient_{i}", "age": 20 + i, "score": 80 + i} for i in range(rows)]
    return json.dumps(data).encode("utf-8")


class TestUpload:
    """Tests for POST /api/v1/data/upload."""

    @patch("app.services.s3_client.upload_file")
    def test_upload_csv_success(self, mock_upload, client):
        """Test successful CSV file upload."""
        mock_upload.return_value = "data/user/file.csv"
        content = _make_csv_content()

        response = client.post(
            "/api/v1/data/upload",
            files={"file": ("test_data.csv", io.BytesIO(content), "text/csv")},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["message"] == "File 'test_data.csv' uploaded successfully"
        assert data["file"]["original_filename"] == "test_data.csv"
        assert data["file"]["file_format"] == "csv"
        assert data["file"]["file_size"] == len(content)
        assert data["file"]["status"] == "uploaded"
        assert data["file"]["row_count"] == 5
        assert data["file"]["column_count"] == 3
        mock_upload.assert_called_once()

    @patch("app.services.s3_client.upload_file")
    def test_upload_json_success(self, mock_upload, client):
        """Test successful JSON file upload."""
        mock_upload.return_value = "data/user/file.json"
        content = _make_json_content()

        response = client.post(
            "/api/v1/data/upload",
            files={"file": ("data.json", io.BytesIO(content), "application/json")},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["file"]["file_format"] == "json"
        assert data["file"]["row_count"] == 5
        assert data["file"]["column_count"] == 3

    def test_upload_unsupported_format(self, client):
        """Test upload with unsupported file format returns error."""
        content = b"some content"

        response = client.post(
            "/api/v1/data/upload",
            files={"file": ("data.txt", io.BytesIO(content), "text/plain")},
        )

        assert response.status_code == 422
        assert "Unsupported file format" in response.json()["detail"]

    def test_upload_empty_file(self, client):
        """Test upload with empty file returns error."""
        response = client.post(
            "/api/v1/data/upload",
            files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
        )

        assert response.status_code == 422
        assert "empty" in response.json()["detail"].lower()

    @patch("app.services.s3_client.upload_file")
    def test_upload_file_too_large(self, mock_upload, client):
        """Test upload with file exceeding size limit."""
        # Create content just over 100MB
        content = b"x" * (104857600 + 1)

        response = client.post(
            "/api/v1/data/upload",
            files={"file": ("big.csv", io.BytesIO(content), "text/csv")},
        )

        assert response.status_code == 422
        assert "size" in response.json()["detail"].lower()
        mock_upload.assert_not_called()

    @patch("app.services.s3_client.upload_file", side_effect=Exception("S3 error"))
    def test_upload_s3_failure(self, mock_upload, client):
        """Test upload when S3 upload fails."""
        content = _make_csv_content()

        response = client.post(
            "/api/v1/data/upload",
            files={"file": ("test.csv", io.BytesIO(content), "text/csv")},
        )

        assert response.status_code == 500
        assert "storage" in response.json()["detail"].lower()


class TestListFiles:
    """Tests for GET /api/v1/data/files."""

    @patch("app.services.s3_client.upload_file")
    def test_list_files_empty(self, mock_upload, client):
        """Test listing files when user has no files."""
        response = client.get("/api/v1/data/files")

        assert response.status_code == 200
        data = response.json()
        assert data["files"] == []
        assert data["total"] == 0

    @patch("app.services.s3_client.upload_file")
    def test_list_files_after_upload(self, mock_upload, client):
        """Test listing files after uploading."""
        mock_upload.return_value = "key"
        content = _make_csv_content()

        # Upload a file
        client.post(
            "/api/v1/data/upload",
            files={"file": ("test.csv", io.BytesIO(content), "text/csv")},
        )

        response = client.get("/api/v1/data/files")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["files"][0]["original_filename"] == "test.csv"

    @patch("app.services.s3_client.upload_file")
    def test_list_files_user_isolation(self, mock_upload, client, db_session, test_user, other_user):
        """Test that users can only see their own files."""
        mock_upload.return_value = "key"
        content = _make_csv_content()

        # Upload as first user
        client.post(
            "/api/v1/data/upload",
            files={"file": ("user1.csv", io.BytesIO(content), "text/csv")},
        )

        # Switch to other user and list - should see nothing
        other_client = _make_client_for_user(db_session, other_user)
        response = other_client.get("/api/v1/data/files")
        assert response.status_code == 200
        assert response.json()["total"] == 0
        app.dependency_overrides.clear()


class TestPreview:
    """Tests for GET /api/v1/data/files/{file_id}/preview."""

    @patch("app.services.s3_client.get_file_content")
    @patch("app.services.s3_client.upload_file")
    def test_preview_csv(self, mock_upload, mock_get, client):
        """Test preview returns first 10 rows of CSV."""
        content = _make_csv_content(rows=15)
        mock_upload.return_value = "key"
        mock_get.return_value = content

        # Upload
        upload_resp = client.post(
            "/api/v1/data/upload",
            files={"file": ("test.csv", io.BytesIO(content), "text/csv")},
        )
        file_id = upload_resp.json()["file"]["id"]

        # Preview
        response = client.get(f"/api/v1/data/files/{file_id}/preview")

        assert response.status_code == 200
        data = response.json()
        assert data["total_rows"] == 15
        assert data["total_columns"] == 3
        assert len(data["rows"]) == 10  # Only first 10 rows
        assert data["columns"] == ["name", "age", "score"]

    def test_preview_nonexistent_file(self, client):
        """Test preview for non-existent file returns 404."""
        fake_id = uuid.uuid4()
        response = client.get(f"/api/v1/data/files/{fake_id}/preview")
        assert response.status_code == 404

    @patch("app.services.s3_client.get_file_content")
    @patch("app.services.s3_client.upload_file")
    def test_preview_user_isolation(self, mock_upload, mock_get, client, db_session, test_user, other_user):
        """Test that users cannot preview other users' files."""
        content = _make_csv_content()
        mock_upload.return_value = "key"
        mock_get.return_value = content

        # Upload as first user
        upload_resp = client.post(
            "/api/v1/data/upload",
            files={"file": ("test.csv", io.BytesIO(content), "text/csv")},
        )
        file_id = upload_resp.json()["file"]["id"]

        # Try to preview as other user
        other_client = _make_client_for_user(db_session, other_user)
        response = other_client.get(f"/api/v1/data/files/{file_id}/preview")
        assert response.status_code == 404
        app.dependency_overrides.clear()


class TestQuality:
    """Tests for GET /api/v1/data/files/{file_id}/quality."""

    @patch("app.services.s3_client.get_file_content")
    @patch("app.services.s3_client.upload_file")
    def test_quality_report(self, mock_upload, mock_get, client):
        """Test quality report returns correct metrics."""
        # CSV with some missing values
        csv_content = "name,age,score\nAlice,30,90\nBob,,85\nCharlie,25,\n".encode("utf-8")
        mock_upload.return_value = "key"
        mock_get.return_value = csv_content

        # Upload
        upload_resp = client.post(
            "/api/v1/data/upload",
            files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")},
        )
        file_id = upload_resp.json()["file"]["id"]

        # Quality
        response = client.get(f"/api/v1/data/files/{file_id}/quality")

        assert response.status_code == 200
        data = response.json()
        assert data["total_rows"] == 3
        assert data["total_columns"] == 3
        assert data["missing_value_percentage"] > 0
        assert len(data["columns"]) == 3

        # Check column types are detected
        col_names = [c["name"] for c in data["columns"]]
        assert "name" in col_names
        assert "age" in col_names
        assert "score" in col_names

    def test_quality_nonexistent_file(self, client):
        """Test quality for non-existent file returns 404."""
        fake_id = uuid.uuid4()
        response = client.get(f"/api/v1/data/files/{fake_id}/quality")
        assert response.status_code == 404


class TestDelete:
    """Tests for DELETE /api/v1/data/files/{file_id}."""

    @patch("app.services.s3_client.delete_file")
    @patch("app.services.s3_client.upload_file")
    def test_delete_file(self, mock_upload, mock_delete, client):
        """Test successful file deletion."""
        mock_upload.return_value = "key"
        content = _make_csv_content()

        # Upload
        upload_resp = client.post(
            "/api/v1/data/upload",
            files={"file": ("test.csv", io.BytesIO(content), "text/csv")},
        )
        file_id = upload_resp.json()["file"]["id"]

        # Delete
        response = client.delete(f"/api/v1/data/files/{file_id}")
        assert response.status_code == 204

        # Verify it's gone
        list_resp = client.get("/api/v1/data/files")
        assert list_resp.json()["total"] == 0
        mock_delete.assert_called_once()

    def test_delete_nonexistent_file(self, client):
        """Test deleting non-existent file returns 404."""
        fake_id = uuid.uuid4()
        response = client.delete(f"/api/v1/data/files/{fake_id}")
        assert response.status_code == 404

    @patch("app.services.s3_client.delete_file")
    @patch("app.services.s3_client.upload_file")
    def test_delete_user_isolation(self, mock_upload, mock_delete, client, db_session, test_user, other_user):
        """Test that users cannot delete other users' files."""
        mock_upload.return_value = "key"
        content = _make_csv_content()

        # Upload as first user
        upload_resp = client.post(
            "/api/v1/data/upload",
            files={"file": ("test.csv", io.BytesIO(content), "text/csv")},
        )
        file_id = upload_resp.json()["file"]["id"]

        # Try to delete as other user
        other_client = _make_client_for_user(db_session, other_user)
        response = other_client.delete(f"/api/v1/data/files/{file_id}")
        assert response.status_code == 404
        mock_delete.assert_not_called()
        app.dependency_overrides.clear()
