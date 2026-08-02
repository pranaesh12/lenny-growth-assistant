"""
Service-layer exceptions.

Custom exceptions raised by the service layer to signal business-rule
violations — as distinct from database errors (handled by the
repository layer) or HTTP concerns (handled by the future API layer).
Each exception carries a plain, human-readable message; translating
these into HTTP status codes is an API-layer concern, not implemented
here.
"""


class ServiceError(Exception):
    """Base class for all service-layer errors."""


class NotFoundError(ServiceError):
    """Raised when a requested resource does not exist."""


class ValidationError(ServiceError):
    """Raised when input fails a business validation rule."""


class ConflictError(ServiceError):
    """
    Raised when an operation conflicts with the resource's current
    state (e.g. renaming an archived session, deleting an
    already-deleted resource).
    """


__all__ = ["ServiceError", "NotFoundError", "ValidationError", "ConflictError"]