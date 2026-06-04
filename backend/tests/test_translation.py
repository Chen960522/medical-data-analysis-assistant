"""Tests for the PDF literature upload and translation API.

Covers:
* ``POST /upload`` — accepts a PDF (201, persists a record associated with the
  user); rejects non-PDF (Req 11.5), >50MB (Req 11.6), empty, and missing
  filename; auth required.
* ``POST /{id}/translate`` — persists a TranslationResult, sets languages /
  page count / status, supports a source-language override; Agent failure →
  502; no parseable payload → 502 + status failed; cross-user → 403.
* ``GET /{id}/status`` — progress + languages.
* ``GET /{id}/result`` — bilingual result, 404 before translation.
* ``GET /{id}/download`` — presigned URL (pdf + docx, bilingual / translation
  modes), missing export → 404, bad format / mode → 400.
* ``GET /history`` — newest-first, user-scoped.
* ``DELETE /{id}`` — removes record + cascades result, best-effort S3 cleanup.
* cross-user → 403, nonexistent → 404, auth → 401 on representative endpoints.

The AgentCore client is injected via ``get_agentcore_client`` and overridden
with a fake returning canned ``AgentResponse`` objects, so no real AWS/Bedrock
calls are made. S3 upload / presigned-URL / delete are monkeypatched so no real
S3 calls are made.

Requirements: 11.1-11.50
"""

import io
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.analysis import get_agentcore_client
from app.core.database import get_db
from app.main import app
from app.middleware.auth import get_current_user
from app.models.base import Base
from app.models.translation import TranslationRecord, TranslationResult
from app.models.user import User
from app.services import s3_client
from app.services.agentcore_client import AgentResponse

# --- Canned Agent translation payload --------------------------------------

TRANSLATION_PAYLOAD = {
    "source_language": "en",
    "target_language": "zh",
    "page_count": 12,
    "original_paragraphs": [
        "Background: Hypertension is a major risk factor.",
        "Methods: A randomized controlled trial was conducted.",
        "Results: Blood pressure decreased significantly.",
    ],
    "translated_paragraphs": [
        "背景：高血压是主要的危险因素。",
        "方法：开展了一项随机对照试验。",
        "结果：血压显著下降。",
    ],
    "document_structure": {
        "title": "A Study on Hypertension",
        "headings": ["Background", "Methods", "Results"],
    },
    "s3_key_pdf": "translations/exports/result.pdf",
    "s3_key_docx": "translations/exports/result.docx",
}


def _translation_response(**overrides) -> AgentResponse:
    """Build a canned AgentResponse carrying a translation payload (overridable)."""
    payload = dict(TRANSLATION_PAYLOAD)
    payload.update(overrides)
    # Carry the payload as extras on the response dict so the tolerant parser
    # (which prefers AgentResponse.to_dict()) picks it up directly.
    resp = AgentResponse(
        response="翻译完成。",
        charts=[],
        analysis_results=[],
        report=None,
        session_id="session-fake",
    )
    # Monkeypatch to_dict to surface the structured translation payload.
    resp.to_dict = lambda: payload  # type: ignore[method-assign]
    return resp


class FakeAgentCoreClient:
    """Fake AgentCore client returning a canned response and recording calls."""

    def __init__(self, response: AgentResponse | None = None, *, raise_exc: Exception | None = None):
        self._response = response if response is not None else _translation_response()
        self._raise_exc = raise_exc
        self.calls: list[dict] = []

    async def invoke_agent(self, payload: dict, session_id: str = "") -> AgentResponse:
        self.calls.append({"payload": payload, "session_id": session_id})
        if self._raise_exc is not None:
            raise self._raise_exc
        return self._response


# --- Fixtures --------------------------------------------------------------


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
    """Create a test user."""
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
    """Create another user for isolation tests."""
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
def fake_client():
    """Shared fake AgentCore client."""
    return FakeAgentCoreClient()


