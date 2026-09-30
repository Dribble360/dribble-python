"""dribble — Python client for the Dribble football data API."""

from .client import BASE_URL, DATASETS, Client, __version__
from .exceptions import (
    AuthenticationError,
    BadRequestError,
    DribbleError,
    NotFoundError,
    RateLimitError,
    ServerError,
)

__all__ = [
    "Client",
    "DribbleError",
    "AuthenticationError",
    "BadRequestError",
    "NotFoundError",
    "RateLimitError",
    "ServerError",
    "BASE_URL",
    "DATASETS",
    "__version__",
]
