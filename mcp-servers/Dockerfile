# MCP Servers image — bundles the 3 self-developed MCP servers plus the
# open-source servers the Agent orchestrates over stdio.
#
# Built and pushed to ECR automatically by CDK (ComputeStack uses
# ecs.ContainerImage.from_asset on this directory).
#
# The backend Agent launches the self-developed servers as stdio modules
# (see app/agent/agent.py / config.py):
#     python -m mcp_servers.chart_generation
#     python -m mcp_servers.report_generation
#     python -m mcp_servers.cnki_search
# To support that import path, the three packages are installed under a
# top-level `mcp_servers` package directory.
#
# Open-source servers are also installed here so the same image can host them:
#     pubmed-mcp-server, markitdown[all], pandas-mcp, awslabs-s3-mcp-server
#     (postgres-mcp-server is launched via `npx`, hence Node.js is installed).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# System dependencies:
# - WeasyPrint (report-generation) needs Pango/Cairo/GDK-Pixbuf + libffi.
# - Node.js + npx is required to launch the open-source postgres-mcp-server.
# - curl for diagnostics / health probing.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        nodejs \
        npm \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        libffi-dev \
        shared-mime-info \
        fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- Self-developed MCP servers -------------------------------------------
# Assemble a top-level `mcp_servers` package so the modules can be launched as
# `python -m mcp_servers.<server>` (matching the backend Agent launch args in
# app/agent/config.py). Each server package is copied under mcp_servers/.
#
# NOTE: chart-generation currently ships only a stub `__init__.py` (no server
# implementation / __main__). It is copied for completeness, but
# `python -m mcp_servers.chart_generation` will not start a server until the
# chart-generation MCP is implemented. report_generation and cnki_search are
# complete (each provides a __main__.py).
COPY report-generation/report_generation /app/mcp_servers/report_generation
COPY cnki-search/cnki_search /app/mcp_servers/cnki_search
COPY chart-generation /app/mcp_servers/chart_generation

RUN touch /app/mcp_servers/__init__.py

# Install the self-developed servers' Python dependencies.
RUN pip install --upgrade pip \
    && pip install \
        "mcp>=1.0.0" \
        "jinja2>=3.1.4" \
        "weasyprint>=63.0" \
        "python-docx>=1.1.2" \
        "boto3==1.35.81" \
        "httpx>=0.27.0" \
        "beautifulsoup4>=4.12.0" \
        "lxml>=5.0.0"

# --- Open-source MCP servers ----------------------------------------------
# Installed so the same image can host them when the Agent launches them.
# postgres-mcp-server is fetched on demand via `npx -y @modelcontextprotocol/server-postgres`.
RUN pip install \
        "pubmed-mcp-server>=0.1.0" \
        "markitdown[all]>=0.0.1" \
        "pandas-mcp>=0.1.0" \
        "awslabs-s3-mcp-server>=0.1.0" \
    || echo "WARNING: one or more open-source MCP servers failed to install; verify package availability"

ENV PYTHONPATH=/app

RUN useradd --create-home --uid 10001 mcpuser
USER mcpuser

EXPOSE 9000

# Default command runs the report-generation server over stdio. In ECS the
# specific server is selected by overriding the container command, or the
# backend Agent spawns each server as a stdio subprocess on demand.
CMD ["python", "-m", "mcp_servers.report_generation"]
