"""
Database connection layer.

This module is the single source of truth for SQLAlchemy engine and
session management. It is responsible ONLY for:

    - Creating the SQLAlchemy Engine (singleton, one per process)
    - Creating the Session factory (SessionLocal)
    - Providing the declarative Base for ORM models
    - Providing the `get_db()` FastAPI dependency
    - Providing a connectivity health-check helper

No models, repositories, or business logic belong here.

Supabase / SSL:
    Supabase's managed PostgreSQL requires SSL for all external
    connections — the database is not reachable over a plaintext
    TCP connection from outside Supabase's own network. Without SSL,
    connection attempts fail outright (or, if a network permitted
    plaintext, would expose credentials and data in transit). SSL is
    enforced here via `connect_args={"sslmode": "require"}` passed to
    `create_engine()`, rather than embedding `sslmode` in the URL
    itself — this keeps the connection string DB-agnostic (works
    whether `DATABASE_URL` was supplied directly or assembled from
    discrete `SUPABASE_DB_*` fields) and keeps the SSL requirement
    explicit and auditable in one place.
"""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings
from app.utils.logger import get_logger

log = get_logger(__name__)


# ----------------------------------------------------------------------
# Engine
# ----------------------------------------------------------------------
# The Engine owns the connection pool. It is created exactly once at
# module import time and reused for the lifetime of the process.
#
# `connect_args={"sslmode": "require"}` is passed through to psycopg2
# and instructs it to negotiate an SSL/TLS connection with the server.
# Supabase rejects non-SSL connections, so this is not optional for
# Supabase-hosted databases; it is also good practice for any
# PostgreSQL instance reachable over a public network, since it
# protects credentials and query data in transit.
engine: Engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URL_SYNC,
    connect_args={"sslmode": "require"},  # Supabase requires SSL — see module docstring
    pool_pre_ping=True,      # validates a connection is alive before use,
                              # preventing "stale connection" errors after
                              # DB restarts, network blips, or Supabase's
                              # own connection idle timeouts
    pool_size=5,              # baseline number of persistent connections;
                              # kept conservative since Supabase's free/
                              # pro tiers cap total concurrent connections
    max_overflow=10,          # additional connections allowed under load,
                              # beyond pool_size, before requests block
    pool_recycle=1800,        # recycle connections after 30 minutes to
                              # avoid connections being dropped by
                              # Supabase's connection pooler (PgBouncer)
                              # or an intermediate network timeout
    future=True,               # SQLAlchemy 2.x style engine
)


# ----------------------------------------------------------------------
# Session factory
# ----------------------------------------------------------------------
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,  # allow ORM objects to remain usable after
                              # commit, without triggering an implicit
                              # re-SELECT on next attribute access
    class_=Session,
)


# ----------------------------------------------------------------------
# Declarative base
# ----------------------------------------------------------------------
class Base(DeclarativeBase):
    """
    Declarative base class for all ORM models.

    All future model classes (Phase: Database Models) will inherit
    from this `Base`.
    """


# ----------------------------------------------------------------------
# FastAPI dependency
# ----------------------------------------------------------------------
def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session per request.

    Uses the generator pattern so FastAPI runs the code before `yield`
    on request entry, and the code after `yield` on request exit
    (including when an exception propagates out of the endpoint),
    guaranteeing the session is always closed.

    Yields:
        Session: A SQLAlchemy ORM session bound to the shared Engine.

    Raises:
        SQLAlchemyError: Re-raised after rollback if a database error
            occurs while the session is in use by the caller.
    """
    db = SessionLocal()
    log.debug("Session created")
    try:
        yield db
    except SQLAlchemyError:
        log.exception("Database session error — rolling back transaction")
        db.rollback()
        raise
    finally:
        db.close()
        log.debug("Session closed")


# ----------------------------------------------------------------------
# Connectivity health check
# ----------------------------------------------------------------------
@contextmanager
def _short_lived_session() -> Generator[Session, None, None]:
    """
    Internal helper that opens and guarantees closure of a short-lived
    session, used only by `check_database_connection()`.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> bool:
    """
    Verifies database connectivity by executing `SELECT 1`, and logs
    the connected PostgreSQL server version on success.

    Intended for use in startup checks, health endpoints, and
    readiness probes. This function NEVER terminates the application
    (no `sys.exit`, no `raise SystemExit`) — connectivity failure is
    reported via a logged error and a `False` return value, leaving
    the decision of how to react (fail startup, degrade readiness,
    retry) entirely to the caller.

    Returns:
        bool: True if the database is reachable and responsive,
            False otherwise.

    Raises:
        This function does not raise; all `SQLAlchemyError` subclasses
        encountered while connecting or querying are caught internally.
    """
    try:
        with _short_lived_session() as db:
            db.execute(text("SELECT 1"))
            server_version = db.execute(text("SHOW server_version")).scalar_one()

        log.info("Database Connected")
        log.info("Database server version: {}", server_version)
        return True

    except OperationalError as exc:
        # Most common failure mode against Supabase: wrong host/port,
        # network/firewall issues, SSL negotiation failure, or the
        # project being paused (Supabase free-tier auto-pause).
        log.error("Connection Failed | reason=operational_error | detail={}", str(exc))
        return False

    except SQLAlchemyError as exc:
        log.error("Connection Failed | reason=sqlalchemy_error | detail={}", str(exc))
        return False


__all__ = [
    "engine",
    "SessionLocal",
    "Base",
    "get_db",
    "check_database_connection",
]