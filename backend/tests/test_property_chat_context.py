"""Property-based tests for conversation context accumulation consistency.

Validates: Requirements 9.14, 9.15, 9.19, 9.20, 9.21
Property 17: 对话上下文累积一致性 (Conversation context accumulation consistency)

    For any conversation message sequence (length <= 50), the conversation
    context SHALL correctly accumulate all executed analyses, generated charts,
    and active analysis dimensions, and the number of items in the context SHALL
    be consistent with the actual number of operations executed.

The chat API under ``app.api.v1.chat`` is the source of truth and is NOT
modified by these tests. Each ``send_message`` call that is linked to an
analysis session appends the Agent-returned charts/results onto that analysis
session (via ``_persist_charts`` / ``_persist_results``), while the active
dimensions are unchanged by the (fake) Agent. The ``GET .../context`` endpoint
derives ``executed_analyses`` / ``active_dimensions`` / ``generated_charts``
from the linked analysis session.

So after ``N`` successful sends (``N <= 50``) where the Agent returns ``K``
charts and ``M`` results per turn, starting from an analysis seeded with
``0`` charts/results and ``n_sys`` system + ``n_user`` user dimensions:

    * ``len(generated_charts)   == N * K``
    * ``len(executed_analyses)  == N * M``
    * ``len(active_dimensions)  == n_sys + n_user`` (Agent adds none, Req 9.19)
    * ``turn_count              == N``
    * message history length    == ``2 * N`` (user+assistant per turn, Req 9.14/9.15)

Performance / isolation notes
-----------------------------
Each Hypothesis example builds and tears down a FRESH in-memory SQLite database
inside the test body (not via a function-scoped fixture) so examples never leak
state and the ``function_scoped_fixture`` health check is never triggered. The
FastAPI ``TestClient`` and its dependency overrides are installed per example
and cleared in a ``finally`` block. A constant dummy password hash is used for
the generated user (Property 17 does not exercise password verification), and
``deadline=None`` disables per-example time limits because each example performs
schema setup plus several HTTP requests.
"""

import uuid
from contextlib import contextmanager

from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.analysis import get_agentcore_client
from app.core.database import get_db
from app.main import app
from app.middleware.auth import get_current_user
from app.models.analysis import AnalysisDimension, AnalysisSession
from app.models.base import Base
from app.models.chat import ChatSession
from app.models.data import DataFile
from app.models.user import User
from app.services.agentcore_client import AgentResponse

# A constant, valid-looking bcrypt hash. Property 17 only exercises context
# accumulation, so the slow bcrypt key-expansion is intentionally avoided.
DUMMY_PASSWORD_HASH = "$2b$12$" + "x" * 53


# --- Fake Agent ------------------------------------------------------------


def _make_chart_options(k: int) -> list[dict]:
    """Return ``k`` ECharts option dicts with derivable titles/types."""
    return [
        {
            "title": {"text": f"图表{i}"},
            "xAxis": {"type": "category", "data": ["男", "女"]},
            "yAxis": {"type": "value"},
            "series": [{"type": "bar", "data": [1 + i, 2 + i]}],
        }
        for i in range(k)
    ]


def _make_result_items(m: int) -> list[dict]:
    """Return ``m`` analysis-result dicts (each a {result_type, result_data})."""
    return [
        {"result_type": "group_comparison", "result_data": {"index": i, "value": i * 1.0}}
        for i in range(m)
    ]


class FakeAgentCoreClient:
    """Fake AgentCore client returning a configurable number of artifacts.

    ``charts_per_turn`` (K) and ``results_per_turn`` (M) make the per-call
    artifact counts vary so the accumulation property can be exercised across
    inputs. Every call is recorded so the context payload passed to the Agent
    can be inspected.
    """

    def __init__(
        self,
        *,
        charts_per_turn: int = 1,
        results_per_turn: int = 1,
        response_text: str = "已完成分析。",
    ) -> None:
        self.charts_per_turn = charts_per_turn
        self.results_per_turn = results_per_turn
        self.response_text = response_text
        self.calls: list[dict] = []

    async def invoke_agent(self, payload: dict, session_id: str = "") -> AgentResponse:
        self.calls.append({"payload": payload, "session_id": session_id})
        return AgentResponse(
            response=self.response_text,
            charts=_make_chart_options(self.charts_per_turn),
            analysis_results=_make_result_items(self.results_per_turn),
            report=None,
            session_id=session_id or "session-fake",
        )


