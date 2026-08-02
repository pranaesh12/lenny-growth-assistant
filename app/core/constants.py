"""
Application-wide constants.

Houses fixed, non-configurable values — things that are not expected
to change per-environment (unlike `Settings`, which is env-driven).
Keeping these separate from `config.py` avoids polluting environment
variables with values that are really just enums/labels internal to
the codebase.
"""

from enum import Enum


class Environment(str, Enum):
    """Supported application runtime environments."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class LLMProvider(str, Enum):
    """Supported LLM providers (wiring added in a later phase)."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"


class LogLevel(str, Enum):
    """Supported logging levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# --- Security-related constants ---
JWT_ALGORITHM = "HS256"
MIN_SECRET_KEY_LENGTH = 32  # enforced in production via Settings validation

# --- Default/fallback values referenced across the app ---
DEFAULT_LOG_FILENAME = "app.log"