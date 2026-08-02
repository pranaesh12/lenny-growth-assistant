"""
Alembic environment configuration.

This module is executed by every Alembic CLI command (`revision`,
`upgrade`, `downgrade`, `current`, `history`, etc.). It is
responsible for:

    - Wiring Alembic to this project's SQLAlchemy `Base.metadata`
      (so future `--autogenerate` runs can detect model changes)
    - Sourcing the database connection URL exclusively from
      `app.core.config.get_settings()` — never hardcoded here
    - Supporting both "offline" migrations (generate SQL without a
      live DB connection) and "online" migrations (execute directly
      against the database)
    - Configuring SQLAlchemy 2.0-style autogenerate comparison
      behavior (`compare_type`, `compare_server_default`)
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# --------------------------------------------------------------------
# Project imports
# --------------------------------------------------------------------
# Importing `app.models` (rather than only `app.db.database.Base`) is
# required for autogenerate to work correctly. `Base` on its own is
# just an empty registry — each model's table only gets registered
# onto `Base.metadata` when that model's module is actually imported
# and its class body executes. `app/models/__init__.py` already
# imports every model (Session, Message, Artifact, Transcript,
# Configuration), so importing the package here is sufficient to
# fully populate `Base.metadata` before Alembic inspects it. There is
# no need to import individual model modules directly in this file —
# doing so would duplicate what `app/models/__init__.py` already does
# and add maintenance burden every time a new model is added.
import app.models  # noqa: F401 — imported for its side effect of registering models on Base.metadata
from app.db.database import Base

# `get_settings()` is the project's single source of truth for
# configuration. The database URL must always come from here — never
# hardcoded in this file or in alembic.ini — so migrations always run
# against the same database the application itself connects to.
from app.core.config import get_settings

# --------------------------------------------------------------------
# Alembic Config object
# --------------------------------------------------------------------
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --------------------------------------------------------------------
# Inject the real database URL from application Settings
# --------------------------------------------------------------------
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.SQLALCHEMY_DATABASE_URL_SYNC)

# --------------------------------------------------------------------
# Target metadata for autogenerate support
# --------------------------------------------------------------------
# By the time this line executes, `import app.models` above has
# already triggered import of every model module, so `Base.metadata`
# now contains all five tables: sessions, messages, artifacts,
# transcripts, configurations.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    Configures the context with just a URL and not an Engine, so no
    actual DBAPI connection is required. Useful for generating a raw
    SQL script to be reviewed or applied manually.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    Creates a live Engine and establishes a real DBAPI connection
    against the database (Supabase PostgreSQL, via the pooler, over
    SSL — same connection path as the application itself).
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args={"sslmode": "require"},
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


# --------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()