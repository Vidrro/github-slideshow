"""Stage 2 - Feature construction.

Two jobs:

1. Compute a running Elo rating for every team across the *entire* match history
   (1872-present). The pre-match Elo difference is the `delta_elo` covariate of
   the Dixon-Coles model. We compute it ourselves so the pipeline does not
   depend on scraping eloratings.net (which blocks bots); the ratings it
   produces are strongly correlated with the published ones.

2. Build the training frame: matches from TRAIN_START onward, each tagged with
   an exponential time weight (half-life ~2y), a home indicator, and the
   pre-match delta_elo. Future/unplayed fixtures are excluded.

Run as a script:

    python -m src.features
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from . import config as C
from .ingest import load_results


# --------------------------------------------------------------------------
# Elo
# --------------------------------------------------------------------------
def _expected(elo_a: float, elo_b: float) -> float:
    """Logistic expected score for A vs B."""
    return 1.0 / (1.0 + 10.0 ** ((elo_b - elo_a) / 400.0))


def _gd_multiplier(goal_diff: int) -> float:
    """World-football-Elo goal-difference weighting of K."""
    gd = abs(goal_diff)
    if gd <= 1:
        return 1.0
    if gd == 2:
        return 1.5
    return (11.0 + gd) / 8.0


def compute_elo_history(results: pd.DataFrame) -> pd.DataFrame:
    """Walk the full history chronologically, recording pre-match Elo.

    Returns the results frame with two extra columns: `home_elo_pre` and
    `away_elo_pre` (the rating each side carried *into* the match). Only rows
    with an actual scoreline update the ratings.
    """
    ratings: dict[str, float] = {}
    home_pre = np.full(len(results), np.nan)
    away_pre = np.full(len(results), np.nan)

    played = results["home_score"].notna() & results["away_score"].notna()

    for i, row in enumerate(results.itertuples(index=False)):
        h, a = row.home_team, row.away_team
        rh = ratings.get(h, C.ELO_INIT)
        ra = ratings.get(a, C.ELO_INIT)
        home_pre[i] = rh
        away_pre[i] = ra

        if not played.iloc[i]:
            continue  # future fixture: record pre-match Elo but don't update

        # Home advantage only when not a neutral venue.
        adv = 0.0 if row.neutral else C.ELO_HOME_ADV
        exp_h = _expected(rh + adv, ra)

        hs, as_ = float(row.home_score), float(row.away_score)
        if hs > as_:
            score_h = 1.0
        elif hs < as_:
            score_h = 0.0
        else:
            score_h = 0.5

        k = C.ELO_K * _gd_multiplier(int(hs - as_))
        delta = k * (score_h - exp_h)
        ratings[h] = rh + delta
        ratings[a] = ra - delta

    out = results.copy()
    out["home_elo_pre"] = home_pre
    out["away_elo_pre"] = away_pre

    # Persist the final rating snapshot for inspection / prediction.
    snap = (
        pd.DataFrame({"team": list(ratings.keys()), "elo": list(ratings.values())})
        .sort_values("elo", ascending=False)
        .reset_index(drop=True)
    )
    snap.to_csv(C.ELO_HISTORY_CSV, index=False)
    return out


def _wc2026_teams() -> set[str]:
    """The 48 teams contesting WC2026 (from the fixtures file if present)."""
    import os

    if os.path.exists(C.FIXTURES_CSV):
        fx = pd.read_csv(C.FIXTURES_CSV)
        return set(fx["home_team"]) | set(fx["away_team"])
    return set()


def current_elo() -> pd.Series:
    """Latest Elo snapshot as a team->rating Series (from elo_history.csv)."""
    snap = pd.read_csv(C.ELO_HISTORY_CSV)
    return snap.set_index("team")["elo"]


# --------------------------------------------------------------------------
# Training frame
# --------------------------------------------------------------------------
def build_training_frame(
    results: pd.DataFrame | None = None,
    as_of: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Construct the weighted, Elo-augmented training table.

    Parameters
    ----------
    results : optional pre-loaded results frame.
    as_of   : only include matches strictly before this date (used by the
              backtest to avoid leakage). Defaults to "today" (include all
              played matches).
    """
    if results is None:
        results = load_results()
    results = compute_elo_history(results)

    as_of = pd.Timestamp(as_of) if as_of is not None else results["date"].max() + pd.Timedelta(days=1)

    played = (
        results["home_score"].notna()
        & results["away_score"].notna()
        & (results["date"] >= pd.Timestamp(C.TRAIN_START))
        & (results["date"] < as_of)
    )
    df = results[played].copy()

    # Exponential time decay relative to the reference date (`as_of`).
    age_days = (as_of - df["date"]).dt.days.clip(lower=0)
    df["weight"] = 0.5 ** (age_days / C.HALF_LIFE_DAYS)

    # Home indicator: 1 only when the home side actually had home advantage.
    df["home_adv"] = (~df["neutral"]).astype(float)

    # Scaled Elo difference (per 100 points) seen from the home side.
    df["delta_elo"] = (df["home_elo_pre"] - df["away_elo_pre"]) / 100.0

    # Drop exotic/non-FIFA sides: iteratively remove teams with too few
    # matches, then matches that involve them. WC2026 nations always survive.
    must_keep = _wc2026_teams()
    while True:
        counts = pd.concat([df["home_team"], df["away_team"]]).value_counts()
        rare = set(counts[counts < C.MIN_TEAM_MATCHES].index) - must_keep
        if not rare:
            break
        df = df[~df["home_team"].isin(rare) & ~df["away_team"].isin(rare)]

    df["home_score"] = df["home_score"].astype(int)
    df["away_score"] = df["away_score"].astype(int)

    cols = [
        "date", "home_team", "away_team", "home_score", "away_score",
        "neutral", "home_adv", "delta_elo", "weight", "tournament",
    ]
    out = df[cols].reset_index(drop=True)
    return out


def run() -> int:
    print("=" * 70)
    print("STAGE 2: FEATURES")
    print("=" * 70)
    results = load_results()
    train = build_training_frame(results)
    train.to_csv(C.TRAINING_CSV, index=False)

    teams = sorted(set(train["home_team"]) | set(train["away_team"]))
    print(f"Training rows: {len(train):,}  ({train['date'].min().date()} .. "
          f"{train['date'].max().date()})")
    print(f"Distinct teams: {len(teams)}")
    print(f"Weight range: {train['weight'].min():.3f} .. {train['weight'].max():.3f}")
    print(f"Mean goals home/away: {train['home_score'].mean():.2f} / "
          f"{train['away_score'].mean():.2f}")

    elo = current_elo()
    print("\nTop-10 current Elo (derived from history):")
    print(elo.head(10).to_string())
    print(f"\nWrote {C.TRAINING_CSV} and {C.ELO_HISTORY_CSV}")
    print("Stage 2 complete.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
