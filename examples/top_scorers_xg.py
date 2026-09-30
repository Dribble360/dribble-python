#!/usr/bin/env python3
"""Example 2: top scorers by expected goals (xG) for one team and season.

Reads the DRIBBLE360_API_KEY environment variable.

Verified row fields used here:
- teams: id, name
- player_matches: player_id, team_id, goals, expected_goals, mins_played
- players: id, name (core fields on every plan)
"""
import os
import sys
from collections import defaultdict

from dribble import Client

TEAM_NAME = "Arsenal"  # change to any team
SEASON = "2026/2027"
MIN_MINUTES = 90


def main():
    client = Client()  # DRIBBLE360_API_KEY

    team = next(
        (t for t in client.teams() if t.get("name", "").lower() == TEAM_NAME.lower()),
        None,
    )
    if team is None:
        sys.exit(f"Team {TEAM_NAME!r} not found.")

    agg = defaultdict(lambda: {"goals": 0, "xg": 0.0, "mins": 0})
    for row in client.player_matches(season=SEASON):
        if row.get("team_id") != team["id"]:
            continue
        pid = row["player_id"]
        agg[pid]["goals"] += row.get("goals") or 0
        agg[pid]["xg"] += row.get("expected_goals") or 0.0
        agg[pid]["mins"] += row.get("mins_played") or 0

    names = {p["id"]: p.get("name", p["id"]) for p in client.players()}

    table = [
        (names.get(pid, pid), v["goals"], v["xg"], v["mins"])
        for pid, v in agg.items()
        if v["mins"] >= MIN_MINUTES
    ]
    table.sort(key=lambda r: r[2], reverse=True)

    print(f"{TEAM_NAME} {SEASON} — top 10 by xG (min {MIN_MINUTES} mins)\n")
    print(f"{'Player':28} {'G':>3} {'xG':>6} {'Min':>5}")
    for name, goals, xg, mins in table[:10]:
        print(f"{name[:28]:28} {goals:>3} {xg:>6.2f} {mins:>5}")


if __name__ == "__main__":
    if not os.environ.get("DRIBBLE360_API_KEY"):
        sys.exit("Set DRIBBLE360_API_KEY first (key from dribble360.com/api-subscribers).")
    main()
