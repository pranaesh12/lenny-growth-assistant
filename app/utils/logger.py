"""
Logging helper functions.

Provides a small, consistent API for the rest of the codebase to log
through, rather than every module calling `loguru.logger` directly
with ad-hoc field names. Keeping this thin wrapper in one place means
structured field conventions (e.g. `request_id=`, `duration_ms=`) stay
consistent as the project grows across later phases (services,
repositories, LLM calls, etc.).

Usage:
    from app.utils.logger import get_logger

    log = get_logger(__name__)
    log.info("Something happened")
    log.bind(request_id="abc-123").warning("Something odd happened")
"""

from loguru import logger as _logger


def get_logger(name: str | None = None):
    """
    Returns a Loguru logger instance, optionally bound with a `name`
    field identifying the calling module.

    Loguru's `logger` is a single global object (not a per-module
    instance like stdlib `logging.getLogger`), so `bind()` is used
    here to attach contextual metadata instead of creating a new
    logger — this is the idiomatic Loguru pattern and avoids any risk
    of duplicate sink registration (requirement #9).

    Args:
        name: Typically `__name__` of the calling module.

    Returns:
        A Loguru logger bound with the `name` field, ready to use.
    """
    return _logger.bind(name=name) if name else _logger


def log_exception(message: str, **context: object) -> None:
    """
    Logs the currently-handled exception with full traceback, plus any
    additional structured context fields.

    Intended for use inside `except` blocks:

        try:
            ...
        except Exception:
            log_exception("Failed to process request", request_id=request_id)
    """
    _logger.bind(**context).opt(exception=True).error(message)


def log_with_context(level: str, message: str, **context: object) -> None:
    """
    Logs a message at the given level with arbitrary structured
    context fields bound to it.

    Example:
        log_with_context("info", "User action processed", user_id=42, action="signup")
    """
    _logger.bind(**context).log(level.upper(), message)


__all__ = ["get_logger", "log_exception", "log_with_context"]