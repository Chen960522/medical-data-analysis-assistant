"""Amazon Bedrock AgentCore Runtime entrypoint for the 「医析」 Agent.

This module exposes the AgentCore Runtime entrypoint (:func:`handle_invocation`)
together with a set of *pure*, dependency-free response-parsing helpers used to
extract structured artifacts (ECharts chart configs, analysis results, and report
content) from the Agent's response.

Design / dependency notes
--------------------------
* The heavy ``bedrock-agentcore`` SDK is imported lazily inside
  :func:`create_app`. Importing this module (and using the parsing helpers /
  :func:`handle_invocation` with an injected agent) never requires the SDK.
* ``strands`` is only touched indirectly via :func:`app.agent.agent.build_agent`,
  which itself defers the import. Tests can monkeypatch
  :data:`build_agent` / :func:`create_agent_with_context` to inject a stub
  callable, exercising the full invocation path without Bedrock.
* The Agent's tool outputs are JSON strings (the chart-generation MCP returns an
  ECharts ``option`` JSON object; the report-generation MCP returns report
  content JSON). The parsing helpers scan the response text for embedded JSON
  blocks and pull out the relevant structures, tolerating plain-text-only
  responses (empty lists) and malformed JSON (skipped).

Requirements: 3.1-3.8, 9.5-9.13
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Iterator
from typing import Any

from .agent import build_agent, build_mcp_clients

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Session → Agent cache
# ---------------------------------------------------------------------------
_SESSION_AGENTS: dict[str, Any] = {}

# Global pre-warmed agent (started at app init time, not on first request)
_GLOBAL_AGENT: Any = None
_GLOBAL_AGENT_LOCK = threading.Lock()


def reset() -> None:
    """Clear the session→agent cache. Intended for tests."""
    global _GLOBAL_AGENT
    _SESSION_AGENTS.clear()
    _GLOBAL_AGENT = None


def _build_agent_parallel() -> Any:
    """Build agent, pre-starting MCP clients and filtering out failed ones.

    Calls start() on each client, then marks _tool_provider_started=True so
    Strands' load_tools() won't attempt a second start().
    """
    all_clients = build_mcp_clients()
    working_clients = []

    for client in all_clients:
        try:
            client.start()
            # Tell Strands the client is already started so it won't re-start
            client._tool_provider_started = True
            working_clients.append(client)
            logger.info("MCP client started: %s", client)
        except Exception as e:
            logger.warning("MCP client start failed (skipping): %s", e)

    return build_agent(mcp_clients=working_clients if working_clients else None)


def _warmup_in_background() -> None:
    """Start MCP clients in a background thread immediately at app init.

    By starting the background thread from create_app(), all MCP clients begin
    initializing concurrently while AgentCore counts down its 30s init window.
    The first real request will block on _GLOBAL_AGENT_LOCK until warmup
    completes, but the agent init itself is not part of the 30s window.
    """
    def _run():
        global _GLOBAL_AGENT
        try:
            agent = _build_agent_parallel()
            with _GLOBAL_AGENT_LOCK:
                _GLOBAL_AGENT = agent
            logger.info("Background agent warmup complete.")
        except Exception as e:
            logger.error("Background agent warmup failed: %s", e)

    t = threading.Thread(target=_run, daemon=True)
    t.start()


def _get_global_agent() -> Any:
    """Return the pre-warmed global agent, building it once on first call.

    Waits up to 55 seconds for the background warmup thread to finish.
    Raises RuntimeError if agent is not ready within the timeout.
    """
    global _GLOBAL_AGENT
    if _GLOBAL_AGENT is not None:
        return _GLOBAL_AGENT
    with _GLOBAL_AGENT_LOCK:
        if _GLOBAL_AGENT is None:
            _GLOBAL_AGENT = _build_agent_parallel()
    return _GLOBAL_AGENT


def create_agent_with_context(
    session_id: str,
    user_id: str = "",
    analysis_context: dict | None = None,
):
    """Return the Agent for a session, reusing the pre-warmed global instance.

    Uses the global pre-warmed agent (MCP clients already started) to avoid
    cold-start delays on the first request. Session-level message history is
    seeded from ``analysis_context`` when provided.

    Args:
        session_id: The AgentCore session identifier.
        user_id: The authenticated user id (reserved for per-user scoping).
        analysis_context: Optional accumulated context (prior messages etc.).

    Returns:
        A Strands ``Agent`` (or any injected stub callable).
    """
    analysis_context = analysis_context or {}

    if session_id and session_id in _SESSION_AGENTS:
        return _SESSION_AGENTS[session_id]

    # Use the pre-warmed global agent; fall back to building a fresh one if
    # _GLOBAL_AGENT was never initialised (e.g. in tests with mocked agents).
    agent = _get_global_agent()

    prior_messages = analysis_context.get("messages")
    if prior_messages:
        try:
            agent.messages = list(prior_messages)
        except (AttributeError, TypeError):
            pass

    if session_id:
        _SESSION_AGENTS[session_id] = agent

    return agent


def handle_invocation(payload: dict) -> dict:
    """AgentCore Runtime entrypoint function.

    Extracts the prompt and session context from ``payload``, builds/restores the
    Agent for the session, invokes it, and returns a structured response dict
    containing the natural-language reply plus the parsed charts, analysis
    results, and report content.

    Args:
        payload: The invocation payload. Recognised keys:
            ``prompt`` (str), ``session_id`` (str), ``user_id`` (str), and
            ``analysis_context`` (dict).

    Returns:
        A dict with keys ``response`` (str), ``charts`` (list[dict]),
        ``analysis_results`` (list[dict]), and ``report`` (dict | None).
    """
    payload = payload or {}
    prompt = payload.get("prompt", "")
    session_id = payload.get("session_id", "")
    user_id = payload.get("user_id", "")
    analysis_context = payload.get("analysis_context", {})

    agent = create_agent_with_context(session_id, user_id, analysis_context)
    response = agent(prompt)

    return {
        "response": _response_to_text(response),
        "charts": extract_charts(response),
        "analysis_results": extract_analysis_results(response),
        "report": extract_report(response),
    }


# ---------------------------------------------------------------------------
# Response parsing helpers (pure / dependency-free)
# ---------------------------------------------------------------------------
_CHART_CONTAINER_KEYS = ("charts",)
_ANALYSIS_CONTAINER_KEYS = ("analysis_results", "results")
_ECHARTS_OPTION_HINTS = ("series", "radar", "visualMap", "parallel")


def _response_to_text(response: Any) -> str:
    """Normalise an Agent response into a scannable text string.

    Handles plain strings, JSON-serialisable structures (dict/list), and
    Strands-style result objects (falling back to ``str`` and including a
    ``message`` payload when present).
    """
    if response is None:
        return ""
    if isinstance(response, str):
        return response
    if isinstance(response, (dict, list)):
        try:
            return json.dumps(response, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(response)

    parts = [str(response)]
    message = getattr(response, "message", None)
    if message is not None and not isinstance(message, str):
        try:
            parts.append(json.dumps(message, ensure_ascii=False, default=str))
        except (TypeError, ValueError):
            parts.append(str(message))
    return "\n".join(parts)


def _extract_balanced(text: str, start: int) -> tuple[str | None, int]:
    """Return the balanced ``{...}`` / ``[...]`` block starting at ``start``.

    String literals (and their escapes) are respected so braces inside JSON
    strings do not affect nesting depth. Returns ``(block, end_exclusive)`` or
    ``(None, start + 1)`` when no balanced block can be found.
    """
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
            if depth == 0:
                return text[start : i + 1], i + 1
    return None, start + 1


def _iter_json_candidates(text: str) -> Iterator[Any]:
    """Yield every top-level JSON value embedded in ``text``.

    Scans for balanced ``{...}`` / ``[...]`` blocks and attempts to parse each.
    Malformed blocks are skipped (the scan resumes after the block so a valid
    block following a malformed one is still discovered).
    """
    i = 0
    n = len(text)
    while i < n:
        if text[i] in "{[":
            block, end = _extract_balanced(text, i)
            if block is not None:
                try:
                    yield json.loads(block)
                except (ValueError, TypeError):
                    pass
                i = end
                continue
        i += 1


def _candidate_dicts(value: Any) -> list[dict]:
    """Flatten a parsed JSON value into a list of dicts to classify.

    Lists are unwrapped one or more levels; non-dict scalars are ignored.
    """
    dicts: list[dict] = []
    if isinstance(value, list):
        for element in value:
            dicts.extend(_candidate_dicts(element))
    elif isinstance(value, dict):
        dicts.append(value)
    return dicts


def _is_echarts_option(obj: Any) -> bool:
    """Heuristically determine whether ``obj`` is an ECharts ``option`` dict."""
    if not isinstance(obj, dict):
        return False
    if any(hint in obj for hint in _ECHARTS_OPTION_HINTS):
        return True
    return "xAxis" in obj and "yAxis" in obj


def extract_charts(response: Any) -> list[dict]:
    """Extract ECharts ``option`` configs from an Agent response.

    Recognises bare option objects (``{"series": [...]}``), wrapper objects
    (``{"chart_type": "bar", "option": {...}}``), and container objects
    (``{"charts": [...]}``), including any of the above nested inside JSON arrays.

    Args:
        response: The Agent response (string, structure, or result object).

    Returns:
        A list of ECharts ``option`` dicts (empty for plain-text responses).
    """
    charts: list[dict] = []
    for value in _iter_json_candidates(_response_to_text(response)):
        for candidate in _candidate_dicts(value):
            # Expand explicit chart containers first.
            expanded = False
            for key in _CHART_CONTAINER_KEYS:
                container = candidate.get(key)
                if isinstance(container, list):
                    expanded = True
                    for item in container:
                        _append_chart(charts, item)
            if expanded:
                continue
            _append_chart(charts, candidate)
    return charts


def _append_chart(charts: list[dict], candidate: Any) -> None:
    """Append the ECharts option from ``candidate`` to ``charts`` if present."""
    if _is_echarts_option(candidate):
        charts.append(candidate)
        return
    if isinstance(candidate, dict):
        option = candidate.get("option")
        if _is_echarts_option(option):
            charts.append(option)


def extract_analysis_results(response: Any) -> list[dict]:
    """Extract analysis-result structures from an Agent response.

    Recognises result objects carrying a ``result_type`` key (matching the
    ``AnalysisResult`` data model) as well as container objects
    (``{"analysis_results": [...]}`` / ``{"results": [...]}``).

    Args:
        response: The Agent response (string, structure, or result object).

    Returns:
        A list of analysis-result dicts (empty for plain-text responses).
    """
    results: list[dict] = []
    for value in _iter_json_candidates(_response_to_text(response)):
        for candidate in _candidate_dicts(value):
            expanded = False
            for key in _ANALYSIS_CONTAINER_KEYS:
                container = candidate.get(key)
                if isinstance(container, list):
                    expanded = True
                    for item in container:
                        if isinstance(item, dict) and "result_type" in item:
                            results.append(item)
            if expanded:
                continue
            if "result_type" in candidate:
                results.append(candidate)
    return results


def extract_report(response: Any) -> dict | None:
    """Extract structured report content from an Agent response.

    Recognises a report object carrying a ``sections`` key (matching the
    ``Report`` data model), either at the top level or wrapped under a
    ``report`` key. Returns the first match, or ``None`` when no report is found.

    Args:
        response: The Agent response (string, structure, or result object).

    Returns:
        The report content dict, or ``None``.
    """
    for value in _iter_json_candidates(_response_to_text(response)):
        for candidate in _candidate_dicts(value):
            if "sections" in candidate:
                return candidate
            nested = candidate.get("report")
            if isinstance(nested, dict) and "sections" in nested:
                return nested
    return None


# ---------------------------------------------------------------------------
# AgentCore application factory
# ---------------------------------------------------------------------------
def create_app():
    """Build the Bedrock AgentCore application and register the entrypoint.

    Does NO initialization — returns immediately so AgentCore's 30s window
    is not exceeded. The global agent and MCP clients are initialized lazily
    on the first :func:`handle_invocation` call.

    Returns:
        A ``BedrockAgentCoreApp`` with :func:`handle_invocation` registered.

    Raises:
        RuntimeError: If the ``bedrock-agentcore`` package is not installed.
    """
    try:
        from bedrock_agentcore.runtime import BedrockAgentCoreApp  # lazy import
    except Exception as exc:  # pragma: no cover - depends on optional dep
        raise RuntimeError(
            "The 'bedrock-agentcore' package is required to run the AgentCore app. "
            "Install it with 'pip install bedrock-agentcore'."
        ) from exc

    app = BedrockAgentCoreApp()
    app.entrypoint(handle_invocation)
    return app


if __name__ == "__main__":  # pragma: no cover - runtime entrypoint
    create_app().run()
