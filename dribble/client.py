"""Python client for the Dribble football data API.

Base URL: https://dribble360.com/api/v1/{dataset}
Auth: ``Authorization: Bearer <drb_... key>``.

Post-match data on a daily refresh — not a live feed. No odds dataset,
no live-scores endpoint.
"""

import os
import time

import requests

from .exceptions import (
    AuthenticationError,
    BadRequestError,
    DribbleError,
    NotFoundError,
    RateLimitError,
    ServerError,
)

__version__ = "0.1.0"

BASE_URL = "https://dribble360.com/api/v1"
ENV_VAR = "DRIBBLE360_API_KEY"

#: All datasets exposed by the API.
DATASETS = (
    "players",
    "teams",
    "matches",
    "transfers",
    "managers",
    "referees",
    "player_matches",
    "team_matches",
)

#: These datasets only return rows when a season is given, e.g. "2025/2026".
SEASON_REQUIRED = {"player_matches", "team_matches"}

DEFAULT_PAGE_SIZE = 1000
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_RETRIES = 3


class Client:
    """Dribble API client.

    Parameters
    ----------
    api_key:
        Your ``drb_...`` key from https://dribble360.com/api-subscribers.
        Falls back to the ``DRIBBLE360_API_KEY`` environment variable.
        The key is sent only as an ``Authorization: Bearer`` header and is
        never logged, printed, or persisted by this client.
    base_url: Override the API base (defaults to the production API).
    timeout: Per-request socket timeout in seconds.
    max_retries: Retries with backoff on HTTP 429 and 5xx responses.
    page_size: Default ``limit`` used when auto-paginating.
    """

    def __init__(
        self,
        api_key=None,
        *,
        base_url=BASE_URL,
        timeout=DEFAULT_TIMEOUT,
        max_retries=DEFAULT_MAX_RETRIES,
        page_size=DEFAULT_PAGE_SIZE,
    ):
        key = api_key or os.environ.get(ENV_VAR)
        if not key:
            raise ValueError(
                "No API key provided. Pass api_key=... or set the "
                f"{ENV_VAR} environment variable. Generate a key at "
                "https://dribble360.com/api-subscribers"
            )
        self._api_key = key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.page_size = page_size
        self.session = requests.Session()
        #: Headers of the most recent response (includes X-RateLimit-*).
        self.last_response_headers = {}

    # -- internals ------------------------------------------------------

    def _headers(self):
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
            "User-Agent": f"dribble-python/{__version__}",
        }

    def _raise_for_status(self, response):
        status = response.status_code
        if status == 200:
            return
        try:
            detail = response.json().get("message") or response.json().get("error")
        except Exception:
            detail = (response.text or "").strip()[:200]
        msg = f"API request failed (HTTP {status})"
        if detail:
            msg += f": {detail}"
        if status in (401, 403):
            raise AuthenticationError(
                msg + " — check your key at dribble360.com/api-subscribers",
                status_code=status,
            )
        if status == 400:
            raise BadRequestError(msg, status_code=status)
        if status == 404:
            raise NotFoundError(msg, status_code=status)
        if status == 429:
            raise RateLimitError(
                msg + " — daily allowance exhausted; resets midnight UTC",
                status_code=status,
                retry_after=response.headers.get("Retry-After"),
            )
        if status >= 500:
            raise ServerError(msg, status_code=status)
        raise DribbleError(msg, status_code=status)

    def _get(self, dataset, params):
        url = f"{self.base_url}/{dataset}"
        last_exc = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.get(
                    url, headers=self._headers(), params=params, timeout=self.timeout
                )
            except requests.RequestException as exc:
                last_exc = DribbleError(f"Request failed: {exc}")
                time.sleep(2 ** attempt)
                continue
            self.last_response_headers = dict(response.headers)
            try:
                self._raise_for_status(response)
            except (RateLimitError, ServerError) as exc:
                last_exc = exc
                wait = 2 ** attempt
                retry_after = getattr(exc, "retry_after", None)
                if retry_after:
                    try:
                        wait = max(wait, int(retry_after))
                    except ValueError:
                        pass
                time.sleep(wait)
                continue
            return response.json()
        raise last_exc

    @staticmethod
    def _rows(payload):
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            rows = payload.get("rows", [])
            return rows if isinstance(rows, list) else []
        return []

    def _check_dataset(self, dataset, params):
        if dataset not in DATASETS:
            raise ValueError(
                f"Unknown dataset {dataset!r}. Available: {', '.join(DATASETS)}"
            )
        if dataset in SEASON_REQUIRED and not params.get("season"):
            raise ValueError(
                f"{dataset} requires a season, e.g. "
                f'client.{dataset}(season="2025/2026")'
            )

    # -- public fetch API -----------------------------------------------

    def fetch_page(self, dataset, *, page=1, page_size=None, **params):
        """Fetch a single page of rows.

        Pages are 1-based. Returns a list of row dicts (possibly empty).
        Extra keyword args are passed through as query params.
        """
        self._check_dataset(dataset, params)
        size = page_size or self.page_size
        params = dict(params, limit=size, offset=(page - 1) * size)
        return self._rows(self._get(dataset, params))

    def fetch(self, dataset, *, page_size=None, max_rows=None, **params):
        """Fetch all rows, auto-paginating with ``limit``/``offset``.

        Stops when a page comes back short, or when ``max_rows`` is reached.
        Extra keyword args are passed through as query params.
        """
        self._check_dataset(dataset, params)
        return self._fetch_all(
            dataset, size=page_size or self.page_size, max_rows=max_rows, **params
        )

    def _fetch_all(self, dataset, *, size, max_rows, **params):
        rows, offset = [], 0
        while True:
            batch = self._rows(
                self._get(dataset, dict(params, limit=size, offset=offset))
            )
            rows.extend(batch)
            if max_rows is not None and len(rows) >= max_rows:
                return rows[:max_rows]
            if len(batch) < size:
                return rows
            offset += size

    def fetch_df(self, dataset, **params):
        """Fetch all rows as a pandas DataFrame (pandas is optional)."""
        try:
            import pandas as pd
        except ImportError as exc:
            raise ImportError(
                "pandas is required for fetch_df(). Install it with "
                "`pip install dribble[pandas]`."
            ) from exc
        return pd.DataFrame(self.fetch(dataset, **params))

    # -- one method per dataset ------------------------------------------

    def players(self, **params):
        """Player directory (id, name/slug, nationality, ...)."""
        return self.fetch("players", **params)

    def teams(self, **params):
        """Team directory (id, name, ...)."""
        return self.fetch("teams", **params)

    def matches(self, **params):
        """Match results incl. xG (match_id, date, teams, goals, xG, ...)."""
        return self.fetch("matches", **params)

    def transfers(self, **params):
        """Transfer records."""
        return self.fetch("transfers", **params)

    def managers(self, **params):
        """Manager directory."""
        return self.fetch("managers", **params)

    def referees(self, **params):
        """Referee directory."""
        return self.fetch("referees", **params)

    def player_matches(self, season=None, **params):
        """Per-player per-match stats. ``season`` is required, e.g. "2025/2026"."""
        return self.fetch("player_matches", season=season, **params)

    def team_matches(self, season=None, **params):
        """Per-team per-match stats. ``season`` is required, e.g. "2025/2026"."""
        return self.fetch("team_matches", season=season, **params)