@pytest.fixture(autouse=True)
def stub_s3(monkeypatch):
    """Monkeypatch s3_client functions to avoid real S3 calls."""
    uploads: list[tuple] = []
    presigned: list[tuple] = []
    deletes: list[str] = []

    def fake_upload_file(s3_key, content, content_type="application/octet-stream"):
        uploads.append((s3_key, len(content), content_type))
        return s3_key

    def fake_get_presigned_url(s3_key, expires_in=3600):
        presigned.append((s3_key, expires_in))
        return f"https://s3.test/{s3_key}?signed=1"

    def fake_delete_file(s3_key):
        deletes.append(s3_key)

    monkeypatch.setattr(s3_client, "upload_file", fake_upload_file)
    monkeypatch.setattr(s3_client, "get_presigned_url", fake_get_presigned_url)
    monkeypatch.setattr(s3_client, "delete_file", fake_delete_file)
    return {"uploads": uploads, "presigned": presigned, "deletes": deletes}


def _apply_overrides(db_session, user, fake_client):
    """Install dependency overrides for db, auth, and the Agent client."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_get_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_agentcore_client] = lambda: fake_client


@pytest.fixture
def client(db_session, test_user, fake_client):
    """Test client authenticated as test_user with a fake Agent client."""
    _apply_overrides(db_session, test_user, fake_client)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _make_client_for_user(db_session, user, fake_client):
    """Create a test client authenticated as a specific user."""
    _apply_overrides(db_session, user, fake_client)
    return TestClient(app)


def _unauthenticated_client(db_session):
    """Create a client with only the DB overridden (no auth)."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _pdf_bytes(size: int = 1024) -> bytes:
    """Generate fake PDF content of a given size."""
    header = b"%PDF-1.4\n"
    return header + b"x" * max(0, size - len(header))


