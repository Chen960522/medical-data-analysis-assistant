"""Tests for the AgentCore entrypoint and runtime client.

Coverage:
    * Pure response-parsing helpers (``extract_charts`` /
      ``extract_analysis_results`` / ``extract_report``): parse embedded ECharts
      option JSON and report JSON, return empties for plain text, and skip
      malformed JSON gracefully.
    * ``handle_invocation`` with an injected fake agent returns the expected
      dict shape without a real Bedrock backend.
    * ``AgentCoreClient.invoke_agent`` with an injected fake runtime invoker
      returns a populated ``AgentResponse``; ``stop_session`` cleans up; and
      session create/resume/stop behaviour works.

These tests are designed to pass even without the ``bedrock-agentcore`` SDK
installed: the SDK is only touched by ``create_app`` (not exercised here), and
the parsing/invocation paths use lazy imports + injected stubs.

Requirements: 3.1-3.8, 9.5-9.13
"""

import json

import pytest

from app.agent import entrypoint
from app.agent.entrypoint import (
    extract_analysis_results,
    extract_charts,
    extract_report,
    handle_invocation,
)
from app.services.agentcore_client import (
    AgentCoreClient,
    AgentResponse,
    _decode_runtime_response,
)

# --- Fixtures / synthetic agent responses --------------------------------

ECHARTS_OPTION = {
    "title": {"text": "年龄分布"},
    "xAxis": {"type": "category", "data": ["20-30", "30-40", "40-50"]},
    "yAxis": {"type": "value"},
    "series": [{"type": "bar", "data": [12, 24, 18]}],
}

ANALYSIS_RESULT = {
    "result_type": "descriptive_statistics",
    "result_data": {"mean": 42.5, "median": 41.0, "std": 8.3},
    "display_order": 1,
}

REPORT_CONTENT = {
    "title": "医学数据分析报告",
    "sections": [
        {"name": "data_summary", "content": "共 1000 行，5 列。"},
        {"name": "key_findings", "content": "年龄与指标 X 显著相关。"},
    ],
}


def _agent_text_response() -> str:
    """A realistic plain-text-with-embedded-JSON agent reply."""
    return (
        "分析完成。以下是年龄分布图表：\n"
        f"{json.dumps(ECHARTS_OPTION, ensure_ascii=False)}\n"
        "描述性统计结果如下：\n"
        f"{json.dumps(ANALYSIS_RESULT, ensure_ascii=False)}\n"
        "并已生成报告：\n"
        f"{json.dumps(REPORT_CONTENT, ensure_ascii=False)}\n"
        "建议进一步分析分组比较。"
    )


@pytest.fixture(autouse=True)
def _reset_session_cache():
    """Ensure the module-level session→agent cache is clean per test."""
    entrypoint.reset()
    yield
    entrypoint.reset()


# --- extract_charts ------------------------------------------------------


class TestExtractCharts:
    def test_extracts_bare_echarts_option(self):
        text = f"图表：{json.dumps(ECHARTS_OPTION)}"
        charts = extract_charts(text)
        assert len(charts) == 1
        assert charts[0]["series"][0]["type"] == "bar"

    def test_extracts_from_wrapper_with_option_key(self):
        wrapper = {"chart_type": "bar", "option": ECHARTS_OPTION}
        charts = extract_charts(json.dumps(wrapper))
        assert len(charts) == 1
        assert charts[0] == ECHARTS_OPTION

    def test_extracts_from_charts_container(self):
        container = {"charts": [ECHARTS_OPTION, {"option": ECHARTS_OPTION}]}
        charts = extract_charts(json.dumps(container))
        assert len(charts) == 2

    def test_plain_text_returns_empty(self):
        assert extract_charts("这是纯文本回复，没有图表。") == []

    def test_malformed_json_is_skipped(self):
        text = '前缀 {"series": [}} 损坏 ' + json.dumps(ECHARTS_OPTION)
        charts = extract_charts(text)
        # The malformed block is skipped; the valid one is still found.
        assert len(charts) == 1
        assert charts[0]["series"][0]["data"] == [12, 24, 18]

    def test_non_chart_json_ignored(self):
        assert extract_charts(json.dumps({"foo": "bar"})) == []


# --- extract_analysis_results --------------------------------------------


class TestExtractAnalysisResults:
    def test_extracts_result_with_result_type(self):
        results = extract_analysis_results(json.dumps(ANALYSIS_RESULT))
        assert len(results) == 1
        assert results[0]["result_type"] == "descriptive_statistics"

    def test_extracts_from_container(self):
        container = {"analysis_results": [ANALYSIS_RESULT, ANALYSIS_RESULT]}
        results = extract_analysis_results(json.dumps(container))
        assert len(results) == 2

    def test_plain_text_returns_empty(self):
        assert extract_analysis_results("没有结构化结果。") == []

    def test_malformed_json_skipped(self):
        text = '{"result_type": } ' + json.dumps(ANALYSIS_RESULT)
        results = extract_analysis_results(text)
        assert len(results) == 1


