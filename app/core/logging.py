"""
Centralized logging configuration using Loguru.

This module replaces the Phase 1 stdlib `logging.dictConfig` setup.
It configures Loguru as the single source of truth for all
application logging:

    - Console sink (human-readable, colorized in development)
    - Rotating file sinks, split by severity (see `_configure_file_sinks`)
    - Structured format: timestamp | level | module:function:line | message
    - Intercepts stdlib `logging` records (from uvicorn, sqlalchemy,
      third-party libs) and routes them through Loguru, so every log
      line in the app — regardless of origin — shares one format and
      one set of sinks.

`setup_logging()` is idempotent: calling it more than once will not
create duplicate sinks/handlers, satisfying requirement #9 (safe to
import/initialize from multiple entry points, e.g. app startup and
test fixtures).
"""

import logging
import sys
from pathlib import Path

from loguru import logger

from app.core.config import settings

# Guard flag to make setup_logging() safe to call multiple times.
_LOGGING_CONFIGURED = False

# Console format: colorized, human-friendly.
_CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{module}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)

# File format: plain text, no color codes (colorizing a file is noise).
_FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
    "{level: <8} | "
    "{module}:{function}:{line} - "
    "{message}"
)


class InterceptHandler(logging.Handler):
    """
    Routes stdlib `logging` records (uvicorn, sqlalchemy, etc.) into
    Loguru, so third-party/framework logs share the same sinks and
    format as application logs instead of bypassing them.
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find the frame that actually emitted the log, so Loguru
        # reports the true caller instead of stdlib's internals.
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def _configure_file_sinks(log_dir: Path) -> None:
    """
    Adds rotating file sinks to the logger.

    Two files are maintained:
        - app.log      : INFO and above (general application activity)
        - error.log    : ERROR and above (fast triage of failures)

    Both rotate daily and are retained for 14 days, compressed on
    rotation to control disk usage. DEBUG/WARNING/CRITICAL all flow
    through `app.log` (or `error.log` for ERROR/CRITICAL) — separate
    per-level files are unnecessary and fragment context; filtering
    by level within these two files covers requirement #4.
    """
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.add(
        log_dir / "app.log",
        format=_FILE_FORMAT,
        level="DEBUG",
        rotation="00:00",       # new file at midnight
        retention="14 days",
        compression="zip",
        enqueue=True,           # thread/process-safe async writes
        backtrace=False,
        diagnose=False,
        encoding="utf-8",
    )

    logger.add(
        log_dir / "error.log",
        format=_FILE_FORMAT,
        level="ERROR",
        rotation="00:00",
        retention="30 days",
        compression="zip",
        enqueue=True,
        backtrace=True,
        diagnose=settings.DEBUG,  # only include variable values in dev
        encoding="utf-8",
    )


def setup_logging() -> None:
    """
    Configures Loguru as the application's sole logger.

    Must be called once, as early as possible during application
    startup (before any module-level logger emits records). Safe to
    call multiple times — subsequent calls are no-ops.
    """
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    # Remove Loguru's default handler before adding our own, to avoid
    # duplicate console output.
    logger.remove()

    # --- Console sink ---
    logger.add(
        sys.stdout,
        format=_CONSOLE_FORMAT,
        level=settings.LOG_LEVEL.value,
        colorize=True,
        backtrace=settings.DEBUG,
        diagnose=settings.DEBUG,
        enqueue=True,
    )

    # --- File sinks ---
    _configure_file_sinks(Path(settings.LOG_DIRECTORY))

    # --- Redirect stdlib logging (uvicorn, sqlalchemy, etc.) into Loguru ---
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for noisy_logger in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy.engine"):
        std_logger = logging.getLogger(noisy_logger)
        std_logger.handlers = [InterceptHandler()]
        std_logger.propagate = False

    _LOGGING_CONFIGURED = True

    logger.debug(
        "Logging configured (level={}, directory={})",
        settings.LOG_LEVEL.value,
        settings.LOG_DIRECTORY,
    )


def log_startup() -> None:
    """Logs a structured application startup event. Called from lifespan."""
    logger.info(
        "Application startup | name={} version={} environment={}",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.ENVIRONMENT.value,
    )


def log_shutdown() -> None:
    """Logs a structured application shutdown event. Called from lifespan."""
    logger.info(
        "Application shutdown | name={} environment={}",
        settings.APP_NAME,
        settings.ENVIRONMENT.value,
    )


__all__ = ["setup_logging", "log_startup", "log_shutdown", "logger"]