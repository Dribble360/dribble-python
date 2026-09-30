#!/usr/bin/env python3
"""Example 3: download a dataset and save it to CSV.

Reads the DRIBBLE360_API_KEY environment variable.
Usage: python save_to_csv.py [dataset] [output.csv]   (default: teams)
"""
import csv
import os
import sys

from dribble import DATASETS, Client


def main():
    dataset = sys.argv[1] if len(sys.argv) > 1 else "teams"
    out_path = sys.argv[2] if len(sys.argv) > 2 else f"{dataset}.csv"
    if dataset not in DATASETS:
        sys.exit(f"Unknown dataset {dataset!r}. Choose from: {', '.join(DATASETS)}")

    client = Client()  # DRIBBLE360_API_KEY
    kwargs = {}
    if dataset in ("player_matches", "team_matches"):
        kwargs["season"] = "2026/2027"  # required for these datasets

    rows = client.fetch(dataset, **kwargs)
    if not rows:
        sys.exit("No rows returned.")

    columns = sorted({k for r in rows for k in r.keys()})
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved {len(rows)} rows x {len(columns)} cols -> {out_path}")


if __name__ == "__main__":
    if not os.environ.get("DRIBBLE360_API_KEY"):
        sys.exit("Set DRIBBLE360_API_KEY first (key from dribble360.com/api-subscribers).")
    main()
