"""Open-source MCP Server integration & verification for the 「医析」 Agent.

This module documents and verifies the integration of the **five open-source**
MCP servers the Agent orchestrates over stdio. The launch *specifications*
themselves live in :mod:`app.agent.agent` (:func:`get_mcp_server_specs`); this
module narrows them to the open-source subset, records the tools each server is
expected to expose (per design.md), and provides connectivity-verification
helpers the Agent (or an operator) can run to confirm every server starts and
advertises its tools.

Open-source MCP servers (install + launch summary, per design.md):

==================  =======================================  ==========================
Server (name)        Install                                  Launch (stdio)
==================  =======================================  ==========================
pubmed               ``pip install pubmed-mcp-server``        ``python -m pubmed_mcp_server``
markitdown           ``pip install markitdown[all]``          ``python -m markitdown.mcp_server``
pandas               ``pip install pandas-mcp``               ``python -m pandas_mcp``
s3                   ``pip install awslabs-s3-mcp-server``    ``python -m awslabs.s3_mcp_server`` (AWS_REGION + endpoint)
postgres             (none — runs via ``npx``)                ``npx -y @modelcontextprotocol/server-postgres <conn>``
==================  =======================================  ==========================

Source repositories (design.md → "MCP Server 选型"):
    * pubmed      : https://github.com/JackKuo666/pubmed-mcp-server
    * markitdown  : https://github.com/microsoft/markitdown
    * pandas      : https://github.com/QuantGeekDev/pandas-mcp
    * s3          : https://github.com/awslabs/mcp
    * postgres    : https://github.com/modelcontextprotocol/servers

All ``strands`` / ``mcp`` imports are deferred to the verification functions so
importing this module never requires the heavy SDKs (matching the lazy-import
pattern in :func:`app.agent.agent.build_mcp_clients`).

Requirements: 3.1-3.5, 10.9-10.21, 11.10-11.15
"""

from __future__ import annotations

from .agent import MCPServerSpec, get_mcp_server_specs

# Logical names of the five open-source MCP servers (a subset of the eight
# servers in :data:`app.agent.agent.MCP_SERVER_NAMES`). Ordered to match the
# design document's "开源复用 MCP Servers" listing.
OPEN_SOURCE_SERVER_NAMES: tuple[str, ...] = (
    "pubmed",
    "markitdown",
    "pandas",
    "s3",
    "postgres",
)

# Source repositories for each open-source server (for documentation/traceability).
OPEN_SOURCE_SERVER_REPOS: dict[str, str] = {
    "pubmed": "https://github.com/JackKuo666/pubmed-mcp-server",
    "markitdown": "https://github.com/microsoft/markitdown",
    "pandas": "https://github.com/QuantGeekDev/pandas-mcp",
    "s3": "https://github.com/awslabs/mcp",
    "postgres": "https://github.com/modelcontextprotocol/servers",
}

# The tools each open-source server is expected to expose (per design.md). Used
# both for documentation and to give the verification step a reference set to
# compare the live tool list against.
EXPECTED_TOOLS_BY_SERVER: dict[str, tuple[str, ...]] = {
    # PubMed literature search (Requirements 10.9-10.21).
    "pubmed": ("search", "get_article_details", "search_by_mesh"),
    # MarkItDown PDF/document → Markdown (Requirements 11.10-11.15).
    "markitdown": ("convert",),
    # pandas-mcp data analysis (Requirements 3.1-3.5).
    "pandas": ("analyze_data", "describe", "query"),
    # aws-s3-mcp-server file operations.
    "s3": ("GetObject", "PutObject", "ListObjects"),
    # postgres-mcp-server read-only SQL.
    "postgres": ("query",),
}


def list_open_source_server_specs() -> list[MCPServerSpec]:
    """Return the launch specs for the five open-source MCP servers.

    Filters :func:`app.agent.agent.get_mcp_server_specs` down to the open-source
    subset (excluding the three self-developed servers), preserving the order in
    :data:`OPEN_SOURCE_SERVER_NAMES`. This is a pure function — no
    ``strands``/``mcp`` import is required to call it.

    Returns:
        A list of :class:`app.agent.agent.MCPServerSpec`, one per open-source
        server.
    """
    by_name = {spec.name: spec for spec in get_mcp_server_specs()}
    return [by_name[name] for name in OPEN_SOURCE_SERVER_NAMES if name in by_name]