# --- extract_report ------------------------------------------------------


class TestExtractReport:
    def test_extracts_report_with_sections(self):
        report = extract_report(json.dumps(REPORT_CONTENT))
        assert report is not None
        assert len(report["sections"]) == 2

    def test_extracts_from_report_wrapper(self):
        wrapper = {"report": REPORT_CONTENT}
        report = extract_report(json.dumps(wrapper))
        assert report is not None
        assert report["title"] == "医学数据分析报告"

    def test_plain_text_returns_none(self):
        assert extract_report("没有报告内容。") is None

    def test_malformed_json_skipped_returns_none(self):
        assert extract_report('{"sections": [}') is None


# --- combined parsing on a realistic mixed response ----------------------


class TestMixedResponseParsing:
    def test_all_artifacts_extracted(self):
        text = _agent_text_response()
        assert len(extract_charts(text)) == 1
        assert len(extract_analysis_results(text)) == 1
        report = extract_report(text)
        assert report is not None and len(report["sections"]) == 2


# --- handle_invocation ---------------------------------------------------


class _StubAgent:
    """A stub callable mimicking a Strands Agent for one canned reply."""

    def __init__(self, reply: str):
        self._reply = reply
        self.messages: list = []
        self.received_prompt: str | None = None

    def __call__(self, prompt: str) -> str:
        self.received_prompt = prompt
        return self._reply


class TestHandleInvocation:
    def test_returns_expected_shape(self, monkeypatch):
        stub = _StubAgent(_agent_text_response())
        monkeypatch.setattr(entrypoint, "build_agent", lambda: stub)

        result = handle_invocation(
            {
                "prompt": "请分析年龄分布",
                "session_id": "sess-1",
                "user_id": "user-1",
                "analysis_context": {},
            }
        )

        assert set(result.keys()) == {"response", "charts", "analysis_results", "report"}
        assert stub.received_prompt == "请分析年龄分布"
        assert isinstance(result["response"], str)
        assert len(result["charts"]) == 1
        assert len(result["analysis_results"]) == 1
        assert result["report"] is not None

    def test_plain_text_reply_yields_empty_artifacts(self, monkeypatch):
        stub = _StubAgent("你好，请先上传数据文件。")
        monkeypatch.setattr(entrypoint, "build_agent", lambda: stub)

        result = handle_invocation({"prompt": "你好", "session_id": "sess-2"})
        assert result["response"] == "你好，请先上传数据文件。"
        assert result["charts"] == []
        assert result["analysis_results"] == []
        assert result["report"] is None

    def test_session_agent_is_cached_and_reused(self, monkeypatch):
        created: list[_StubAgent] = []

        def _factory():
            agent = _StubAgent("ok")
            created.append(agent)
            return agent

        monkeypatch.setattr(entrypoint, "build_agent", _factory)

        handle_invocation({"prompt": "a", "session_id": "sess-shared"})
        handle_invocation({"prompt": "b", "session_id": "sess-shared"})
        # Same session id → only one agent built.
        assert len(created) == 1

    def test_prior_messages_seeded_into_agent(self, monkeypatch):
        stub = _StubAgent("ok")
        monkeypatch.setattr(entrypoint, "build_agent", lambda: stub)

        prior = [{"role": "user", "content": "之前的问题"}]
        handle_invocation(
            {
                "prompt": "后续问题",
                "session_id": "sess-ctx",
                "analysis_context": {"messages": prior},
            }
        )
        assert stub.messages == prior

    def test_empty_payload_is_tolerated(self, monkeypatch):
        stub = _StubAgent("空提示回复")
        monkeypatch.setattr(entrypoint, "build_agent", lambda: stub)
        result = handle_invocation({})
        assert result["response"] == "空提示回复"
        assert stub.received_prompt == ""


# --- _decode_runtime_response --------------------------------------------


class _FakeStreamingBody:
    """Mimics a boto3 StreamingBody exposing read() -> bytes."""

    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data


class TestDecodeRuntimeResponse:
    def test_decodes_boto3_streaming_body(self):
        payload = {"response": "hi", "charts": []}
        raw = {"response": _FakeStreamingBody(json.dumps(payload).encode("utf-8"))}
        decoded = _decode_runtime_response(raw)
        assert decoded["response"] == "hi"

    def test_decodes_json_string(self):
        decoded = _decode_runtime_response(json.dumps({"response": "x"}))
        assert decoded == {"response": "x"}

    def test_plain_text_body_wrapped(self):
        decoded = _decode_runtime_response("just text")
        assert decoded == {"response": "just text"}

    def test_passthrough_decoded_dict(self):
        raw = {"charts": [ECHARTS_OPTION], "analysis_results": []}
        decoded = _decode_runtime_response(raw)
        assert decoded["charts"] == [ECHARTS_OPTION]


