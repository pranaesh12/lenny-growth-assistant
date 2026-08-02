"""
Security-related configuration helpers.

Phase 2 scope: this module provides configuration-level security
utilities only (secret key validation, algorithm constants exposed
for future use). It does NOT implement authentication, password
hashing, or JWT issuance/verification — those belong to a future
Auth/Security service phase and depend on Settings defined here.
"""

import logging
import secrets

from app.core.constants import JWT_ALGORITHM, MIN_SECRET_KEY_LENGTH
from app.core.constants import Environment

logger = logging.getLogger(__name__)


def validate_secret_key(secret_key: str, environment: Environment) -> str:
    """
    Validates the configured SECRET_KEY based on the running environment.

    In production, a weak, default, or missing secret key is a hard
    failure (raises ValueError) rather than a warning — this is
    enforced at settings-load time so misconfiguration is caught at
    startup, not discovered later during a security incident.

    In development/testing, a weak key only logs a warning so local
    setup friction stays low.

    Args:
        secret_key: The configured secret key value.
        environment: The current running environment.

    Returns:
        The validated secret key, unchanged.

    Raises:
        ValueError: If running in production with an insecure key.
    """
    is_placeholder = secret_key in (
        "",
        "change_this_to_a_random_secret_in_production",
        "dev-only-secret-key-not-for-production-use",
    )
    is_too_short = len(secret_key) < MIN_SECRET_KEY_LENGTH

    if environment == Environment.PRODUCTION and (is_placeholder or is_too_short):
        raise ValueError(
            "SECRET_KEY is missing, a placeholder, or too short "
            f"(minimum {MIN_SECRET_KEY_LENGTH} characters) for a "
            "production environment. Generate one with: "
            "python -c \"import secrets; print(secrets.token_urlsafe(64))\""
        )

    if is_placeholder or is_too_short:
        logger.warning(
            "SECRET_KEY looks like a placeholder or is shorter than "
            "%s characters. This is acceptable for local development "
            "only — do not use this value in production.",
            MIN_SECRET_KEY_LENGTH,
        )

    return secret_key


def generate_secret_key() -> str:
    """
    Generates a cryptographically secure random secret key.

    Utility for local setup / CLI use (e.g. `python -m app.core.security`),
    not called automatically by Settings.
    """
    return secrets.token_urlsafe(64)


__all__ = ["validate_secret_key", "generate_secret_key", "JWT_ALGORITHM"]


if __name__ == "__main__":
    print(generate_secret_key())