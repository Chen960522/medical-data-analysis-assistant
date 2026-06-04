"""Tests for the medical data analysis Agent configuration.

These tests cover the dependency-free surface of the Agent package: the system
prompt content, the Bedrock model parameter defaults, and the MCP server launch
specifications. They are designed to pass WITHOUT the ``strands`` / ``mcp`` SDKs
installed (heavy imports are deferred to the factory functions).

When the SDKs ARE installed, :func:`build_mcp_clients` is exercised to confirm
it registers exactly 8 clients; otherwise the factory is asserted to raise a
clear ``RuntimeError``.

Requirements: 3.1-3.8, 9.5-9.9
"""

import importlib.util

import pytest

from app.agent import (
    EXPECTED_MCP_CLIENT_COUNT,
    MCP_SERVER_NAMES,
    SYSTEM_PROMPT,
    build_mcp_clients,
    get_mcp_server_specs,
    get_model_parameters,
)

_STRANDS_AVAILABLE = (
    importlib.util.find_spec("strands") is not None and importlib.util.find_spec("mcp") is not None
)


# --- System prompt -------------------------------------------------------


class TestSystemPrompt:
    def test_is_non_empty_string(self):
        assert isinstance(SYSTEM_PROMPT, str)
        assert SYSTEM_PROMPT.strip()

    def test_contains_agent_role_marker(self):
        # The agent is named 「医析」 and is a medical data analysis assistant.
        assert "医析" in SYSTEM_PROMPT
        assert "医学数据分析助手" in SYSTEM_PROMPT

    def test_contains_security_constraints(self):
        # Security section: no raw patient data, no PII, scope to current user.
        assert "安全约束" in SYSTEM_PROMPT
        assert "不直接暴露原始患者数据" in SYSTEM_PROMPT
        assert "可识别个人身份的信息" in SYSTEM_PROMPT
        assert "限定在当前用户的数据范围内" in SYSTEM_PROMPT

    def test_mentions_tool_categories(self):
        # Core capabilities should reference the major tool categories.
        for marker in ("pandas-mcp", "图表生成", "文献检索", "PubMed", "CNKI", "MarkItDown", "报告生成"):
            assert marker in SYSTEM_PROMPT, f"missing tool marker: {marker}"

    def test_mentions_conversation_rules(self):
        # Requirements 9.5-9.9: clarify intent, explain limitations + alternatives.
        assert "对话规则" in SYSTEM_PROMPT
        assert "主动询问澄清" in SYSTEM_PROMPT
        assert "建议替代方案" in SYSTEM_PROMPT


# --- Model parameters ----------------------------------------------------


class TestModelParameters:
    def test_defaults_match_design(self):
        params = get_model_parameters()
        assert params.model_id == "anthropic.claude-sonnet-4-20250514-v1:0"
        assert params.region_name == "us-west-2"
        assert params.temperature == 0.3
        assert params.max_tokens == 4096


# --- MCP server specs (dependency-free) ----------------------------------


class TestMCPServerSpecs:
    def test_eight_servers_configured(self):
        specs = get_mcp_server_specs()
        assert len(specs) == EXPECTED_MCP_CLIENT_COUNT == 8

    def test_spec_names_match_expected(self):
        specs = get_mcp_server_specs()
        assert tuple(spec.name for spec in specs) == MCP_SERVER_NAMES

    def test_every_spec_has_command_and_args(self):
        for spec in get_mcp_server_specs():
            assert spec.command, f"{spec.name} missing command"
            assert spec.args, f"{spec.name} missing args"

    def test_self_developed_module_invocations(self):
        by_name = {spec.name: spec for spec in get_mcp_server_specs()}
        assert by_name["chart_generation"].args == ["-m", "mcp_servers.chart_generation"]
        assert by_name["report_generation"].args == ["-m", "mcp_servers.report_generation"]
        assert by_name["cnki_search"].args == ["-m", "mcp_servers.cnki_search"]

    def test_open_source_module_invocations(self):
        by_name = {spec.name: spec for spec in get_mcp_server_specs()}
        assert by_name["pubmed"].args == ["-m", "pubmed_mcp_server"]
        assert by_name["markitdown"].args == ["-m", "markitdown.mcp_server"]
        assert by_name["pandas"].args == ["-m", "pandas_mcp"]
        assert by_name["s3"].args == ["-m", "awslabs.s3_mcp_server"]
        assert by_name["s3"].env.get("AWS_REGION") == "us-west-2"

    def test_postgres_spec_uses_npx_with_connection_string(self):
        by_name = {spec.name: spec for spec in get_mcp_server_specs()}
        postgres = by_name["postgres"]
        assert postgres.command == "npx"
        assert postgres.args[:2] == ["-y", "@modelcontextprotocol/server-postgres"]
        # The DB connection string is appended as the final argument.
        assert postgres.args[-1].startswith("postgresql://")


# --- MCP client factory --------------------------------------------------


class TestBuildMCPClients:
    @pytest.mark.skipif(not _STRANDS_AVAILABLE, reason="strands/mcp not installed")
    def test_builds_eight_clients_when_sdk_available(self):
        clients = build_mcp_clients()
        assert len(clients) == EXPECTED_MCP_CLIENT_COUNT == 8

    @pytest.mark.skipif(_STRANDS_AVAILABLE, reason="strands/mcp installed; factory succeeds")
    def test_raises_clear_error_without_sdk(self):
        with pytest.raises(RuntimeError, match="strands-agents"):
            build_mcp_clients()
