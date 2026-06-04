"""Tests for the Agent-driven analysis API.

Covers: starting an analysis (persists results/charts/report), auth and
cross-user isolation, status/results/charts retrieval, adding/removing
dimensions, history ordering, and deletion with cascade.

The AgentCore client is injected via ``get_agentcore_client`` and overridden
with a fake returning canned ``AgentResponse`` objects, so no real AWS/Bedrock
calls are made.

Requirements: 3.1-3.8, 6.1-6.5
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
from app.models.analysis import AnalysisDimension, AnalysisResult, AnalysisSession, Chart
from app.models.base import Base
from app.models.data import DataFile
from app.models.report import Report
from app.models.user import User
from app.services.agentcore_client import AgentResponse

# --- Canned Agent artifacts ----------------------------------------------

ECHARTS_OPTION = {
    "title": {"text": "年龄分布"},
    "xAxis": {"type": "category", "data": ["20-30", "30-40", "40-50"]},
    "yAxis": {"type": "value"},
    "series": [{"type": "bar", "data": [12, 24, 18]}],
}

ANALYSIS_RESULT = {
    "result_type": "descriptive_statistics",
    "result_data": {"mean": 42.5, "median": 41.0, "std": 8.3},
}

REPORT_CONTENT = {
    "title": "医学数据分析报告",
    "sections": [
        {"name": "data_summary", "content": "共 100 行，3 列。"},
        {"name": "key_findings", "content": "年龄分布近似正态。"},
    ],
}


class FakeAgentCoreClient:
    """Fake AgentCore client returning canned responses and recording calls."""

    def __init__(self, response: AgentResponse | None = None):
        self._response = response or AgentResponse(
            response="分析完成",
            charts=[ECHARTS_OPTION],
            analysis_results=[ANALYSIS_RESULT],
            report=REPORT_CONTENT,
            session_id="session-fake",
        )
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


@pytest.fixture
def fake_client():
    """Shared fake AgentCore client."""
    return FakeAgentCoreClient()


@pytest.fixture
def client(db_session, test_user, fake_client):
    """Test client authenticated as test_user with a fake Agent client."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_get_current_user():
        return test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_agentcore_client] = lambda: fake_client
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _make_client_for_user(db_session, user, fake_client):
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
    app.dependency_overrides[get_agentcore_client] = lambda: fake_client
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


def _start_analysis(client, file_id) -> dict:
    """Helper to start an analysis and return the response JSON."""
    resp = client.post("/api/v1/analysis/start", json={"file_id": str(file_id)})
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- POST /start -----------------------------------------------------------


class TestStartAnalysis:
    def test_start_creates_session_and_persists_artifacts(self, client, db_session, test_user):
        data_file = _make_data_file(db_session, test_user)

        body = _start_analysis(client, data_file.id)

        # Session created and completed.
        assert body["session"]["file_id"] == str(data_file.id)
        assert body["session"]["status"] == "completed"
        assert body["session"]["started_at"] is not None
        assert body["session"]["completed_at"] is not None

        # Artifacts returned.
        assert len(body["results"]) == 1
        assert body["results"][0]["result_type"] == "descriptive_statistics"
        assert len(body["charts"]) == 1
        assert body["charts"][0]["chart_type"] == "bar"
        assert body["charts"][0]["title"] == "年龄分布"
        assert body["report"]["title"] == "医学数据分析报告"

        # Persisted in DB.
        session_id = uuid.UUID(body["session"]["id"])
        results = db_session.execute(
            select(AnalysisResult).where(AnalysisResult.session_id == session_id)
        ).scalars().all()
        charts = db_session.execute(
            select(Chart).where(Chart.session_id == session_id)
        ).scalars().all()
        reports = db_session.execute(
            select(Report).where(Report.session_id == session_id)
        ).scalars().all()
        assert len(results) == 1
        assert len(charts) == 1
        assert len(reports) == 1

    def test_start_invokes_agent(self, client, db_session, test_user, fake_client):
        data_file = _make_data_file(db_session, test_user)
        _start_analysis(client, data_file.id)
        assert len(fake_client.calls) == 1
        assert str(data_file.id) in fake_client.calls[0]["payload"]["prompt"]

    def test_start_requires_auth(self, db_session, test_user):
        data_file = _make_data_file(db_session, test_user)
        unauth = _unauthenticated_client(db_session)
        resp = unauth.post("/api/v1/analysis/start", json={"file_id": str(data_file.id)})
        assert resp.status_code == 401
        app.dependency_overrides.clear()

    def test_start_nonexistent_file(self, client):
        resp = client.post("/api/v1/analysis/start", json={"file_id": str(uuid.uuid4())})
        assert resp.status_code == 404

    def test_start_other_users_file_denied(self, client, db_session, other_user):
        # File belongs to other_user; test_user (client) must be denied with 403.
        data_file = _make_data_file(db_session, other_user)
        resp = client.post("/api/v1/analysis/start", json={"file_id": str(data_file.id)})
        assert resp.status_code == 403


