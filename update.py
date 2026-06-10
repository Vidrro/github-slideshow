#!/usr/bin/env python3
"""Daily update during the tournament.

Re-ingests the latest results (the martj42 dataset is updated continuously
during the World Cup), rebuilds features, re-estimates the Dixon-Coles
parameters, and regenerates predictions for the remaining (unplayed) fixtures.

Usage:
    python update.py

Intended to be run once a day while WC2026 is in progress. It is idempotent:
running it before any match is played reproduces the pre-tournament forecast.
"""
from __future__ import annotations

import sys

import pandas as pd

from src import config as C
from src import ingest, features, model as model_mod, predict


def main() -> int:
    print("#" * 70)
    print("# WORLD CUP 2026 - DAILY UPDATE")
    print("#" * 70)

    # 1. Ingest fresh data.
    if ingest.run() != 0:
        print("Update aborted: ingestion failed.")
        return 1

    # 2. Rebuild features and refit.
    features.run()
    model_mod.run()

    # 3. Report tournament progress.
    fx = pd.read_csv(C.FIXTURES_CSV, parse_dates=["date"])
    played = fx["home_score"].notna()
    print(f"\nGroup-stage progress: {int(played.sum())}/{len(fx)} matches played.")

    if played.any():
        print("Most recent results:")
        recent = fx[played].sort_values("date").tail(5)
        for _, r in recent.iterrows():
            print(f"  {r['date'].date()}  {r['home_team']} "
                  f"{int(r['home_score'])}-{int(r['away_score'])} {r['away_team']}")

    # 4. Regenerate predictions for the pending matches + Monte Carlo.
    predict.run()

    pending = fx[~played]
    print(f"\nRegenerated forecasts; {len(pending)} group fixtures still pending.")
    print("Update complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
