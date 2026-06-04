"""Tests for the Agent-driven report generation and download API.

Covers: generating a report (persists structured content + exported S3 keys,
returns it with download-availability flags), auth and cross-user isolation,
nonexistent analysis; and downloading a report (presigned URL per format,
missing/unsupported format, cross-user isolation, auth).

The AgentCore client is injected via ``get_agentcore_client`` and overridden
with a fake returning canned ``AgentResponse`` objects, so no real AWS/Bedrock
calls are made. S3 presigned-URL generation is monkeypatched so no real S3
calls are made.

Requirements: 5.1-5.7
"""

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
from app.models.analysis import AnalysisSession
from app.models.base import Base
from app.models.data import DataFile
from app.models.report import Report
from app.models.user import User
from app.services import s3_client
from app.services.agentcore_client import AgentResponse

# --- Canned Agent report payload ------------------------------------------

REPORT_CONTENT = {
    "title": "医学数据分析报告",
    "analysis_id": "",  # filled per-test where relevant
    "metadata": {
        "file_name": "data.csv",
        "upload_time": "2024-01-01T00:00:00Z",
        "row_count": 100,
        "column_count": 3,
    },
    "sections": [
        {"key": "data_summary", "title": "数据摘要", "body": "共 100 行，3 列。", "charts": []},
        {"key": "key_findings", "title": "关键发现", "body": "年龄分布近似正态。", "charts": []},
        {"key": "statistical_results", "title": "统计分析结果", "body": "均值 42.5。", "charts": []},
        {"key": "visualizations", "title": "可视化图表", "body": "", "charts": []},
        {"key": "recommendations", "title": "建议", "body": "建议进一步随访。", "charts": []},
    ],
    # Exported file S3 keys returned by the report-generation MCP export tool.
    "s3_key_pdf": "reports/report-abc.pdf",
    "s3_key_docx": "reports/report-abc.docx",
}


def _report_response(**overrides) -> AgentResponse:
    """Build a canned AgentResponse whose report payload can be overridden."""
    report = dict(REPORT_CONTENT)
    report.update(overrides)
    return AgentResponse(
        response="报告已生成。",
        charts=[],
        analysis_results=[],
        report=report,
        session_id="session-fake",
    )


class FakeAgentCoreClient:
    """Fake AgentCore client returning canned responses and recording calls."""

    def __init__(self, response: AgentResponse | None = None):
        self._response = response or _report_response()
        self.calls: list[dict] = []

    async def invoke_agent(self, payload: dict, session_id: str = "") -> AgentResponse:
        self.calls.append({"payload": payload, "session_id": session_id})
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


def _make_data_file(db_session, user, name="data.csv") -> DataFile:
    """Create a DataFile owned by user."""
    data_file = DataFile(
        user_id=user.id,
        filename=f"{uuid.uuid4()}_{name}",
        original_filename=name,
        file_size=1024,
        file_format="csv",
        s3_key=f"data/{user.id}/{name}",
        row_count=100,
        column_count=3,
        status="uploaded",
    )
    db_session.add(data_file)
    db_session.commit()
    db_session.refresh(data_file)
    return data_file


