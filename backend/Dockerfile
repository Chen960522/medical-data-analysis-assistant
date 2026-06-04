# Backend API image — FastAPI served by uvicorn on port 8000.
#
# Built and pushed to ECR automatically by CDK (ComputeStack uses
# ecs.ContainerImage.from_asset on this directory). The ECS container health
# check runs `curl -f http://localhost:8000/health`, so curl is installed.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# curl is required by the ECS container health check (GET /health).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first for better layer caching. pyproject.toml uses the
# hatchling backend with packages = ["app"], so the app package must be present
# for the build install.
COPY pyproject.toml ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

RUN pip install --upgrade pip && pip install .

# Run as a non-root user.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

# Production server. Configuration is supplied via APP_*-prefixed environment
# variables / ECS task secrets (see docs/DEPLOYMENT.md section 4).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
