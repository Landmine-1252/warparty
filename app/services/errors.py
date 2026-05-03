from __future__ import annotations


class ServiceError(ValueError):
    """Expected business-rule violation suitable for user-facing responses."""