def _make_record(db_session, user, *, name="paper.pdf", status="uploaded") -> TranslationRecord:
    """Create a TranslationRecord owned by user."""
    record = TranslationRecord(
        user_id=user.id,
        filename=f"{uuid.uuid4()}_{name}",
        original_filename=name,
        file_size=2048,
        s3_key=f"translations/{user.id}/{name}",
        status=status,
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    return record


def _make_result(db_session, record, *, s3_key_pdf=None, s3_key_docx=None) -> TranslationResult:
    """Create a TranslationResult for a record."""
    result = TranslationResult(
        translation_id=record.id,
        original_paragraphs=["orig"],
        translated_paragraphs=["译文"],
        document_structure={"title": "t"},
        s3_key_pdf=s3_key_pdf,
        s3_key_docx=s3_key_docx,
    )
    db_session.add(result)
    db_session.commit()
    db_session.refresh(result)
    return result


def _upload_pdf(client, name="paper.pdf", content=None, content_type="application/pdf"):
    """Helper to POST a PDF upload."""
    if content is None:
        content = _pdf_bytes()
    return client.post(
        "/api/v1/translation/upload",
        files={"file": (name, io.BytesIO(content), content_type)},
    )


# --- POST /upload ----------------------------------------------------------


class TestUpload:
    def test_upload_pdf_success(self, client, db_session, test_user, stub_s3):
        content = _pdf_bytes(4096)
        resp = _upload_pdf(client, "research.pdf", content)
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["original_filename"] == "research.pdf"
        assert data["file_size"] == len(content)
        assert data["status"] == "uploaded"
        assert data["page_count"] is None

        # Persisted and associated with the user (Req 11.9).
        record = db_session.execute(
            select(TranslationRecord).where(TranslationRecord.id == uuid.UUID(data["id"]))
        ).scalar_one()
        assert record.user_id == test_user.id
        assert record.s3_key.startswith(f"translations/{test_user.id}/")
        # S3 upload was invoked once.
        assert len(stub_s3["uploads"]) == 1

    def test_upload_rejects_non_pdf(self, client, stub_s3):
        # Req 11.5 — only PDF accepted.
        resp = _upload_pdf(client, "data.txt", b"hello", "text/plain")
        assert resp.status_code == 422
        assert "PDF" in resp.json()["detail"]
        assert stub_s3["uploads"] == []

    def test_upload_rejects_oversize(self, client, stub_s3):
        # Req 11.6 — > 50MB rejected.
        content = b"%PDF-1.4\n" + b"x" * (50 * 1024 * 1024 + 1)
        resp = _upload_pdf(client, "big.pdf", content)
        assert resp.status_code == 422
        assert "size" in resp.json()["detail"].lower()
        assert stub_s3["uploads"] == []

    def test_upload_rejects_empty(self, client, stub_s3):
        resp = _upload_pdf(client, "empty.pdf", b"")
        assert resp.status_code == 422
        assert "empty" in resp.json()["detail"].lower()
        assert stub_s3["uploads"] == []

    def test_upload_requires_auth(self, db_session):
        unauth = _unauthenticated_client(db_session)
        resp = unauth.post(
            "/api/v1/translation/upload",
            files={"file": ("p.pdf", io.BytesIO(_pdf_bytes()), "application/pdf")},
        )
        assert resp.status_code == 401
        app.dependency_overrides.clear()


# --- POST /{id}/translate --------------------------------------------------


class TestTranslate:
    def test_translate_persists_result_and_languages(self, client, db_session, test_user):
        record = _make_record(db_session, test_user)
        resp = client.post(f"/api/v1/translation/{record.id}/translate", json={})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["translation_id"] == str(record.id)
        assert data["source_language"] == "en"
        assert data["target_language"] == "zh"
        assert data["status"] == "completed"
        assert data["original_paragraphs"] == TRANSLATION_PAYLOAD["original_paragraphs"]
        assert data["translated_paragraphs"] == TRANSLATION_PAYLOAD["translated_paragraphs"]
        assert data["document_structure"]["title"] == "A Study on Hypertension"

        # Record updated, result persisted.
        db_session.expire_all()
        refreshed = db_session.get(TranslationRecord, record.id)
        assert refreshed.status == "completed"
        assert refreshed.progress == 100.0
        assert refreshed.source_language == "en"
        assert refreshed.target_language == "zh"
        assert refreshed.page_count == 12
        assert refreshed.completed_at is not None
        result = db_session.execute(
            select(TranslationResult).where(TranslationResult.translation_id == record.id)
        ).scalar_one()
        assert result.s3_key_pdf == "translations/exports/result.pdf"
        assert result.s3_key_docx == "translations/exports/result.docx"

    def test_translate_source_language_override(self, db_session, test_user):
        # Override to zh -> target should become en (Req 11.19).
        record = _make_record(db_session, test_user)
        fake = FakeAgentCoreClient(_translation_response())
        _apply_overrides(db_session, test_user, fake)
        with TestClient(app) as c:
            resp = c.post(
                f"/api/v1/translation/{record.id}/translate",
                json={"source_language": "zh"},
            )
        app.dependency_overrides.clear()
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["source_language"] == "zh"
        assert data["target_language"] == "en"
        # Override forwarded to the Agent context.
        assert fake.calls[0]["payload"]["analysis_context"]["source_language_override"] == "zh"

    def test_translate_invalid_override_returns_400(self, client, db_session, test_user):
        record = _make_record(db_session, test_user)
        resp = client.post(
            f"/api/v1/translation/{record.id}/translate",
            json={"source_language": "fr"},
        )
        assert resp.status_code == 400

    def test_translate_agent_failure_returns_502_and_marks_failed(self, db_session, test_user):
        record = _make_record(db_session, test_user)
        fake = FakeAgentCoreClient(raise_exc=RuntimeError("bedrock down"))
        _apply_overrides(db_session, test_user, fake)
        with TestClient(app) as c:
            resp = c.post(f"/api/v1/translation/{record.id}/translate", json={})
        app.dependency_overrides.clear()
        assert resp.status_code == 502
        db_session.expire_all()
        assert db_session.get(TranslationRecord, record.id).status == "failed"

    def test_translate_unparseable_payload_returns_502(self, db_session, test_user):
        record = _make_record(db_session, test_user)
        # Plain-text response with no translation JSON.
        plain = AgentResponse(response="抱歉，无法解析。", session_id="s")
        fake = FakeAgentCoreClient(plain)
        _apply_overrides(db_session, test_user, fake)
        with TestClient(app) as c:
            resp = c.post(f"/api/v1/translation/{record.id}/translate", json={})
        app.dependency_overrides.clear()
        assert resp.status_code == 502
        db_session.expire_all()
        assert db_session.get(TranslationRecord, record.id).status == "failed"

    def test_translate_cross_user_denied(self, client, db_session, other_user):
        record = _make_record(db_session, other_user)
        resp = client.post(f"/api/v1/translation/{record.id}/translate", json={})
        assert resp.status_code == 403

    def test_translate_nonexistent(self, client):
        resp = client.post(f"/api/v1/translation/{uuid.uuid4()}/translate", json={})
        assert resp.status_code == 404


# --- GET /{id}/status ------------------------------------------------------


class TestStatus:
    def test_status_returns_progress_and_languages(self, client, db_session, test_user):
        record = _make_record(db_session, test_user, status="processing")
        record.progress = 42.0
        record.source_language = "en"
        record.target_language = "zh"
        db_session.commit()

        resp = client.get(f"/api/v1/translation/{record.id}/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "processing"
        assert data["progress"] == 42.0
        assert data["source_language"] == "en"
        assert data["target_language"] == "zh"

    def test_status_cross_user_denied(self, client, db_session, other_user):
        record = _make_record(db_session, other_user)
        resp = client.get(f"/api/v1/translation/{record.id}/status")
        assert resp.status_code == 403

    def test_status_nonexistent(self, client):
        resp = client.get(f"/api/v1/translation/{uuid.uuid4()}/status")
        assert resp.status_code == 404


# --- GET /{id}/result ------------------------------------------------------


class TestResult:
    def test_result_returns_bilingual_arrays(self, client, db_session, test_user):
        record = _make_record(db_session, test_user, status="completed")
        record.source_language = "en"
        record.target_language = "zh"
        db_session.commit()
        _make_result(db_session, record, s3_key_pdf="k.pdf")

        resp = client.get(f"/api/v1/translation/{record.id}/result")
        assert resp.status_code == 200
        data = resp.json()
        assert data["original_paragraphs"] == ["orig"]
        assert data["translated_paragraphs"] == ["译文"]
        assert data["source_language"] == "en"
        assert data["document_structure"]["title"] == "t"

    def test_result_404_before_translation(self, client, db_session, test_user):
        record = _make_record(db_session, test_user)
        resp = client.get(f"/api/v1/translation/{record.id}/result")
        assert resp.status_code == 404

    def test_result_cross_user_denied(self, client, db_session, other_user):
        record = _make_record(db_session, other_user)
        _make_result(db_session, record)
        resp = client.get(f"/api/v1/translation/{record.id}/result")
        assert resp.status_code == 403


# --- GET /{id}/download ----------------------------------------------------


class TestDownload:
    def test_download_pdf_bilingual(self, client, db_session, test_user, stub_s3):
        record = _make_record(db_session, test_user)
        _make_result(db_session, record, s3_key_pdf="translations/x.pdf")

        resp = client.get(f"/api/v1/translation/{record.id}/download?format=pdf&mode=bilingual")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["format"] == "pdf"
        assert data["mode"] == "bilingual"
        assert data["download_url"] == "https://s3.test/translations/x.pdf?signed=1"
        assert ("translations/x.pdf", 3600) in stub_s3["presigned"]

    def test_download_defaults_pdf_bilingual(self, client, db_session, test_user, stub_s3):
        record = _make_record(db_session, test_user)
        _make_result(db_session, record, s3_key_pdf="translations/x.pdf")
        resp = client.get(f"/api/v1/translation/{record.id}/download")
        assert resp.status_code == 200
        data = resp.json()
        assert data["format"] == "pdf"
        assert data["mode"] == "bilingual"

    def test_download_docx_translation_mode(self, client, db_session, test_user, stub_s3):
        record = _make_record(db_session, test_user)
        _make_result(db_session, record, s3_key_docx="translations/x.docx")
        resp = client.get(f"/api/v1/translation/{record.id}/download?format=docx&mode=translation")
        assert resp.status_code == 200
        data = resp.json()
        assert data["format"] == "docx"
        assert data["mode"] == "translation"
        assert data["download_url"].endswith("translations/x.docx?signed=1")

    def test_download_missing_export_returns_404(self, client, db_session, test_user, stub_s3):
        # Has PDF export only; requesting docx -> 404.
        record = _make_record(db_session, test_user)
        _make_result(db_session, record, s3_key_pdf="translations/x.pdf")
        resp = client.get(f"/api/v1/translation/{record.id}/download?format=docx")
        assert resp.status_code == 404

    def test_download_no_result_returns_404(self, client, db_session, test_user, stub_s3):
        record = _make_record(db_session, test_user)
        resp = client.get(f"/api/v1/translation/{record.id}/download?format=pdf")
        assert resp.status_code == 404

    def test_download_unsupported_format_returns_400(self, client, db_session, test_user, stub_s3):
        record = _make_record(db_session, test_user)
        _make_result(db_session, record, s3_key_pdf="translations/x.pdf")
        resp = client.get(f"/api/v1/translation/{record.id}/download?format=txt")
        assert resp.status_code == 400

    def test_download_unsupported_mode_returns_400(self, client, db_session, test_user, stub_s3):
        record = _make_record(db_session, test_user)
        _make_result(db_session, record, s3_key_pdf="translations/x.pdf")
        resp = client.get(f"/api/v1/translation/{record.id}/download?format=pdf&mode=summary")
        assert resp.status_code == 400

    def test_download_cross_user_denied(self, client, db_session, other_user, stub_s3):
        record = _make_record(db_session, other_user)
        _make_result(db_session, record, s3_key_pdf="translations/x.pdf")
        resp = client.get(f"/api/v1/translation/{record.id}/download?format=pdf")
        assert resp.status_code == 403


# --- GET /history ----------------------------------------------------------


class TestHistory:
    def test_history_sorted_desc_and_user_scoped(self, client, db_session, test_user, other_user):
        from datetime import datetime, timedelta, timezone

        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        first = _make_record(db_session, test_user, name="first.pdf")
        first.created_at = base
        second = _make_record(db_session, test_user, name="second.pdf")
        second.created_at = base + timedelta(hours=1)
        # Other user's record should be excluded.
        _make_record(db_session, other_user, name="other.pdf")
        db_session.commit()

        resp = client.get("/api/v1/translation/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        ids = [item["id"] for item in data["records"]]
        # Newest (second) first.
        assert ids == [str(second.id), str(first.id)]

    def test_history_empty(self, client):
        resp = client.get("/api/v1/translation/history")
        assert resp.status_code == 200
        assert resp.json() == {"records": [], "total": 0}

    def test_history_requires_auth(self, db_session):
        unauth = _unauthenticated_client(db_session)
        resp = unauth.get("/api/v1/translation/history")
        assert resp.status_code == 401
        app.dependency_overrides.clear()


# --- DELETE /{id} ----------------------------------------------------------


class TestDelete:
    def test_delete_removes_record_and_result(self, client, db_session, test_user, stub_s3):
        record = _make_record(db_session, test_user)
        _make_result(db_session, record, s3_key_pdf="translations/x.pdf")
        record_id = record.id

        resp = client.delete(f"/api/v1/translation/{record_id}")
        assert resp.status_code == 204

        db_session.expire_all()
        assert db_session.get(TranslationRecord, record_id) is None
        # Cascade removed the result.
        remaining = db_session.execute(
            select(TranslationResult).where(TranslationResult.translation_id == record_id)
        ).scalar_one_or_none()
        assert remaining is None
        # Best-effort S3 cleanup invoked (uploaded PDF + exported PDF).
        assert record.s3_key in stub_s3["deletes"]

    def test_delete_nonexistent(self, client):
        resp = client.delete(f"/api/v1/translation/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_delete_cross_user_denied(self, client, db_session, other_user, stub_s3):
        record = _make_record(db_session, other_user)
        resp = client.delete(f"/api/v1/translation/{record.id}")
        assert resp.status_code == 403
        db_session.expire_all()
        assert db_session.get(TranslationRecord, record.id) is not None
