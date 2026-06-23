# Backend API image — FastAPI served by uvicorn on port 8000.
#
# Built and pushed to ECR automatically by CDK (ComputeStack uses
# ecs.ContainerImage.from_asset on this directory). The ECS container health
# check runs `curl -f http://localhost:8000/health`, so curl is installed.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# curl: ECS health check. System libs: WeasyPrint (report-generation MCP).
# Node.js + npm: postgres-mcp-server launched via npx.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl nodejs npm \
        libpango-1.0-0 libpangocairo-1.0-0 libcairo2 \
        libgdk-pixbuf-2.0-0 libffi-dev shared-mime-info fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Self-developed MCP servers (stdio subprocesses launched by the Agent).
COPY mcp-servers/report-generation/report_generation ./mcp_servers/report_generation
COPY mcp-servers/cnki-search/cnki_search ./mcp_servers/cnki_search
COPY mcp-servers/chart-generation ./mcp_servers/chart_generation
RUN touch ./mcp_servers/__init__.py

COPY backend/pyproject.toml ./
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini

RUN pip install --upgrade pip && pip install . && \
    pip install --upgrade "strands-agents>=1.44.0" "mcp>=1.12.0" && \
    pip install "pubmed-mcp-server>=0.1.0" \
    || echo "WARNING: pubmed-mcp-server install failed (non-critical)"

# Run as a non-root user.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

# Production server. Configuration is supplied via APP_*-prefixed environment
# variables / ECS task secrets (see docs/DEPLOYMENT.md section 4).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
