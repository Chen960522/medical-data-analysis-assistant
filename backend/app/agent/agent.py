"""Strands Agent assembly for the medical data analysis assistant.

This module wires the 「医析」 Agent together: a Bedrock model
(:mod:`app.agent.config`), the system prompt (:mod:`app.agent.prompts`), and the
eight MCP tool servers (5 open-source + 3 self-developed) connected over stdio.

All ``strands`` / ``mcp`` imports are performed lazily inside the factory
functions so that importing this module never requires the heavy AI SDKs. The
MCP server launch commands/args are sourced from application settings (with
defaults matching the design document), keeping the wiring configurable and
unit-testable.

MCP servers (per design.md):
    Open-source (5):
        - pubmed-mcp-server     : PubMed literature search
        - markitdown-mcp        : PDF/document → Markdown
        - pandas-mcp            : data analysis
        - aws-s3-mcp-server     : S3 file operations
        - postgres-mcp-server   : read-only SQL queries
    Self-developed (3):
        - chart-generation      : ECharts config generation
        - report-generation     : structured PDF/Word reports
        - cnki-search           : CNKI literature search

Requirements: 3.1-3.8, 9.5-9.9
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..core.config import settings
from .config import build_bedrock_model
from .prompts import SYSTEM_PROMPT

# Logical names for the 8 MCP servers the Agent orchestrates.
MCP_SERVER_NAMES: tuple[str, ...] = (
    # open-source
    "pubmed",
    "markitdown",
    "pandas",
    "s3",
    "postgres",
    # self-developed
    "chart_generation",
    "report_generation",
    "cnki_search",
)

EXPECTED_MCP_CLIENT_COUNT = len(MCP_SERVER_NAMES)


@dataclass(frozen=True)
class MCPServerSpec:
    """A dependency-free description of how to launch one MCP server over stdio.

    Attributes:
        name: Logical server name (one of :data:`MCP_SERVER_NAMES`).
        command: The executable to run (e.g. ``python`` or ``npx``).
        args: Positional arguments passed to the command.
        env: Optional environment variables for the subprocess.
    """

    name: str
    command: str
    args: list[str]
    env: dict[str, str] = field(default_factory=dict)


def _split_args(raw: str) -> list[str]:
    """Split a comma-separated settings string into a list of arguments."""
    return [part.strip() for part in raw.split(",") if part.strip()]


def _build_s3_env() -> dict[str, str]:
    """Build the environment for the aws-s3-mcp-server subprocess.

    ``AWS_REGION`` always comes from ``settings.bedrock_region`` (matching the
    design default of ``us-west-2``). When a custom S3 endpoint is configured
    (e.g. LocalStack in local/dev via ``settings.s3_endpoint_url``) it is passed
    through as ``AWS_ENDPOINT_URL`` / ``AWS_ENDPOINT_URL_S3`` so the server talks
    to the local stack instead of the real AWS endpoint. The default bucket name
    is forwarded as ``S3_BUCKET_NAME`` for convenience.

    Returns:
        The environment variable mapping for the S3 MCP server. ``AWS_REGION``
        is always present; endpoint keys are only added when configured.
    """
    env: dict[str, str] = {"AWS_REGION": settings.bedrock_region}

    endpoint = (settings.s3_endpoint_url or "").strip()
    if endpoint:
        env["AWS_ENDPOINT_URL"] = endpoint
        env["AWS_ENDPOINT_URL_S3"] = endpoint

    bucket = (settings.s3_bucket_name or "").strip()
    if bucket:
        env["S3_BUCKET_NAME"] = bucket

    return env


def get_mcp_server_specs() -> list[MCPServerSpec]:
    """Resolve the launch specifications for all 8 MCP servers from settings.

    This is a pure function (no ``strands``/``mcp`` import) returning plain
    dataclasses, so tests can verify the wiring without the SDKs installed.

    Returns:
        A list of :class:`MCPServerSpec`, one per server in
        :data:`MCP_SERVER_NAMES`.
    """
    # postgres-mcp-server needs the DB connection string appended as the final arg.
    postgres_args = _split_args(settings.mcp_postgres_args) + [settings.database_url]

    return [
        # === open-source MCP servers ===
        MCPServerSpec(
            name="pubmed",
            command=settings.mcp_pubmed_command,
            args=_split_args(settings.mcp_pubmed_args),
        ),
        MCPServerSpec(
            name="markitdown",
            command=settings.mcp_markitdown_command,
            args=_split_args(settings.mcp_markitdown_args),
        ),
        MCPServerSpec(
            name="pandas",
            command=settings.mcp_pandas_command,
            args=_split_args(settings.mcp_pandas_args),
        ),
        MCPServerSpec(
            name="s3",
            command=settings.mcp_s3_command,
            args=_split_args(settings.mcp_s3_args),
            env=_build_s3_env(),
        ),
        MCPServerSpec(
            name="postgres",
            command=settings.mcp_postgres_command,
            args=postgres_args,
        ),
        # === self-developed MCP servers ===
        MCPServerSpec(
            name="chart_generation",
            command=settings.mcp_chart_command,
            args=_split_args(settings.mcp_chart_args),
        ),
        MCPServerSpec(
            name="report_generation",
            command=settings.mcp_report_command,
            args=_split_args(settings.mcp_report_args),
        ),
        MCPServerSpec(
            name="cnki_search",
            command=settings.mcp_cnki_command,
            args=_split_args(settings.mcp_cnki_args),
        ),
    ]


def build_mcp_clients() -> list:
    """Build the 8 ``MCPClient`` instances the Agent connects to over stdio.

    ``strands`` / ``mcp`` are imported lazily here so that importing this module
    (and running the pure config/prompt unit tests) does not require the SDKs.

    Returns:
        A list of ``strands.tools.mcp.MCPClient`` instances, one per server in
        :func:`get_mcp_server_specs`.

    Raises:
        RuntimeError: If the ``strands`` / ``mcp`` packages are not installed.
    """
    try:
        from mcp import StdioServerParameters  # lazy import
        from strands.tools.mcp import MCPClient  # lazy import
    except Exception as exc:  # pragma: no cover - depends on optional dep
        raise RuntimeError(
            "The 'strands-agents' and 'mcp' packages are required to build MCP clients. "
            "Install them with 'pip install strands-agents mcp'."
        ) from exc

    clients = []
    for spec in get_mcp_server_specs():
        # Bind the spec values as defaults to avoid late-binding in the closure.
        def _factory(command=spec.command, args=spec.args, env=spec.env):
            if env:
                return StdioServerParameters(command=command, args=args, env=env)
            return StdioServerParameters(command=command, args=args)

        clients.append(MCPClient(_factory))

    return clients


def build_agent(mcp_clients: list | None = None, model=None):
    """Assemble and return the 「医析」 Strands Agent.

    ``strands`` is imported lazily here so importing this module does not require
    the SDK.

    Args:
        mcp_clients: Optional pre-built list of ``MCPClient`` instances. When
            omitted, :func:`build_mcp_clients` is used.
        model: Optional pre-built Bedrock model. When omitted,
            :func:`build_bedrock_model` is used.

    Returns:
        A configured ``strands.Agent`` with the Bedrock model, all 8 MCP tool
        clients, and the medical-analysis system prompt.

    Raises:
        RuntimeError: If the ``strands`` / ``mcp`` packages are not installed.
    """
    try:
        from strands import Agent  # lazy import
    except Exception as exc:  # pragma: no cover - depends on optional dep
        raise RuntimeError(
            "The 'strands-agents' package is required to build the Agent. "
            "Install it with 'pip install strands-agents'."
        ) from exc

    resolved_model = model if model is not None else build_bedrock_model()
    resolved_clients = mcp_clients if mcp_clients is not None else build_mcp_clients()

    return Agent(
        model=resolved_model,
        tools=list(resolved_clients),
        system_prompt=SYSTEM_PROMPT,
    )