def _make_analysis(db_session, user) -> AnalysisSession:
    """Create a completed AnalysisSession owned by user."""
    data_file = _make_data_file(db_session, user)
    session = AnalysisSession(
        user_id=user.id,
        file_id=data_file.id,
        status="completed",
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


def _make_report(db_session, user, *, s3_key_pdf=None, s3_key_docx=None) -> Report:
    """Create a Report owned by user with the given exported S3 keys."""
    session = _make_analysis(db_session, user)
    report = Report(
        session_id=session.id,
        user_id=user.id,
        title="医学数据分析报告",
        content={"title": "医学数据分析报告", "sections": []},
        s3_key_pdf=s3_key_pdf,
        s3_key_docx=s3_key_docx,
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)
    return report


@pytest.fixture
def fake_client():
    """Shared fake AgentCore client."""
    return FakeAgentCoreClient()


@pytest.fixture
def stub_presigned_url(monkeypatch):
    """Monkeypatch s3_client.get_presigned_url to avoid real S3 calls."""
    calls: list[tuple] = []

    def fake_get_presigned_url(s3_key, expires_in=3600):
        calls.append((s3_key, expires_in))
        return f"https://s3.test/{s3_key}?signed=1"

    monkeypatch.setattr(s3_client, "get_presigned_url", fake_get_presigned_url)
    return calls


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


# --- POST /generate --------------------------------------------------------


class TestGenerateReport:
    def test_generate_persists_content_and_returns_it(self, client, db_session, test_user):
        analysis = _make_analysis(db_session, test_user)

        resp = client.post(
            "/api/v1/reports/generate", json={"analysis_id": str(analysis.id)}
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()

        # Returned report mirrors the structured content + download flags.
        assert data["session_id"] == str(analysis.id)
        assert data["title"] == "医学数据分析报告"
        section_keys = [s["key"] for s in data["content"]["sections"]]
        assert section_keys == [
            "data_summary",
            "key_findings",
            "statistical_results",
            "visualizations",
            "recommendations",
        ]
        assert data["content"]["metadata"]["file_name"] == "data.csv"
        assert data["has_pdf"] is True
        assert data["has_docx"] is True

        # Persisted in DB with the exported S3 keys captured.
        reports = db_session.execute(
            select(Report).where(Report.session_id == analysis.id)
        ).scalars().all()
        assert len(reports) == 1
        assert reports[0].s3_key_pdf == "reports/report-abc.pdf"
        assert reports[0].s3_key_docx == "reports/report-abc.docx"
        assert reports[0].content["title"] == "医学数据分析报告"

    def test_generate_invokes_agent_with_analysis_id(self, client, db_session, test_user, fake_client):
        analysis = _make_analysis(db_session, test_user)
        client.post("/api/v1/reports/generate", json={"analysis_id": str(analysis.id)})
        assert len(fake_client.calls) == 1
        assert str(analysis.id) in fake_client.calls[0]["payload"]["prompt"]
        assert fake_client.calls[0]["payload"]["analysis_context"]["analysis_id"] == str(analysis.id)

    def test_generate_without_exported_keys_sets_flags_false(self, db_session, test_user):
        analysis = _make_analysis(db_session, test_user)
        # Agent returns content without any S3 export keys.
        report_payload = {
            "title": "无导出报告",
            "sections": [{"key": "data_summary", "title": "数据摘要", "body": "x", "charts": []}],
        }
        fake = FakeAgentCoreClient(
            AgentResponse(response="ok", report=report_payload, session_id="s")
        )
        _apply_overrides(db_session, test_user, fake)
        with TestClient(app) as c:
            resp = c.post("/api/v1/reports/generate", json={"analysis_id": str(analysis.id)})
        app.dependency_overrides.clear()

        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "无导出报告"
        assert data["has_pdf"] is False
        assert data["has_docx"] is False

    def test_generate_with_exports_list_shape(self, db_session, test_user):
        analysis = _make_analysis(db_session, test_user)
        report_payload = {
            "title": "列表导出报告",
            "sections": [],
            "exports": [
                {"format": "pdf", "s3_key": "reports/x.pdf"},
                {"format": "docx", "s3_key": "reports/x.docx"},
            ],
        }
        fake = FakeAgentCoreClient(
            AgentResponse(response="ok", report=report_payload, session_id="s")
        )
        _apply_overrides(db_session, test_user, fake)
        with TestClient(app) as c:
            resp = c.post("/api/v1/reports/generate", json={"analysis_id": str(analysis.id)})
        app.dependency_overrides.clear()

        assert resp.status_code == 201
        data = resp.json()
        assert data["has_pdf"] is True
        assert data["has_docx"] is True
        report_id = uuid.UUID(data["id"])
        report = db_session.get(Report, report_id)
        assert report.s3_key_pdf == "reports/x.pdf"
        assert report.s3_key_docx == "reports/x.docx"

    def test_generate_nonexistent_analysis(self, client):
        resp = client.post(
            "/api/v1/reports/generate", json={"analysis_id": str(uuid.uuid4())}
        )
        assert resp.status_code == 404

    def test_generate_cross_user_analysis_denied(self, client, db_session, other_user):
        analysis = _make_analysis(db_session, other_user)
        resp = client.post(
            "/api/v1/reports/generate", json={"analysis_id": str(analysis.id)}
        )
        assert resp.status_code == 403

    def test_generate_requires_auth(self, db_session, test_user):
        analysis = _make_analysis(db_session, test_user)
        unauth = _unauthenticated_client(db_session)
        resp = unauth.post(
            "/api/v1/reports/generate", json={"analysis_id": str(analysis.id)}
        )
        assert resp.status_code == 401
        app.dependency_overrides.clear()


# --- GET /{report_id}/download ---------------------------------------------


class TestDownloadReport:
    def test_download_pdf_returns_presigned_url(self, client, db_session, test_user, stub_presigned_url):
        report = _make_report(db_session, test_user, s3_key_pdf="reports/r.pdf")

        resp = client.get(f"/api/v1/reports/{report.id}/download?format=pdf")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["format"] == "pdf"
        assert data["download_url"] == "https://s3.test/reports/r.pdf?signed=1"
        assert stub_presigned_url == [("reports/r.pdf", 3600)]

    def test_download_defaults_to_pdf(self, client, db_session, test_user, stub_presigned_url):
        report = _make_report(db_session, test_user, s3_key_pdf="reports/r.pdf")
        resp = client.get(f"/api/v1/reports/{report.id}/download")
        assert resp.status_code == 200
        assert resp.json()["format"] == "pdf"

    def test_download_docx_returns_presigned_url(self, client, db_session, test_user, stub_presigned_url):
        report = _make_report(db_session, test_user, s3_key_docx="reports/r.docx")

        resp = client.get(f"/api/v1/reports/{report.id}/download?format=docx")
        assert resp.status_code == 200
        data = resp.json()
        assert data["format"] == "docx"
        assert data["download_url"] == "https://s3.test/reports/r.docx?signed=1"

    def test_download_missing_format_returns_404(self, client, db_session, test_user, stub_presigned_url):
        # Report has a PDF but no Word export; requesting docx => 404.
        report = _make_report(db_session, test_user, s3_key_pdf="reports/r.pdf")
        resp = client.get(f"/api/v1/reports/{report.id}/download?format=docx")
        assert resp.status_code == 404

    def test_download_unsupported_format_returns_400(self, client, db_session, test_user, stub_presigned_url):
        report = _make_report(db_session, test_user, s3_key_pdf="reports/r.pdf")
        resp = client.get(f"/api/v1/reports/{report.id}/download?format=txt")
        assert resp.status_code == 400

    def test_download_nonexistent_report(self, client, stub_presigned_url):
        resp = client.get(f"/api/v1/reports/{uuid.uuid4()}/download?format=pdf")
        assert resp.status_code == 404

    def test_download_cross_user_denied(self, client, db_session, test_user, other_user, fake_client, stub_presigned_url):
        report = _make_report(db_session, other_user, s3_key_pdf="reports/r.pdf")
        resp = client.get(f"/api/v1/reports/{report.id}/download?format=pdf")
        assert resp.status_code == 403

    def test_download_requires_auth(self, db_session, test_user):
        report = _make_report(db_session, test_user, s3_key_pdf="reports/r.pdf")
        unauth = _unauthenticated_client(db_session)
        resp = unauth.get(f"/api/v1/reports/{report.id}/download?format=pdf")
        assert resp.status_code == 401
        app.dependency_overrides.clear()