def get_expected_tools(server_name: str) -> tuple[str, ...]:
    """Return the documented expected tool names for an open-source server.

    Args:
        server_name: One of :data:`OPEN_SOURCE_SERVER_NAMES`.

    Returns:
        The tuple of expected tool names (empty if the server is unknown).
    """
    return EXPECTED_TOOLS_BY_SERVER.get(server_name, ())


def _build_stdio_client(spec: MCPServerSpec):
    """Build a single ``MCPClient`` for ``spec`` over stdio.

    ``strands`` / ``mcp`` are imported lazily so importing this module does not
    require the SDKs.

    Args:
        spec: The launch specification to wrap.

    Returns:
        A ``strands.tools.mcp.MCPClient`` configured from ``spec``.

    Raises:
        RuntimeError: If the ``strands`` / ``mcp`` packages are not installed.
    """
    try:
        from mcp import StdioServerParameters  # lazy import
        from strands.tools.mcp import MCPClient  # lazy import
    except Exception as exc:  # pragma: no cover - depends on optional dep
        raise RuntimeError(
            "The 'strands-agents' and 'mcp' packages are required to verify MCP "
            "servers. Install them with 'pip install strands-agents mcp'."
        ) from exc

    def _factory(command=spec.command, args=spec.args, env=spec.env):
        if env:
            return StdioServerParameters(command=command, args=args, env=env)
        return StdioServerParameters(command=command, args=args)

    return MCPClient(_factory)


def _tool_name(tool: object) -> str:
    """Best-effort extraction of a tool's name from an MCP tool object.

    Strands exposes listed tools with a ``tool_name`` attribute; the underlying
    MCP tool spec uses ``name``. Falls back to ``str`` so verification never
    crashes on an unexpected shape.
    """
    for attr in ("tool_name", "name"):
        value = getattr(tool, attr, None)
        if isinstance(value, str) and value:
            return value
    return str(tool)


def verify_mcp_server_tools(spec: MCPServerSpec) -> list[str]:
    """Start one MCP server over stdio and return the names of its tools.

    Opens the ``MCPClient`` session, lists the advertised tools, and returns
    their names. ``strands`` / ``mcp`` are imported lazily inside
    :func:`_build_stdio_client`.

    Args:
        spec: The launch specification of the server to verify.

    Returns:
        The list of tool names advertised by the server.

    Raises:
        RuntimeError: If the ``strands`` / ``mcp`` packages are not installed.
    """
    client = _build_stdio_client(spec)
    with client:
        tools = client.list_tools_sync()
    return [_tool_name(tool) for tool in tools]


def verify_all_open_source_servers() -> dict[str, list[str] | str]:
    """Verify connectivity & tool listing for every open-source MCP server.

    Iterates over :func:`list_open_source_server_specs`, starting each server
    and listing its tools. Servers that start and respond contribute a
    ``name -> [tool names]`` entry; servers that fail to start contribute a
    ``name -> "error: <message>"`` entry so a single broken server does not abort
    verification of the rest.

    ``strands`` / ``mcp`` are imported lazily; if the SDKs are entirely missing,
    the first server verification raises ``RuntimeError`` (callers that want a
    soft result should ensure the SDKs are installed first).

    Returns:
        A mapping of open-source server name → list of tool names (on success)
        or an ``"error: ..."`` string (on failure).

    Raises:
        RuntimeError: If the ``strands`` / ``mcp`` packages are not installed.
    """
    results: dict[str, list[str] | str] = {}
    for spec in list_open_source_server_specs():
        try:
            results[spec.name] = verify_mcp_server_tools(spec)
        except RuntimeError:
            # SDKs missing entirely — propagate so the caller gets a clear signal.
            raise
        except Exception as exc:  # pragma: no cover - depends on live servers
            results[spec.name] = f"error: {exc}"
    return results
