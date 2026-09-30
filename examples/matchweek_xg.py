#!/usr/bin/env python3
"""Example 1: last completed Premier League matchweek, with xG.

Reads the DRIBBLE360_API_KEY environment variable.

Data notes (verified against the API):
- matches rows carry: id, date, week, status, description ("Home vs Away"),
  home_score, away_score, season_id. xG is NOT on the match row.
- xG lives on team_matches rows: (match_id, side) -> expected_goals.
- Competitions are selected via season_id (see season-map in the docs);
  there is no verified `competition=` query param, so we filter client-side.
"""
import os
import sys

from dribble import Client

# Premier League 2026/27 (from the season map; update for other comps/seasons)
PL_SEASON_ID = "6pdwluctev9iebv00r4qqukno"
SEASON = "2026/2027"


def main():
    client = Client()  # DRIBBLE360_API_KEY

    matches = [
        m
        for m in client.matches(season=SEASON)
        if m.get("season_id") == PL_SEASON_ID
    ]
    played = [m for m in matches if m.get("status") == "PLAYED"]
    if not played:
        print("No completed matches found.", file=sys.stderr)
        return

    latest_week = max(m["week"] for m in played if m.get("week") is not None)

    # xG lookup: (match_id, side) -> expected_goals
    xg = {}
    for row in client.team_matches(season=SEASON):
        xg[(row.get("match_id"), row.get("side"))] = row.get("expected_goals")

    print(f"Premier League {SEASON} — matchweek {latest_week}\n")
    week_matches = sorted(
        (m for m in played if m.get("week") == latest_week),
        key=lambda m: m.get("date") or "",
    )
    for m in week_matches:
        desc = m.get("description") or ""
        home, away = (desc.split(" vs ", 1) + ["", ""])[:2]
        hx = xg.get((m.get("id"), "HOME"))
        ax = xg.get((m.get("id"), "AWAY"))
        score = f"{m.get('home_score')}-{m.get('away_score')}"
        xg_str = (
            f"xG {hx:.2f}-{ax:.2f}" if hx is not None and ax is not None else "xG n/a"
        )
        print(f"{m.get('date', '')[:10]}  {home.strip():22} {score:5}  {away.strip():22}  {xg_str}")


if __name__ == "__main__":
    if not os.environ.get("DRIBBLE360_API_KEY"):
        sys.exit("Set DRIBBLE360_API_KEY first (key from dribble360.com/api-subscribers).")
    main()
