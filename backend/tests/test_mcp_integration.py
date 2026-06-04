"""Tests for the open-source MCP Server integration & verification helpers.

These cover the dependency-free surface added in task 15.2: the open-source
server subset, the documented expected-tools mapping, the S3 credential/endpoint
environment wiring, and the lazy-import guard on the verification helpers. They
are designed to pass WITHOUT the ``strands`` / ``mcp`` SDKs installed.

This file intentionally does NOT duplicate the spec/command assertions already
covered by ``test_agent_config.py`` — it focuses on the open-source integration
layer (:mod:`app.agent.mcp_integration`) and the S3 env additions.

Requirements: 3.1-3.5, 10.9-10.21, 11.10-11.15
"""

import importlib.util

import pytest

from app.agent import (
    EXPECTED_TOOLS_BY_SERVER,
    OPEN_SOURCE_SERVER_NAMES,
    OPEN_SOURCE_SERVER_REPOS,
    get_expected_tools,
    get_mcp_server_specs,
    list_open_source_server_specs,
    verify_all_open_source_servers,
    verify_mcp_server_tools,
)

_STRANDS_AVAILABLE = (
    importlib.util.find_spec("strands") is not None and importlib.util.find_spec("mcp") is not None
)

_EXPECTED_OPEN_SOURCE = ("pubmed", "markitdown", "pandas", "s3", "postgres")


# --- Open-source server subset ------------------------------------------


class TestOpenSourceServerSpecs:
    def test_lists_exactly_five_open_source_servers(self):
        specs = list_open_source_server_specs()
        assert len(specs) == 5

    def test_names_match_expected_open_source_set(self):
        names = tuple(spec.name for spec in list_open_source_server_specs())
        assert names == OPEN_SOURCE_SERVER_NAMES == _EXPECTED_OPEN_SOURCE

    def test_excludes_self_developed_servers(self):
        names = {spec.name for spec in list_open_source_server_specs()}
        for self_developed in ("chart_generation", "report_generation", "cnki_search"):
            assert self_developed not in names

    def test_specs_are_the_same_objects_as_full_specs(self):
        # The open-source subset must reuse the canonical specs from agent.py,
        # not re-derive them, so command/args stay in sync.
        full = {spec.name: spec for spec in get_mcp_server_specs()}
        for spec in list_open_source_server_specs():
            assert spec == full[spec.name]

    def test_every_open_source_server_has_a_source_repo(self):
        for name in OPEN_SOURCE_SERVER_NAMES:
            assert OPEN_SOURCE_SERVER_REPOS[name].startswith("https://")


# --- Documented expected tools ------------------------------------------


class TestExpectedTools:
    def test_mapping_covers_all_five_servers(self):
        assert set(EXPECTED_TOOLS_BY_SERVER) == set(OPEN_SOURCE_SERVER_NAMES)

    def test_every_server_lists_at_least_one_tool(self):
        for name in OPEN_SOURCE_SERVER_NAMES:
            assert len(EXPECTED_TOOLS_BY_SERVER[name]) >= 1

    def test_documented_tools_match_design(self):
        assert EXPECTED_TOOLS_BY_SERVER["pubmed"] == ("search", "get_article_details", "search_by_mesh")
        assert EXPECTED_TOOLS_BY_SERVER["markitdown"] == ("convert",)
        assert EXPECTED_TOOLS_BY_SERVER["pandas"] == ("analyze_data", "describe", "query")
        assert EXPECTED_TOOLS_BY_SERVER["s3"] == ("GetObject", "PutObject", "ListObjects")
        assert EXPECTED_TOOLS_BY_SERVER["postgres"] == ("query",)

    def test_get_expected_tools_helper(self):
        assert get_expected_tools("pandas") == ("analyze_data", "describe", "query")

    def test_get_expected_tools_unknown_server_returns_empty(self):
        assert get_expected_tools("does-not-exist") == ()


# --- S3 credential / endpoint env wiring --------------------------------


class TestS3Environment:
    def _s3_env(self) -> dict:
        by_name = {spec.name: spec for spec in get_mcp_server_specs()}
        return by_name["s3"].env

    def test_aws_region_preserved(self):
        # Must remain the bedrock region (us-west-2) — see test_agent_config.py.
        assert self._s3_env().get("AWS_REGION") == "us-west-2"

    def test_endpoint_url_included_when_configured(self):
        # The default settings configure a LocalStack endpoint, which should be
        # forwarded to the S3 MCP server so dev runs hit the local stack.
        env = self._s3_env()
        assert env.get("AWS_ENDPOINT_URL") == "http://localhost:4566"
        assert env.get("AWS_ENDPOINT_URL_S3") == "http://localhost:4566"

    def test_bucket_name_forwarded(self):
        assert self._s3_env().get("S3_BUCKET_NAME") == "medical-data-files"

    def test_endpoint_keys_absent_when_not_configured(self, monkeypatch):
        # When no endpoint is configured, only AWS_REGION (+ bucket) should be set.
        from app.agent import agent as agent_module

        monkeypatch.setattr(agent_module.settings, "s3_endpoint_url", "", raising=False)
        env = agent_module._build_s3_env()
        assert env.get("AWS_REGION") == "us-west-2"
        assert "AWS_ENDPOINT_URL" not in env
        assert "AWS_ENDPOINT_URL_S3" not in env


# --- Verification helpers (SDK-dependent) -------------------------------


class TestVerificationHelpers:
    @pytest.mark.skipif(_STRANDS_AVAILABLE, reason="strands/mcp installed; helper builds a client")
    def test_verify_single_server_raises_without_sdk(self):
        spec = list_open_source_server_specs()[0]
        with pytest.raises(RuntimeError, match="strands-agents"):
            verify_mcp_server_tools(spec)

    @pytest.mark.skipif(_STRANDS_AVAILABLE, reason="strands/mcp installed; helper builds a client")
    def test_verify_all_raises_without_sdk(self):
        with pytest.raises(RuntimeError, match="strands-agents"):
            verify_all_open_source_servers()
