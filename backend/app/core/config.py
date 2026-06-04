"""Application configuration using pydantic-settings."""

from urllib.parse import quote_plus

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/medical_assistant"

    # Optional individual database components. When ``db_host`` is provided
    # (e.g. injected from the ECS task environment + Secrets Manager in
    # production), ``database_url`` is assembled from these parts. This keeps the
    # password out of any single plaintext variable: in ECS the password is
    # injected as ``APP_DB_PASSWORD`` from Secrets Manager while host/port/name/
    # user come from plain environment variables.
    db_host: str = ""
    db_port: int = 5432
    db_name: str = ""
    db_user: str = ""
    db_password: str = ""

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_secret_key: str = "change-me-in-production-use-a-strong-random-secret"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_hours: int = 24

    # Security
    bcrypt_cost_factor: int = 12
    max_login_attempts: int = 5
    account_lockout_minutes: int = 15

    # Email (placeholder for future implementation)
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "noreply@medical-assistant.com"

    # S3
    s3_bucket_name: str = "medical-data-files"
    s3_endpoint_url: str = "http://localhost:4566"
    aws_region: str = "us-east-1"
    s3_max_file_size: int = 104857600  # 100MB

    # Application
    app_name: str = "Medical Data Analysis Assistant"
    app_base_url: str = "http://localhost:8000"

    # AI Agent / Bedrock model
    bedrock_model_id: str = "anthropic.claude-sonnet-4-20250514-v1:0"
    bedrock_region: str = "us-west-2"
    agent_temperature: float = 0.3
    agent_max_tokens: int = 4096

    # Bedrock AgentCore Runtime
    # ARN of the deployed AgentCore Runtime (set per environment; empty by default
    # so local/test runs do not require a real ARN). Example:
    #   arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/medical-analysis
    agentcore_runtime_arn: str = ""
    agentcore_region: str = "us-west-2"
    # Optional runtime version/alias qualifier (e.g. "DEFAULT" or a version id).
    agentcore_qualifier: str = ""

    # MCP server launch commands (open-source servers)
    mcp_pubmed_command: str = "python"
    mcp_pubmed_args: str = "-m,pubmed_mcp_server"
    mcp_markitdown_command: str = "python"
    mcp_markitdown_args: str = "-m,markitdown.mcp_server"
    mcp_pandas_command: str = "python"
    mcp_pandas_args: str = "-m,pandas_mcp"
    mcp_s3_command: str = "python"
    mcp_s3_args: str = "-m,awslabs.s3_mcp_server"
    mcp_postgres_command: str = "npx"
    mcp_postgres_args: str = "-y,@modelcontextprotocol/server-postgres"

    # MCP server launch commands (self-developed servers)
    mcp_chart_command: str = "python"
    mcp_chart_args: str = "-m,mcp_servers.chart_generation"
    mcp_report_command: str = "python"
    mcp_report_args: str = "-m,mcp_servers.report_generation"
    mcp_cnki_command: str = "python"
    mcp_cnki_args: str = "-m,mcp_servers.cnki_search"

    model_config = {"env_prefix": "APP_", "env_file": ".env", "extra": "ignore"}

    @model_validator(mode="after")
    def _assemble_database_url(self) -> "Settings":
        """Assemble ``database_url`` from individual parts when ``db_host`` is set.

        In production the ECS task supplies ``APP_DB_HOST`` / ``APP_DB_PORT`` /
        ``APP_DB_NAME`` / ``APP_DB_USER`` as plain environment variables and
        ``APP_DB_PASSWORD`` from Secrets Manager. When ``db_host`` is provided we
        build the SQLAlchemy URL from these parts so the password never has to be
        embedded in a single plaintext ``APP_DATABASE_URL``. The password is
        URL-encoded to tolerate special characters. When ``db_host`` is empty
        (local/dev), the explicit ``database_url`` default is used unchanged.
        """
        if self.db_host:
            user = quote_plus(self.db_user or "postgres")
            password = quote_plus(self.db_password)
            self.database_url = (
                f"postgresql://{user}:{password}@{self.db_host}:{self.db_port}/{self.db_name}"
            )
        return self


settings = Settings()