# --- DB / app helpers ------------------------------------------------------


@contextmanager
def fresh_session():
    """Yield a session bound to a brand-new in-memory SQLite database."""
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
        engine.dispose()


@contextmanager
def app_client(session, user: User, fake: FakeAgentCoreClient):
    """Yield a TestClient with db/auth/Agent overrides, cleared on exit."""

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_agentcore_client] = lambda: fake
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def _make_user(session) -> User:
    """Create and persist a verified user with a constant dummy hash."""
    user = User(
        email=f"chat_{uuid.uuid4().hex}@example.com",
        password_hash=DUMMY_PASSWORD_HASH,
        is_verified=True,
        is_locked=False,
        failed_login_count=0,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _make_analysis(session, user: User, *, n_sys: int = 0, n_user: int = 0) -> AnalysisSession:
    """Create an AnalysisSession with ``n_sys`` system + ``n_user`` user dims.

    The analysis starts with 0 charts and 0 results so accumulation counts are
    simply ``N * K`` / ``N * M`` after N sends.
    """
    data_file = DataFile(
        user_id=user.id,
        filename=f"{uuid.uuid4().hex}_data.csv",
        original_filename="data.csv",
        file_size=1024,
        file_format="csv",
        s3_key=f"data/{user.id}/data.csv",
        row_count=100,
        column_count=3,
        status="uploaded",
    )
    session.add(data_file)
    session.commit()
    session.refresh(data_file)

    analysis = AnalysisSession(user_id=user.id, file_id=data_file.id, status="completed")
    session.add(analysis)
    session.commit()
    session.refresh(analysis)

    dims = [
        AnalysisDimension(session_id=analysis.id, name=f"系统维度{i}", dimension_type="system")
        for i in range(n_sys)
    ] + [
        AnalysisDimension(session_id=analysis.id, name=f"用户维度{i}", dimension_type="user")
        for i in range(n_user)
    ]
    if dims:
        session.add_all(dims)
        session.commit()

    return analysis


def _create_linked_chat_session(client: TestClient, analysis_id) -> str:
    """Create a chat session linked to ``analysis_id`` and return its id."""
    resp = client.post(
        "/api/v1/chat/sessions", json={"analysis_session_id": str(analysis_id)}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _send(client: TestClient, session_id: str, text: str = "继续分析"):
    """Send one message; return the response object."""
    return client.post(
        f"/api/v1/chat/sessions/{session_id}/messages", json={"message": text}
    )


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestConversationContextAccumulationProperties:
    """Property 17 — conversation context accumulation consistency (Req 9.14-9.21)."""

    @given(
        num_messages=st.integers(min_value=0, max_value=12),
        charts_per_turn=st.integers(min_value=0, max_value=3),
        results_per_turn=st.integers(min_value=0, max_value=3),
        n_sys=st.integers(min_value=0, max_value=3),
        n_user=st.integers(min_value=0, max_value=3),
    )
    @settings(max_examples=30, deadline=None)
    def test_context_counts_match_executed_operations(
        self,
        num_messages: int,
        charts_per_turn: int,
        results_per_turn: int,
        n_sys: int,
        n_user: int,
    ) -> None:
        """Context item counts equal the actual number of executed operations.

        After ``N`` sends returning ``K`` charts and ``M`` results per turn,
        starting from an analysis seeded with ``n_sys`` system + ``n_user`` user
        dimensions and 0 charts/results:
          * ``generated_charts``  == ``N * K``                 (Req 9.15)
          * ``executed_analyses`` == ``N * M``                 (Req 9.15)
          * ``active_dimensions`` == ``n_sys + n_user`` and the system/user
            split is preserved (Req 9.19, distinguishes generated origins)
          * ``turn_count``        == ``N``
          * message history       == ``2 * N`` (Req 9.14/9.15 accumulation)

        Validates: Requirements 9.14, 9.15, 9.19, 9.20, 9.21
        """
        with fresh_session() as session:
            user = _make_user(session)
            analysis = _make_analysis(session, user, n_sys=n_sys, n_user=n_user)
            fake = FakeAgentCoreClient(
                charts_per_turn=charts_per_turn, results_per_turn=results_per_turn
            )

            with app_client(session, user, fake) as client:
                chat_id = _create_linked_chat_session(client, analysis.id)

                for i in range(num_messages):
                    resp = _send(client, chat_id, f"分析 {i}")
                    assert resp.status_code == 201, resp.text

                ctx = client.get(f"/api/v1/chat/sessions/{chat_id}/context")
                assert ctx.status_code == 200, ctx.text
                ctx_data = ctx.json()

                hist = client.get(f"/api/v1/chat/sessions/{chat_id}/messages")
                assert hist.status_code == 200, hist.text

            # Accumulated charts/results scale with the executed operations.
            assert len(ctx_data["generated_charts"]) == num_messages * charts_per_turn
            assert len(ctx_data["executed_analyses"]) == num_messages * results_per_turn

            # Active dimensions are unchanged by the (fake) Agent, and the
            # system/user origin split is preserved (Req 9.19).
            dims = ctx_data["active_dimensions"]
            assert len(dims) == n_sys + n_user
            assert sum(1 for d in dims if d["dimension_type"] == "system") == n_sys
            assert sum(1 for d in dims if d["dimension_type"] == "user") == n_user

            # Turn count and message history accumulate one turn (2 messages) each.
            assert ctx_data["turn_count"] == num_messages
            assert hist.json()["total"] == 2 * num_messages

    @given(
        num_messages=st.integers(min_value=1, max_value=8),
        charts_per_turn=st.integers(min_value=0, max_value=3),
        results_per_turn=st.integers(min_value=0, max_value=3),
    )
    @settings(max_examples=25, deadline=None)
    def test_context_passed_to_agent_grows_monotonically(
        self, num_messages: int, charts_per_turn: int, results_per_turn: int
    ) -> None:
        """The context the Agent sees accumulates monotonically across turns.

        ``_build_analysis_context`` is assembled BEFORE the new user message is
        persisted, so on the (1-indexed) i-th call the context reflects only the
        ``i - 1`` previously completed turns:
          * ``history`` length          == ``2 * (i - 1)``
          * ``executed_analyses`` count == ``(i - 1) * M``
          * ``generated_charts`` count  == ``(i - 1) * K``
        These counts are therefore non-decreasing across successive sends.

        Validates: Requirements 9.14, 9.15
        """
        with fresh_session() as session:
            user = _make_user(session)
            analysis = _make_analysis(session, user, n_sys=1, n_user=1)
            fake = FakeAgentCoreClient(
                charts_per_turn=charts_per_turn, results_per_turn=results_per_turn
            )

            with app_client(session, user, fake) as client:
                chat_id = _create_linked_chat_session(client, analysis.id)
                for i in range(num_messages):
                    resp = _send(client, chat_id, f"第 {i} 轮")
                    assert resp.status_code == 201, resp.text

            assert len(fake.calls) == num_messages

            prev_charts = -1
            prev_results = -1
            for j, call in enumerate(fake.calls):  # j is 0-indexed (i - 1)
                ctx = call["payload"]["analysis_context"]
                assert ctx["analysis_session_id"] == str(analysis.id)

                # Prior history seen on this call == 2 messages per prior turn.
                assert len(ctx["history"]) == 2 * j

                charts_seen = len(ctx["generated_charts"])
                results_seen = len(ctx["executed_analyses"])
                assert charts_seen == j * charts_per_turn
                assert results_seen == j * results_per_turn

                # Active dimensions are constant across turns (Agent adds none).
                assert len(ctx["active_dimensions"]) == 2

                # Monotonic, non-decreasing accumulation.
                assert charts_seen >= prev_charts
                assert results_seen >= prev_results
                prev_charts, prev_results = charts_seen, results_seen


# ---------------------------------------------------------------------------
# Example-based regression tests
# ---------------------------------------------------------------------------


class TestConversationContextAccumulationExamples:
    """Representative example-based regressions for Property 17 (Req 9.14-9.21)."""

    def test_three_turns_accumulate_charts_results_and_keep_dimensions(self) -> None:
        """1 sys + 1 user dim, K=1/M=1, 3 sends → 3 charts, 3 results, 2 dims.

        Validates: Requirements 9.14, 9.15, 9.19
        """
        with fresh_session() as session:
            user = _make_user(session)
            analysis = _make_analysis(session, user, n_sys=1, n_user=1)
            fake = FakeAgentCoreClient(charts_per_turn=1, results_per_turn=1)

            with app_client(session, user, fake) as client:
                chat_id = _create_linked_chat_session(client, analysis.id)
                for i in range(3):
                    assert _send(client, chat_id, f"轮 {i}").status_code == 201

                ctx = client.get(f"/api/v1/chat/sessions/{chat_id}/context").json()
                hist = client.get(f"/api/v1/chat/sessions/{chat_id}/messages").json()

            assert len(ctx["generated_charts"]) == 3
            assert len(ctx["executed_analyses"]) == 3
            assert ctx["turn_count"] == 3
            assert hist["total"] == 6

            dim_types = sorted(d["dimension_type"] for d in ctx["active_dimensions"])
            assert dim_types == ["system", "user"]

    def test_zero_messages_context_equals_initial_artifacts(self) -> None:
        """Zero sends → context equals the seeded analysis artifacts (Req 9.15)."""
        with fresh_session() as session:
            user = _make_user(session)
            analysis = _make_analysis(session, user, n_sys=2, n_user=1)
            fake = FakeAgentCoreClient(charts_per_turn=2, results_per_turn=2)

            with app_client(session, user, fake) as client:
                chat_id = _create_linked_chat_session(client, analysis.id)
                ctx = client.get(f"/api/v1/chat/sessions/{chat_id}/context").json()
                hist = client.get(f"/api/v1/chat/sessions/{chat_id}/messages").json()

            # No operations executed yet: charts/results stay at the initial 0.
            assert ctx["generated_charts"] == []
            assert ctx["executed_analyses"] == []
            assert ctx["turn_count"] == 0
            assert hist["total"] == 0
            # Dimensions reflect exactly what was seeded.
            assert len(ctx["active_dimensions"]) == 3
            assert sum(1 for d in ctx["active_dimensions"] if d["dimension_type"] == "system") == 2
            assert sum(1 for d in ctx["active_dimensions"] if d["dimension_type"] == "user") == 1

    def test_turn_with_zero_artifacts_keeps_counts_at_initial(self) -> None:
        """A send returning K=0/M=0 leaves charts/results counts unchanged.

        Validates: Requirements 9.15
        """
        with fresh_session() as session:
            user = _make_user(session)
            analysis = _make_analysis(session, user, n_sys=1, n_user=0)
            fake = FakeAgentCoreClient(charts_per_turn=0, results_per_turn=0)

            with app_client(session, user, fake) as client:
                chat_id = _create_linked_chat_session(client, analysis.id)
                assert _send(client, chat_id).status_code == 201

                ctx = client.get(f"/api/v1/chat/sessions/{chat_id}/context").json()
                hist = client.get(f"/api/v1/chat/sessions/{chat_id}/messages").json()

            assert ctx["generated_charts"] == []
            assert ctx["executed_analyses"] == []
            # The turn still happened: one user+assistant pair, turn_count 1.
            assert ctx["turn_count"] == 1
            assert hist["total"] == 2
            assert len(ctx["active_dimensions"]) == 1

    def test_at_turn_limit_send_rejected_and_context_unchanged(self) -> None:
        """At the 50-turn cap a send is 409 and the accumulated context is intact.

        This ties to the "length <= 50" clause of Property 17: beyond the cap no
        new operation executes, so context counts must not change.

        Validates: Requirements 9.14, 9.15
        """
        with fresh_session() as session:
            user = _make_user(session)
            analysis = _make_analysis(session, user, n_sys=1, n_user=1)
            # Seed the chat session already at the cap, linked to the analysis.
            chat = ChatSession(
                user_id=user.id, analysis_session_id=analysis.id, turn_count=50
            )
            session.add(chat)
            session.commit()
            session.refresh(chat)
            chat_id = str(chat.id)

            fake = FakeAgentCoreClient(charts_per_turn=2, results_per_turn=2)
            with app_client(session, user, fake) as client:
                before = client.get(f"/api/v1/chat/sessions/{chat_id}/context").json()

                resp = _send(client, chat_id, "再来一个分析")
                assert resp.status_code == 409

                after = client.get(f"/api/v1/chat/sessions/{chat_id}/context").json()

            # No Agent call, and the context is unchanged.
            assert fake.calls == []
            assert len(after["generated_charts"]) == len(before["generated_charts"]) == 0
            assert len(after["executed_analyses"]) == len(before["executed_analyses"]) == 0
            assert after["turn_count"] == before["turn_count"] == 50
            assert len(after["active_dimensions"]) == 2
