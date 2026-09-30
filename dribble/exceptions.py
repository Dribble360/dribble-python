"""Exceptions raised by the dribble client.

The API key is never included in exception messages.
"""


class DribbleError(Exception):
    """Base error for all dribble client failures."""

    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


class AuthenticationError(DribbleError):
    """HTTP 401/403 — missing, invalid, or expired API key."""


class BadRequestError(DribbleError):
    """HTTP 400 — the request was malformed (e.g. bad dataset or params)."""


class NotFoundError(DribbleError):
    """HTTP 404 — unknown dataset or resource."""


class RateLimitError(DribbleError):
    """HTTP 429 — daily call allowance exhausted.

    Rate limits reset at midnight UTC. ``retry_after`` carries the
    ``Retry-After`` header value when the server sends one.
    """

    def __init__(self, message, status_code=None, retry_after=None):
        super().__init__(message, status_code)
        self.retry_after = retry_after


class ServerError(DribbleError):
    """HTTP 5xx — the API failed; safe to retry."""