# --- AgentCoreClient -----------------------------------------------------


def _make_client_with_fake(reply_payload: dict) -> tuple[AgentCoreClient, list]:
    """Build a client whose injected invoker records calls and returns a payload."""
    calls: list[dict] = []

    def _fake_invoker(payload, session_id, user_id):
        calls.append({"payload": payload, "session_id": session_id, "user_id": user_id})
        return {"response": _FakeStreamingBody(json.dumps(reply_payload).encode("utf-8"))}

    client = AgentCoreClient(runtime_invoker=_fake_invoker, runtime_arn="arn:fake", region="us-west-2")
    return client, calls


class TestAgentCoreClientInvoke:
    async def test_invoke_returns_populated_response(self):
        reply = {
            "response": "分析完成",
            "charts": [ECHARTS_OPTION],
            "analysis_results": [ANALYSIS_RESULT],
            "report": REPORT_CONTENT,
        }
        client, calls = _make_client_with_fake(reply)

        result = await client.invoke_agent({"prompt": "分析", "user_id": "u1"})

        assert isinstance(result, AgentResponse)
        assert result.response == "分析完成"
        assert result.charts == [ECHARTS_OPTION]
        assert result.analysis_results == [ANALYSIS_RESULT]
        assert result.report == REPORT_CONTENT
        assert result.session_id.startswith("session-")
        # The invoker received the resolved session id and user id.
        assert calls[0]["session_id"] == result.session_id
        assert calls[0]["user_id"] == "u1"

    async def test_invoke_parses_artifacts_from_text_when_not_prestructured(self):
        reply = {"response": _agent_text_response()}
        client, _ = _make_client_with_fake(reply)

        result = await client.invoke_agent({"prompt": "分析"})
        assert len(result.charts) == 1
        assert len(result.analysis_results) == 1
        assert result.report is not None

    async def test_invoke_resumes_existing_session(self):
        client, calls = _make_client_with_fake({"response": "ok"})
        sid = client.create_session(user_id="u1")

        result = await client.invoke_agent({"prompt": "继续"}, session_id=sid)
        assert result.session_id == sid
        # No new session was created.
        assert client.active_sessions == [sid]

    async def test_to_dict_shape(self):
        client, _ = _make_client_with_fake({"response": "ok"})
        result = await client.invoke_agent({"prompt": "x"})
        d = result.to_dict()
        assert set(d.keys()) == {"response", "charts", "analysis_results", "report", "session_id"}

    async def test_supports_awaitable_invoker(self):
        async def _async_invoker(payload, session_id, user_id):
            return {"response": "异步回复"}

        client = AgentCoreClient(runtime_invoker=_async_invoker, runtime_arn="arn:fake")
        result = await client.invoke_agent({"prompt": "x"})
        assert result.response == "异步回复"


class TestAgentCoreClientSessions:
    def test_create_generates_uuid_session(self):
        client = AgentCoreClient(runtime_invoker=lambda *a: {}, runtime_arn="arn:fake")
        sid = client.create_session(user_id="u1")
        assert sid.startswith("session-")
        assert client.has_session(sid)

    def test_create_resumes_known_session(self):
        client = AgentCoreClient(runtime_invoker=lambda *a: {}, runtime_arn="arn:fake")
        sid = client.create_session(user_id="u1")
        again = client.create_session(user_id="u1", session_id=sid)
        assert again == sid
        assert client.active_sessions == [sid]

    def test_create_with_explicit_unknown_id_uses_it(self):
        client = AgentCoreClient(runtime_invoker=lambda *a: {}, runtime_arn="arn:fake")
        sid = client.create_session(user_id="u1", session_id="custom-123")
        assert sid == "custom-123"
        assert client.has_session("custom-123")

    async def test_stop_session_deactivates(self):
        client, _ = _make_client_with_fake({"response": "ok"})
        result = await client.invoke_agent({"prompt": "x"})
        sid = result.session_id
        assert client.has_session(sid)

        await client.stop_session(sid)
        assert not client.has_session(sid)
        assert sid not in client.active_sessions

    async def test_stop_unknown_session_is_noop(self):
        client = AgentCoreClient(runtime_invoker=lambda *a: {}, runtime_arn="arn:fake")
        # Should not raise.
        await client.stop_session("does-not-exist")
