# dribble — Python client for the Dribble football data API

Query Opta-sourced football data (matches, xG, player/team stats, transfers and more)
from Python in a few lines. Built for analysts, bettors-modelers, and developers
building on [dribble360.com](https://dribble360.com).

## Install

```bash
pip install dribble
```

With optional pandas support (for `fetch_df`):

```bash
pip install "dribble[pandas]"
```

## Quickstart

```python
from dribble import Client

client = Client()  # reads DRIBBLE360_API_KEY from the environment

# Premier League 2026/27 matches
matches = client.matches(season="2026/2027")

# Per-player match stats (season is required here)
pm = client.player_matches(season="2026/2027")

# ... or as a DataFrame
df = client.fetch_df("team_matches", season="2026/2027")
```

## Auth

Generate a key at [dribble360.com/api-subscribers](https://dribble360.com/api-subscribers)
(shown once — store it somewhere safe), then either:

```bash
export DRIBBLE360_API_KEY="drb_..."
```

or pass it explicitly:

```python
client = Client(api_key="drb_...")
```

The client sends the key only as an `Authorization: Bearer` header and never
logs, prints, or persists it.

Plans and limits: [dribble360.com/pricing](https://dribble360.com/pricing).
Rate limits reset at midnight UTC; responses carry `X-RateLimit-*` headers
(available on the client as `client.last_response_headers`).

## Datasets

One method per dataset; extra keyword arguments are passed through as query
params (`season`, `limit`, `offset`, ...). All fetches auto-paginate.

| Method | Dataset | Notes |
|---|---|---|
| `client.players()` | 90,582 players | id, name/slug, nationality |
| `client.teams()` | 8,054 teams | id, name |
| `client.matches()` | 41,017 matches | id, date, week, status, scores, `season_id` |
| `client.transfers()` | 179,554 transfers | |
| `client.managers()` | 72,299 managers | |
| `client.referees()` | 180,774 referees | |
| `client.player_matches(season)` | ~210K rows/season | **season required**, e.g. `"2025/2026"`; per-player stats incl. `expected_goals`, `expected_assists` |
| `client.team_matches(season)` | ~12K rows/season | **season required**; per-team stats incl. `expected_goals`, `side` (HOME/AWAY) |

xG lives on the `*_matches` rows (`expected_goals`), keyed by `match_id` —
see `examples/matchweek_xg.py` for the join. Competitions are selected via
`season_id` on match rows (no verified `competition=` query param exists, so
filter client-side).

```python
# one page at a time
page = client.fetch_page("matches", page=2, page_size=500, season="2026/2027")

# everything, with a cap
rows = client.fetch("transfers", max_rows=10_000)
```

Errors raise typed exceptions: `AuthenticationError` (401/403),
`BadRequestError` (400), `NotFoundError` (404), `RateLimitError` (429),
`ServerError` (5xx). The client retries 429/5xx with backoff automatically.

## Examples

In [`examples/`](examples/):

1. `matchweek_xg.py` — latest completed Premier League matchweek with xG
2. `top_scorers_xg.py` — top 10 scorers by xG for a team and season
3. `save_to_csv.py` — download any dataset to CSV (`python save_to_csv.py teams teams.csv`)

## Honest scope notes

- **Post-match data on a daily refresh — not a live feed.** No live scores, no pre-kickoff lineups.
- **No odds data.** There is no odds dataset and no bookmaker fields anywhere in the API.
- Nulls: in count fields (goals, shots, fouls) null means zero where the metric is covered for that competition/season; null xG/xA means no qualifying action was recorded.
- Licence: personal & research use is permitted on all plans; commercial use (apps, dashboards, models, published research) needs API Elite/Flite. **Raw-data redistribution is never included by default** — it needs a separately signed order form / data-licence addendum (Terms §6, §8). See [pricing](https://dribble360.com/pricing) for plan details.

## License

MIT — see [LICENSE](LICENSE).
