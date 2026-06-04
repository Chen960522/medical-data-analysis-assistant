"""Tests for the conversational analysis (chat) API.

Covers: creating a chat session (with/without a linked analysis, cross-user and
nonexistent analysis), sending messages (persists user+assistant messages,
returns charts/results inline, increments turn_count, persists new artifacts to
the linked analysis), the 50-turn limit, fetching chronological history, and
fetching the conversation context (active dimensions split system/user +
generated charts).

The AgentCore client is injected via ``get_agentcore_client`` and overridden
with a fake returning canned ``AgentResponse`` objects, so no real AWS/Bedrock
calls are made.

Requirements: 9.1-9.22
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
from app.models.chat import ChatMessage, ChatSession
from app.models.data import DataFile
from app.models.user import User
from app.services.agentcore_client import AgentResponse

# --- Canned Agent artifacts ----------------------------------------------

ECHARTS_OPTION = {
    "title": {"text": "性别分组血压"},
    "xAxis": {"type": "category", "data": ["男", "女"]},
    "yAxis": {"type": "value"},
    "series": [{"type": "bar", "data": [128, 122]}],
}

ANALYSIS_RESULT = {
    "result_type": "group_comparison",
    "result_data": {"male_mean": 128.0, "female_mean": 122.0},
}


class FakeAgentCoreClient:
    """Fake AgentCore client returning canned responses and recording calls."""

    def __init__(self, response: AgentResponse | None = None):
        self._response = response or AgentResponse(
            response="已按性别分组比较血压。",
            charts=[ECHARTS_OPTION],
            analysis_results=[ANALYSIS_RESULT],
            report=None,
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


def _make_analysis(db_session, user, *, with_artifacts=False) -> AnalysisSession:
    """Create an AnalysisSession owned by user, optionally with artifacts."""
    data_file = _make_data_file(db_session, user)
    session = AnalysisSession(
        user_id=user.id,
        file_id=data_file.id,
        status="completed",
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    if with_artifacts:
        db_session.add_all(
            [
                AnalysisDimension(
                    session_id=session.id, name="年龄分组", dimension_type="system"
                ),
                AnalysisDimension(
                    session_id=session.id, name="性别分组", dimension_type="user"
                ),
                AnalysisResult(
                    session_id=session.id,
                    result_type="descriptive_statistics",
                    result_data={"mean": 42.5},
                ),
                Chart(
                    session_id=session.id,
                    chart_type="bar",
                    title="年龄分布",
                    echarts_option=ECHARTS_OPTION,
                ),
            ]
        )
        db_session.commit()

    return session


@pytest.fixture
def fake_client():
    """Shared fake AgentCore client."""
    return FakeAgentCoreClient()


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


def _create_session(client, analysis_session_id=None) -> dict:
    """Helper to create a chat session and return the response JSON."""
    body = {}
    if analysis_session_id is not None:
        body["analysis_session_id"] = str(analysis_session_id)
    resp = client.post("/api/v1/chat/sessions", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- POST /sessions --------------------------------------------------------


class TestCreateSession:
    def test_create_without_analysis(self, client):
        body = _create_session(client)
        assert body["analysis_session_id"] is None
        assert body["turn_count"] == 0
        assert body["id"]

    def test_create_with_analysis(self, client, db_session, test_user):
        analysis = _make_analysis(db_session, test_user)
        body = _create_session(client, analysis.id)
        assert body["analysis_session_id"] == str(analysis.id)
        assert body["turn_count"] == 0

    def test_create_with_nonexistent_analysis(self, client):
        resp = client.post(
            "/api/v1/chat/sessions", json={"analysis_session_id": str(uuid.uuid4())}
        )
        assert resp.status_code == 404

    def test_create_with_cross_user_analysis_denied(self, client, db_session, other_user):
        analysis = _make_analysis(db_session, other_user)
        resp = client.post(
            "/api/v1/chat/sessions", json={"analysis_session_id": str(analysis.id)}
        )
        assert resp.status_code == 403

    def test_create_requires_auth(self, db_session):
        unauth = _unauthenticated_client(db_session)
        resp = unauth.post("/api/v1/chat/sessions", json={})
        assert resp.status_code == 401
        app.dependency_overrides.clear()


# --- POST /sessions/{id}/messages ------------------------------------------


class TestSendMessage:
    def test_send_persists_messages_and_returns_artifacts(self, client, db_session, test_user):
        session_id = _create_session(client)["id"]

        resp = client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"message": "按性别分组比较血压"},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()

        # Assistant reply + inline artifacts returned.
        assert data["message"]["role"] == "assistant"
        assert data["message"]["content"] == "已按性别分组比较血压。"
        assert len(data["charts"]) == 1
        assert len(data["analysis_results"]) == 1
        assert data["turn_count"] == 1

        # Assistant metadata carries the artifacts for inline display.
        assert data["message"]["metadata"]["analysis_results"][0]["result_type"] == "group_comparison"

        # Both user and assistant messages persisted.
        messages = db_session.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == uuid.UUID(session_id))
            .order_by(ChatMessage.created_at.asc())
        ).scalars().all()
        assert [m.role for m in messages] == ["user", "assistant"]
        assert messages[0].content == "按性别分组比较血压"

    def test_send_invokes_agent_with_session_id(self, client, fake_client):
        session_id = _create_session(client)["id"]
        client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"message": "你好"},
        )
        assert len(fake_client.calls) == 1
        assert fake_client.calls[0]["session_id"] == session_id
        assert fake_client.calls[0]["payload"]["prompt"] == "你好"

    def test_send_increments_turn_count(self, client):
        session_id = _create_session(client)["id"]
        for expected in (1, 2, 3):
            resp = client.post(
                f"/api/v1/chat/sessions/{session_id}/messages",
                json={"message": f"消息 {expected}"},
            )
            assert resp.json()["turn_count"] == expected

    def test_send_persists_artifacts_to_linked_analysis(self, client, db_session, test_user):
        analysis = _make_analysis(db_session, test_user)
        session_id = _create_session(client, analysis.id)["id"]

        client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"message": "按性别分组比较血压"},
        )

        # New chart/result added to the linked analysis dashboard (Req 9.13).
        charts = db_session.execute(
            select(Chart).where(Chart.session_id == analysis.id)
        ).scalars().all()
        results = db_session.execute(
            select(AnalysisResult).where(AnalysisResult.session_id == analysis.id)
        ).scalars().all()
        assert len(charts) == 1
        assert len(results) == 1
        assert charts[0].chart_type == "bar"

    def test_send_context_includes_linked_analysis(self, client, db_session, test_user, fake_client):
        analysis = _make_analysis(db_session, test_user, with_artifacts=True)
        session_id = _create_session(client, analysis.id)["id"]

        client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"message": "和之前的年龄分组比较"},
        )
        context = fake_client.calls[0]["payload"]["analysis_context"]
        assert context["analysis_session_id"] == str(analysis.id)
        assert len(context["executed_analyses"]) == 1
        assert len(context["active_dimensions"]) == 2
        assert len(context["generated_charts"]) == 1

    def test_send_nonexistent_session(self, client):
        resp = client.post(
            f"/api/v1/chat/sessions/{uuid.uuid4()}/messages",
            json={"message": "hi"},
        )
        assert resp.status_code == 404

    def test_send_cross_user_denied(self, client, db_session, test_user, other_user, fake_client):
        session_id = _create_session(client)["id"]
        other = _make_client_for_user(db_session, other_user, fake_client)
        resp = other.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"message": "hi"},
        )
        assert resp.status_code == 403
        app.dependency_overrides.clear()

    def test_send_requires_auth(self, db_session, test_user):
        # Create a session directly in the DB for the unauth attempt.
        session = ChatSession(user_id=test_user.id, turn_count=0)
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        unauth = _unauthenticated_client(db_session)
        resp = unauth.post(
            f"/api/v1/chat/sessions/{session.id}/messages",
            json={"message": "hi"},
        )
        assert resp.status_code == 401
        app.dependency_overrides.clear()


# --- 50-turn limit ---------------------------------------------------------


class TestTurnLimit:
    def test_send_rejected_at_limit_without_agent_call(self, client, db_session, test_user, fake_client):
        # Seed a session already at the cap.
        session = ChatSession(user_id=test_user.id, turn_count=50)
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        resp = client.post(
            f"/api/v1/chat/sessions/{session.id}/messages",
            json={"message": "再来一个分析"},
        )
        assert resp.status_code == 409
        # No Agent call was made and turn_count is unchanged.
        assert len(fake_client.calls) == 0
        db_session.refresh(session)
        assert session.turn_count == 50

    def test_send_allowed_just_below_limit(self, client, db_session, test_user):
        session = ChatSession(user_id=test_user.id, turn_count=49)
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        resp = client.post(
            f"/api/v1/chat/sessions/{session.id}/messages",
            json={"message": "最后一轮"},
        )
        assert resp.status_code == 201
        assert resp.json()["turn_count"] == 50


# --- GET /sessions/{id}/messages -------------------------------------------


class TestGetMessages:
    def test_history_is_chronological(self, client):
        session_id = _create_session(client)["id"]
        client.post(
            f"/api/v1/chat/sessions/{session_id}/messages", json={"message": "第一条"}
        )
        client.post(
            f"/api/v1/chat/sessions/{session_id}/messages", json={"message": "第二条"}
        )

        resp = client.get(f"/api/v1/chat/sessions/{session_id}/messages")
        assert resp.status_code == 200
        data = resp.json()
        # 2 turns => 4 messages (user/assistant alternating chronologically).
        assert data["total"] == 4
        roles = [m["role"] for m in data["messages"]]
        assert roles == ["user", "assistant", "user", "assistant"]
        assert data["messages"][0]["content"] == "第一条"

    def test_history_empty_for_new_session(self, client):
        session_id = _create_session(client)["id"]
        resp = client.get(f"/api/v1/chat/sessions/{session_id}/messages")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_history_requires_auth(self, db_session, test_user):
        session = ChatSession(user_id=test_user.id, turn_count=0)
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        unauth = _unauthenticated_client(db_session)
        resp = unauth.get(f"/api/v1/chat/sessions/{session.id}/messages")
        assert resp.status_code == 401
        app.dependency_overrides.clear()

    def test_history_cross_user_denied(self, client, db_session, test_user, other_user, fake_client):
        session_id = _create_session(client)["id"]
        other = _make_client_for_user(db_session, other_user, fake_client)
        resp = other.get(f"/api/v1/chat/sessions/{session_id}/messages")
        assert resp.status_code == 403
        app.dependency_overrides.clear()


# --- GET /sessions/{id}/context --------------------------------------------


class TestGetContext:
    def test_context_distinguishes_system_and_user_dimensions(self, client, db_session, test_user):
        analysis = _make_analysis(db_session, test_user, with_artifacts=True)
        session_id = _create_session(client, analysis.id)["id"]

        resp = client.get(f"/api/v1/chat/sessions/{session_id}/context")
        assert resp.status_code == 200
        data = resp.json()
        assert data["analysis_session_id"] == str(analysis.id)
        assert len(data["executed_analyses"]) == 1
        assert len(data["generated_charts"]) == 1

        dim_types = {d["name"]: d["dimension_type"] for d in data["active_dimensions"]}
        assert dim_types == {"年龄分组": "system", "性别分组": "user"}

    def test_context_empty_without_linked_analysis(self, client):
        session_id = _create_session(client)["id"]
        resp = client.get(f"/api/v1/chat/sessions/{session_id}/context")
        assert resp.status_code == 200
        data = resp.json()
        assert data["analysis_session_id"] is None
        assert data["executed_analyses"] == []
        assert data["active_dimensions"] == []
        assert data["generated_charts"] == []

    def test_context_requires_auth(self, db_session, test_user):
        session = ChatSession(user_id=test_user.id, turn_count=0)
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        unauth = _unauthenticated_client(db_session)
        resp = unauth.get(f"/api/v1/chat/sessions/{session.id}/context")
        assert resp.status_code == 401
        app.dependency_overrides.clear()

    def test_context_cross_user_denied(self, client, db_session, test_user, other_user, fake_client):
        session_id = _create_session(client)["id"]
        other = _make_client_for_user(db_session, other_user, fake_client)
        resp = other.get(f"/api/v1/chat/sessions/{session_id}/context")
        assert resp.status_code == 403
        app.dependency_overrides.clear()
