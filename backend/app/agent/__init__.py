"""Medical data analysis Agent package (「医析」).

Exposes the public factory functions and configuration for the Strands Agent.
All heavy ``strands`` / ``mcp`` imports are deferred to the factory functions,
so importing this package (and the prompt/config constants) is dependency-free.

Requirements: 3.1-3.8, 9.5-9.9
"""

from __future__ import annotations

from .agent import (
    EXPECTED_MCP_CLIENT_COUNT,
    MCP_SERVER_NAMES,
    MCPServerSpec,
    build_agent,
    build_mcp_clients,
    get_mcp_server_specs,
)
from .config import ModelParameters, build_bedrock_model, get_model_parameters
from .entrypoint import (
    create_agent_with_context,
    create_app,
    extract_analysis_results,
    extract_charts,
    extract_report,
    handle_invocation,
)
from .mcp_integration import (
    EXPECTED_TOOLS_BY_SERVER,
    OPEN_SOURCE_SERVER_NAMES,
    OPEN_SOURCE_SERVER_REPOS,
    get_expected_tools,
    list_open_source_server_specs,
    verify_all_open_source_servers,
    verify_mcp_server_tools,
)
from .prompts import SYSTEM_PROMPT

__all__ = [
    "SYSTEM_PROMPT",
    "ModelParameters",
    "build_bedrock_model",
    "get_model_parameters",
    "MCPServerSpec",
    "MCP_SERVER_NAMES",
    "EXPECTED_MCP_CLIENT_COUNT",
    "get_mcp_server_specs",
    "build_mcp_clients",
    "build_agent",
    "handle_invocation",
    "create_agent_with_context",
    "create_app",
    "extract_charts",
    "extract_analysis_results",
    "extract_report",
    "OPEN_SOURCE_SERVER_NAMES",
    "OPEN_SOURCE_SERVER_REPOS",
    "EXPECTED_TOOLS_BY_SERVER",
    "list_open_source_server_specs",
    "get_expected_tools",
    "verify_mcp_server_tools",
    "verify_all_open_source_servers",
]
