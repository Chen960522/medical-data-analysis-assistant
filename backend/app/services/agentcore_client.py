"""Client for invoking the 「医析」 Agent on Amazon Bedrock AgentCore Runtime.

This service encapsulates the AgentCore Runtime call (``invoke_agent_runtime``)
and session lifecycle (create / resume / stop), parsing the returned payload into
a dependency-free :class:`AgentResponse` using the shared response-parsing helpers
from :mod:`app.agent.entrypoint`.

Design / dependency notes
--------------------------
* ``boto3`` is imported lazily inside the runtime-invoker factory so importing
  this module never requires AWS SDKs.
* The underlying runtime invoker is injectable (constructor argument or
  :meth:`AgentCoreClient.configure_invoker`), so tests can supply a fake and
  avoid real AWS calls.
* Session management is in-memory: sessions are tracked in a dict; a uuid is
  generated when no session id is supplied, and an existing id is resumed.

Requirements: 3.1-3.8, 9.5-9.13
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ..agent.entrypoint import (
    extract_analysis_results,
    extract_charts,
    extract_report,
)
from ..core.config import settings

# A runtime invoker is any callable taking (payload, session_id, user_id) and
# returning the raw runtime response (a dict, JSON string, or mapping with a
# ``response`` body). This indirection makes the AWS call injectable for tests.
RuntimeInvoker = Callable[[dict, str, str], Any]


@dataclass
class AgentResponse:
    """Structured result of an AgentCore invocation (dependency-free).

    Attributes:
        response: The Agent's natural-language reply text.
        charts: Parsed ECharts ``option`` configs.
        analysis_results: Parsed analysis-result structures.
        report: Parsed structured report content (or ``None``).
        session_id: The AgentCore session id this response belongs to.
    """

    response: str = ""
    charts: list[dict] = field(default_factory=list)
    analysis_results: list[dict] = field(default_factory=list)
    report: dict | None = None
    session_id: str = ""

    def to_dict(self) -> dict:
        """Return a plain-dict representation of the response."""
        return {
            "response": self.response,
            "charts": self.charts,
            "analysis_results": self.analysis_results,
            "report": self.report,
            "session_id": self.session_id,
        }


def _decode_runtime_response(raw: Any) -> dict:
    """Normalise a raw runtime response into a dict payload.

    Handles:
        * already-decoded dicts (returned as-is),
        * JSON strings / bytes,
        * boto3-style responses carrying a streaming ``response`` body (an object
          with ``.read()``) or a plain string under ``response``.
    """
    if raw is None:
        return {}
    if isinstance(raw, dict) and "response" not in raw and (
        "charts" in raw or "analysis_results" in raw or "report" in raw
    ):
        # Already a decoded entrypoint-style dict without a streaming body.
        return raw

    body: Any = raw
    if isinstance(raw, dict):
        body = raw.get("response", raw)

    # boto3 StreamingBody (or any object exposing read()).
    read = getattr(body, "read", None)
    if callable(read):
        body = read()

    if isinstance(body, bytes):
        body = body.decode("utf-8")

    if isinstance(body, str):
        try:
            decoded = json.loads(body)
        except (ValueError, TypeError):
            return {"response": body}
        return decoded if isinstance(decoded, dict) else {"response": body}

    if isinstance(body, dict):
        return body

    return {"response": str(body)}


class AgentCoreClient:
    """Encapsulates Bedrock AgentCore Runtime invocation and session lifecycle."""

    def __init__(
        self,
        runtime_invoker: RuntimeInvoker | None = None,
        runtime_arn: str | None = None,
        region: str | None = None,
        qualifier: str | None = None,
    ) -> None:
        """Initialise the client.

        Args:
            runtime_invoker: Optional injected callable performing the runtime
                call. When omitted, a boto3-backed invoker is created lazily on
                first use (no AWS SDK import happens at construction time).
            runtime_arn: AgentCore Runtime ARN. Defaults to
                ``settings.agentcore_runtime_arn``.
            region: AWS region. Defaults to ``settings.agentcore_region``.
            qualifier: Optional runtime version/alias qualifier. Defaults to
                ``settings.agentcore_qualifier``.
        """
        self._runtime_invoker = runtime_invoker
        self._runtime_arn = runtime_arn if runtime_arn is not None else settings.agentcore_runtime_arn
        self._region = region if region is not None else settings.agentcore_region
        self._qualifier = qualifier if qualifier is not None else settings.agentcore_qualifier
        # Tracks active sessions: session_id -> {"user_id": ..., "active": bool}.
        self._sessions: dict[str, dict] = {}

    # -- configuration ---------------------------------------------------
    def configure_invoker(self, runtime_invoker: RuntimeInvoker) -> None:
        """Inject/override the runtime invoker (used by tests)."""
        self._runtime_invoker = runtime_invoker

    # -- session management ----------------------------------------------
    @property
    def active_sessions(self) -> list[str]:
        """Return the ids of currently active sessions."""
        return [sid for sid, meta in self._sessions.items() if meta.get("active")]

    def create_session(self, user_id: str = "", session_id: str | None = None) -> str:
        """Create a new session or resume an existing one.

        Args:
            user_id: The authenticated user id to associate with the session.
            session_id: Optional existing session id to resume. When omitted (or
                unknown) a new uuid-based session id is generated.

        Returns:
            The active session id.
        """
        if session_id and session_id in self._sessions:
            # Resume: re-activate and refresh ownership.
            meta = self._sessions[session_id]
            meta["active"] = True
            if user_id:
                meta["user_id"] = user_id
            return session_id

        resolved = session_id or f"session-{uuid.uuid4().hex}"
        self._sessions[resolved] = {"user_id": user_id, "active": True}
        return resolved

    def has_session(self, session_id: str) -> bool:
        """Return whether ``session_id`` is a known, active session."""
        meta = self._sessions.get(session_id)
        return bool(meta and meta.get("active"))

    # -- invocation ------------------------------------------------------
    def _get_runtime_invoker(self) -> RuntimeInvoker:
        """Return the configured invoker, building a boto3-backed one lazily."""
        if self._runtime_invoker is not None:
            return self._runtime_invoker
        self._runtime_invoker = self._build_boto3_invoker()
        return self._runtime_invoker

    def _build_boto3_invoker(self) -> RuntimeInvoker:
        """Build a boto3-backed runtime invoker (lazy ``boto3`` import)."""
        try:
            import boto3  # lazy import
        except Exception as exc:  # pragma: no cover - depends on optional dep
            raise RuntimeError(
                "The 'boto3' package is required to invoke AgentCore Runtime. "
                "Install it with 'pip install boto3'."
            ) from exc

        if not self._runtime_arn:
            raise RuntimeError(
                "AgentCore Runtime ARN is not configured. Set 'APP_AGENTCORE_RUNTIME_ARN' "
                "or pass runtime_arn to AgentCoreClient."
            )

        client = boto3.client("bedrock-agentcore", region_name=self._region)
        runtime_arn = self._runtime_arn
        qualifier = self._qualifier

        def _invoke(payload: dict, session_id: str, user_id: str) -> Any:
            kwargs: dict[str, Any] = {
                "agentRuntimeArn": runtime_arn,
                "runtimeSessionId": session_id,
                "payload": json.dumps(payload).encode("utf-8"),
                "contentType": "application/json",
                "accept": "application/json",
            }
            if user_id:
                kwargs["runtimeUserId"] = user_id
            if qualifier:
                kwargs["qualifier"] = qualifier
            return client.invoke_agent_runtime(**kwargs)

        return _invoke

    async def invoke_agent(self, payload: dict, session_id: str = "") -> AgentResponse:
        """Invoke the Agent on AgentCore Runtime and parse the response.

        Args:
            payload: The invocation payload (e.g. ``prompt``, ``analysis_context``).
                A ``user_id`` may be supplied here to associate the session.
            session_id: Optional session id to resume; a new one is created when
                empty.

        Returns:
            A populated :class:`AgentResponse`.
        """
        payload = dict(payload or {})
        user_id = payload.get("user_id", "")
        resolved_session = self.create_session(user_id=user_id, session_id=session_id or None)

        # Ensure the payload carries the resolved session id for the runtime.
        payload.setdefault("session_id", resolved_session)

        invoker = self._get_runtime_invoker()
        raw = invoker(payload, resolved_session, user_id)
        # Support both sync and awaitable invokers.
        if hasattr(raw, "__await__"):
            raw = await raw

        decoded = _decode_runtime_response(raw)

        response_text = decoded.get("response", "")
        if not isinstance(response_text, str):
            response_text = json.dumps(response_text, ensure_ascii=False)

        # Prefer artifacts the runtime already extracted; otherwise parse the
        # response text with the shared helpers.
        charts = decoded.get("charts")
        if not isinstance(charts, list):
            charts = extract_charts(response_text)
        analysis_results = decoded.get("analysis_results")
        if not isinstance(analysis_results, list):
            analysis_results = extract_analysis_results(response_text)
        report = decoded.get("report")
        if not isinstance(report, dict):
            report = extract_report(response_text)

        return AgentResponse(
            response=response_text,
            charts=charts,
            analysis_results=analysis_results,
            report=report,
            session_id=resolved_session,
        )

    async def stop_session(self, session_id: str) -> None:
        """Stop an AgentCore session and release its resources.

        Marks the session inactive locally and, when a boto3 invoker / ARN is
        configured, calls ``stop_runtime_session``. Unknown sessions are a no-op.

        Args:
            session_id: The session id to stop.
        """
        if session_id not in self._sessions:
            return

        # Best-effort remote stop only when a real runtime is configured and the
        # invoker has not been overridden with a fake (fakes set _runtime_invoker).
        if self._runtime_invoker is None and self._runtime_arn:
            await self._stop_remote_session(session_id)

        self._sessions[session_id]["active"] = False

    async def _stop_remote_session(self, session_id: str) -> None:  # pragma: no cover - needs AWS
        """Call ``stop_runtime_session`` on the AgentCore Runtime."""
        try:
            import boto3  # lazy import
        except Exception:
            return

        client = boto3.client("bedrock-agentcore", region_name=self._region)
        kwargs: dict[str, Any] = {
            "runtimeSessionId": session_id,
            "agentRuntimeArn": self._runtime_arn,
        }
        if self._qualifier:
            kwargs["qualifier"] = self._qualifier
        client.stop_runtime_session(**kwargs)