# --- GET status/results/charts ---------------------------------------------


class TestRetrieval:
    def test_status_after_start(self, client, db_session, test_user):
        data_file = _make_data_file(db_session, test_user)
        body = _start_analysis(client, data_file.id)
        analysis_id = body["session"]["id"]

        resp = client.get(f"/api/v1/analysis/{analysis_id}/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["progress"] == 100
        assert data["stage"]

    def test_results_returns_persisted(self, client, db_session, test_user):
        data_file = _make_data_file(db_session, test_user)
        body = _start_analysis(client, data_file.id)
        analysis_id = body["session"]["id"]

        resp = client.get(f"/api/v1/analysis/{analysis_id}/results")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["result_data"]["mean"] == 42.5
        assert data["report"]["title"] == "医学数据分析报告"

    def test_charts_returns_persisted(self, client, db_session, test_user):
        data_file = _make_data_file(db_session, test_user)
        body = _start_analysis(client, data_file.id)
        analysis_id = body["session"]["id"]

        resp = client.get(f"/api/v1/analysis/{analysis_id}/charts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["charts"][0]["echarts_option"]["series"][0]["type"] == "bar"

    def test_status_nonexistent(self, client):
        resp = client.get(f"/api/v1/analysis/{uuid.uuid4()}/status")
        assert resp.status_code == 404

    def test_retrieval_requires_auth(self, db_session, test_user):
        data_file = _make_data_file(db_session, test_user)
        session = AnalysisSession(user_id=test_user.id, file_id=data_file.id, status="completed")
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        unauth = _unauthenticated_client(db_session)
        resp = unauth.get(f"/api/v1/analysis/{session.id}/results")
        assert resp.status_code == 401
        app.dependency_overrides.clear()

    def test_cross_user_results_denied(self, client, db_session, test_user, other_user, fake_client):
        data_file = _make_data_file(db_session, test_user)
        body = _start_analysis(client, data_file.id)
        analysis_id = body["session"]["id"]

        other = _make_client_for_user(db_session, other_user, fake_client)
        resp = other.get(f"/api/v1/analysis/{analysis_id}/results")
        assert resp.status_code == 403
        app.dependency_overrides.clear()


# --- Dimensions ------------------------------------------------------------


class TestDimensions:
    def test_add_dimension_creates_user_dimension_and_results(self, client, db_session, test_user):
        data_file = _make_data_file(db_session, test_user)
        analysis_id = _start_analysis(client, data_file.id)["session"]["id"]

        resp = client.post(
            f"/api/v1/analysis/{analysis_id}/dimensions",
            json={"description": "按性别分组比较血压"},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["dimension"]["dimension_type"] == "user"
        assert data["dimension"]["name"] == "按性别分组比较血压"
        # Supplementary artifacts persisted from the Agent response.
        assert len(data["results"]) == 1
        assert len(data["charts"]) == 1

        # Dimension persisted.
        dims = db_session.execute(
            select(AnalysisDimension).where(
                AnalysisDimension.session_id == uuid.UUID(analysis_id)
            )
        ).scalars().all()
        assert len(dims) == 1

    def test_add_dimension_with_explicit_name(self, client, db_session, test_user):
        data_file = _make_data_file(db_session, test_user)
        analysis_id = _start_analysis(client, data_file.id)["session"]["id"]

        resp = client.post(
            f"/api/v1/analysis/{analysis_id}/dimensions",
            json={"description": "desc", "name": "性别维度", "config": {"group_by": "sex"}},
        )
        assert resp.status_code == 201
        assert resp.json()["dimension"]["name"] == "性别维度"
        assert resp.json()["dimension"]["config"] == {"group_by": "sex"}

    def test_remove_dimension(self, client, db_session, test_user):
        data_file = _make_data_file(db_session, test_user)
        analysis_id = _start_analysis(client, data_file.id)["session"]["id"]

        add_resp = client.post(
            f"/api/v1/analysis/{analysis_id}/dimensions",
            json={"description": "按年龄分组"},
        )
        dim_id = add_resp.json()["dimension"]["id"]

        del_resp = client.delete(f"/api/v1/analysis/{analysis_id}/dimensions/{dim_id}")
        assert del_resp.status_code == 204

        dims = db_session.execute(
            select(AnalysisDimension).where(
                AnalysisDimension.session_id == uuid.UUID(analysis_id)
            )
        ).scalars().all()
        assert len(dims) == 0

    def test_remove_nonexistent_dimension(self, client, db_session, test_user):
        data_file = _make_data_file(db_session, test_user)
        analysis_id = _start_analysis(client, data_file.id)["session"]["id"]
        resp = client.delete(f"/api/v1/analysis/{analysis_id}/dimensions/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_add_dimension_cross_user_denied(self, client, db_session, test_user, other_user, fake_client):
        data_file = _make_data_file(db_session, test_user)
        analysis_id = _start_analysis(client, data_file.id)["session"]["id"]

        other = _make_client_for_user(db_session, other_user, fake_client)
        resp = other.post(
            f"/api/v1/analysis/{analysis_id}/dimensions",
            json={"description": "x"},
        )
        assert resp.status_code == 403
        app.dependency_overrides.clear()


# --- History ---------------------------------------------------------------


class TestHistory:
    def test_history_ordered_desc_and_scoped(self, client, db_session, test_user, other_user):
        # Three sessions for test_user with increasing created_at.
        f1 = _make_data_file(db_session, test_user, "a.csv")
        from datetime import datetime, timedelta, timezone

        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        ids = []
        for i in range(3):
            s = AnalysisSession(
                user_id=test_user.id,
                file_id=f1.id,
                status="completed",
                created_at=base + timedelta(days=i),
            )
            db_session.add(s)
            db_session.commit()
            db_session.refresh(s)
            ids.append(str(s.id))

        # A session belonging to other_user must not appear.
        f2 = _make_data_file(db_session, other_user, "b.csv")
        s_other = AnalysisSession(user_id=other_user.id, file_id=f2.id, status="completed")
        db_session.add(s_other)
        db_session.commit()

        resp = client.get("/api/v1/analysis/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        returned_ids = [s["id"] for s in data["sessions"]]
        # Descending by created_at => reverse of insertion order.
        assert returned_ids == list(reversed(ids))

    def test_history_requires_auth(self, db_session):
        unauth = _unauthenticated_client(db_session)
        resp = unauth.get("/api/v1/analysis/history")
        assert resp.status_code == 401
        app.dependency_overrides.clear()


# --- DELETE /{analysis_id} -------------------------------------------------


class TestDeleteAnalysis:
    def test_delete_removes_session_and_associated_data(self, client, db_session, test_user):
        data_file = _make_data_file(db_session, test_user)
        analysis_id = _start_analysis(client, data_file.id)["session"]["id"]
        session_uuid = uuid.UUID(analysis_id)

        resp = client.delete(f"/api/v1/analysis/{analysis_id}")
        assert resp.status_code == 204

        # Session and cascaded data removed.
        assert db_session.get(AnalysisSession, session_uuid) is None
        assert (
            db_session.execute(
                select(AnalysisResult).where(AnalysisResult.session_id == session_uuid)
            ).scalars().all()
            == []
        )
        assert (
            db_session.execute(
                select(Chart).where(Chart.session_id == session_uuid)
            ).scalars().all()
            == []
        )
        assert (
            db_session.execute(
                select(Report).where(Report.session_id == session_uuid)
            ).scalars().all()
            == []
        )

    def test_delete_nonexistent(self, client):
        resp = client.delete(f"/api/v1/analysis/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_delete_cross_user_denied(self, client, db_session, test_user, other_user, fake_client):
        data_file = _make_data_file(db_session, test_user)
        analysis_id = _start_analysis(client, data_file.id)["session"]["id"]

        other = _make_client_for_user(db_session, other_user, fake_client)
        resp = other.delete(f"/api/v1/analysis/{analysis_id}")
        assert resp.status_code == 403
        app.dependency_overrides.clear()
