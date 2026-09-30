"""Unit tests for the dribble client. All HTTP is mocked — no network, no key."""

import os
from unittest.mock import MagicMock, patch

import pytest

from dribble import (
    AuthenticationError,
    BadRequestError,
    Client,
    DribbleError,
    NotFoundError,
    RateLimitError,
    ServerError,
)


def make_response(status=200, payload=None, headers=None):
    resp = MagicMock()
    resp.status_code = status
    resp.headers = headers or {}
    resp.json.return_value = payload if payload is not None else {"rows": []}
    resp.text = ""
    return resp


def client_with_mock(*responses):
    """Client whose session.get returns the given mock responses in order."""
    c = Client(api_key="drb_test_key")
    c.session.get = MagicMock(side_effect=list(responses))
    return c


def test_missing_key_raises():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="DRIBBLE360_API_KEY"):
            Client()


def test_env_var_key():
    with patch.dict(os.environ, {"DRIBBLE360_API_KEY": "drb_from_env"}):
        c = Client()
        assert c._api_key == "drb_from_env"


def test_constructor_arg_beats_env():
    with patch.dict(os.environ, {"DRIBBLE360_API_KEY": "drb_from_env"}):
        c = Client(api_key="drb_explicit")
        assert c._api_key == "drb_explicit"


def test_auth_header_sent():
    c = client_with_mock(make_response(200, {"rows": [{"id": 1}]}))
    c.fetch_page("teams")
    _, kwargs = c.session.get.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer drb_test_key"
    assert "drb_test_key" not in str(kwargs.get("params", {}))


def test_key_never_in_url():
    c = client_with_mock(make_response(200, {"rows": []}))
    c.fetch_page("teams")
    args, kwargs = c.session.get.call_args
    assert "drb_test_key" not in args[0]
    assert "drb_test_key" not in str(kwargs.get("params", {}))


def test_single_page_fetch():
    rows = [{"id": 1}, {"id": 2}]
    c = client_with_mock(make_response(200, {"rows": rows}))
    assert c.fetch_page("teams") == rows


def test_pagination_params():
    c = client_with_mock(make_response(200, {"rows": []}))
    c.fetch_page("teams", page=3, page_size=50)
    _, kwargs = c.session.get.call_args
    assert kwargs["params"]["limit"] == 50
    assert kwargs["params"]["offset"] == 100


def test_fetch_auto_paginates():
    c = client_with_mock(
        make_response(200, {"rows": [{"id": 1}, {"id": 2}]}),
        make_response(200, {"rows": [{"id": 3}]}),
    )
    rows = c.fetch("teams", page_size=2)
    assert [r["id"] for r in rows] == [1, 2, 3]
    assert c.session.get.call_count == 2


def test_fetch_max_rows():
    c = client_with_mock(make_response(200, {"rows": [{"id": i} for i in range(5)]}))
    rows = c.fetch("teams", page_size=5, max_rows=3)
    assert len(rows) == 3


def test_filter_params_passed_through():
    c = client_with_mock(make_response(200, {"rows": []}))
    c.fetch_page("matches", season="2025/2026", page_size=10)
    _, kwargs = c.session.get.call_args
    assert kwargs["params"]["season"] == "2025/2026"


def test_unknown_dataset_raises():
    c = client_with_mock()
    with pytest.raises(ValueError, match="Unknown dataset"):
        c.fetch_page("odds")


def test_season_required():
    c = client_with_mock()
    with pytest.raises(ValueError, match="requires a season"):
        c.player_matches()
    with pytest.raises(ValueError, match="requires a season"):
        c.team_matches(season=None)


def test_season_passed_for_match_stats():
    c = client_with_mock(make_response(200, {"rows": []}))
    c.player_matches("2025/2026")
    _, kwargs = c.session.get.call_args
    assert kwargs["params"]["season"] == "2025/2026"


def test_401_maps_to_authentication_error():
    c = client_with_mock(make_response(401, {"message": "bad key"}))
    with pytest.raises(AuthenticationError):
        c.fetch_page("teams")


def test_404_maps_to_not_found():
    c = client_with_mock(make_response(404, {"message": "nope"}))
    with pytest.raises(NotFoundError):
        c.fetch_page("teams")


def test_400_maps_to_bad_request():
    c = client_with_mock(make_response(400, {"message": "bad param"}))
    with pytest.raises(BadRequestError):
        c.fetch_page("teams")


def test_429_retries_then_raises_rate_limit():
    c = client_with_mock(
        make_response(429, {"message": "slow down"}),
        make_response(429, {"message": "slow down"}),
        make_response(429, {"message": "slow down"}),
        make_response(429, {"message": "slow down"}),
    )
    c.max_retries = 1
    with patch("dribble.client.time.sleep"):
        with pytest.raises(RateLimitError):
            c.fetch_page("teams")
    assert c.session.get.call_count == 2


def test_500_retries_then_succeeds():
    c = client_with_mock(
        make_response(500, {"message": "boom"}),
        make_response(200, {"rows": [{"id": 9}]}),
    )
    c.max_retries = 2
    with patch("dribble.client.time.sleep"):
        assert c.fetch_page("teams") == [{"id": 9}]


def test_500_exhausted_raises_server_error():
    c = client_with_mock(make_response(500), make_response(500))
    c.max_retries = 1
    with patch("dribble.client.time.sleep"):
        with pytest.raises(ServerError):
            c.fetch_page("teams")


def test_error_message_never_contains_key():
    c = client_with_mock(make_response(401, {"message": "bad key"}))
    try:
        c.fetch_page("teams")
    except DribbleError as exc:
        assert "drb_test_key" not in str(exc)
    else:
        pytest.fail("expected AuthenticationError")


def test_bare_list_payload():
    c = client_with_mock(make_response(200, [{"id": 1}]))
    c.session.get.return_value.json.return_value = [{"id": 1}]
    assert c.fetch_page("teams") == [{"id": 1}]


def test_fetch_df_without_pandas():
    c = client_with_mock()
    with patch.dict("sys.modules", {"pandas": None}):
        with pytest.raises(ImportError, match="pandas"):
            c.fetch_df("teams")


def test_fetch_df_uses_pandas():
    pd = pytest.importorskip("pandas")
    c = client_with_mock(make_response(200, {"rows": [{"a": 1}, {"a": 2}]}))
    df = c.fetch_df("teams")
    assert list(df["a"]) == [1, 2]


def test_dataset_methods_hit_right_paths():
    c = client_with_mock(*[make_response(200, {"rows": []}) for _ in range(8)])
    c.players()
    c.teams()
    c.matches()
    c.transfers()
    c.managers()
    c.referees()
    c.player_matches("2025/2026")
    c.team_matches("2025/2026")
    paths = [call.args[0] for call in c.session.get.call_args_list]
    for dataset in ("players", "teams", "matches", "transfers",
                    "managers", "referees", "player_matches", "team_matches"):
        assert any(p.endswith(f"/{dataset}") for p in paths), dataset
