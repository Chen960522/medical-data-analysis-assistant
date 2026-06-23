"""Alembic environment configuration."""

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Add the backend directory to sys.path so models can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Allow overriding sqlalchemy.url via APP_DATABASE_URL or individual APP_DB_* vars
import os  # noqa: E402
from urllib.parse import quote_plus  # noqa: E402

_db_url = os.environ.get("APP_DATABASE_URL")
if not _db_url and os.environ.get("APP_DB_HOST"):
    _user = quote_plus(os.environ.get("APP_DB_USER", "postgres"))
    _password = quote_plus(os.environ.get("APP_DB_PASSWORD", ""))
    _host = os.environ["APP_DB_HOST"]
    _port = os.environ.get("APP_DB_PORT", "5432")
    _name = os.environ.get("APP_DB_NAME", "medical_analysis")
    _db_url = f"postgresql://{_user}:{_password}@{_host}:{_port}/{_name}"
if _db_url:
    config.set_main_option("sqlalchemy.url", _db_url.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
