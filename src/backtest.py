"""Stage 5 - Backtesting against Qatar 2022 and Euro 2024.

For each historical tournament we:
  1. retrain the Dixon-Coles model using ONLY matches before the tournament
     started (as_of = first match date) to avoid look-ahead leakage;
  2. predict each tournament match's 1X2 (home/draw/away) probabilities;
  3. score the forecasts with the Ranked Probability Score (RPS) and the
     multiclass Brier score against the realised regulation-time outcomes;
  4. compare against a naive "always 1-1" baseline and, if a market-odds file is
     present, against bookmaker implied probabilities.

Run as a script:

    python -m src.backtest
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from . import config as C
from .features import compute_elo_history, build_training_frame
from .ingest import load_results, load_odds
from .model import DixonColesModel
from .predict import score_matrix


# --------------------------------------------------------------------------
# Scoring rules
# --------------------------------------------------------------------------
def rps(probs: np.ndarray, outcome: int) -> float:
    """Ranked Probability Score for ordered categories [home, draw, away].

    `outcome` is the index (0/1/2) of the realised category. Lower is better.
    """
    obs = np.zeros(len(probs))
    obs[outcome] = 1.0
    cum_p = np.cumsum(probs)
    cum_o = np.cumsum(obs)
    return float(np.sum((cum_p[:-1] - cum_o[:-1]) ** 2) / (len(probs) - 1))


def brier(probs: np.ndarray, outcome: int) -> float:
    """Multiclass Brier score. Lower is better."""
    obs = np.zeros(len(probs))
    obs[outcome] = 1.0
    return float(np.sum((probs - obs) ** 2))


def _outcome_index(home_score: int, away_score: int) -> int:
    if home_score > away_score:
        return 0  # home win
    if home_score == away_score:
        return 1  # draw
    return 2      # away win


# --------------------------------------------------------------------------
# Per-tournament backtest
# --------------------------------------------------------------------------
def backtest_tournament(name: str, tournament: str, start: str, end: str,
                        results: pd.DataFrame) -> dict:
    """Backtest one tournament; returns a metrics dict."""
    # Pre-match Elo for every match across full history (sequential, no leak).
    elo_aug = compute_elo_history(results)

    mask = (
        (elo_aug["tournament"] == tournament)
        & (elo_aug["date"] >= pd.Timestamp(start))
        & (elo_aug["date"] <= pd.Timestamp(end))
        & elo_aug["home_score"].notna()
    )
    matches = elo_aug[mask].copy()
    if matches.empty:
        return {"tournament": name, "n_matches": 0}

    # Train strictly on pre-tournament data.
    train = build_training_frame(results, as_of=start)
    teams = sorted(set(train["home_team"]) | set(train["away_team"]))
    model = DixonColesModel(teams).fit(train, verbose=False)

    odds = load_odds()  # optional benchmark

    model_rps, model_brier = [], []
    base_rps, base_brier = [], []
    mkt_rps, mkt_brier = [], []
    n_market = 0

    # Naive baseline: always predict 1-1 -> a certain draw, p = [0, 1, 0].
    base_probs = np.array([0.0, 1.0, 0.0])

    for _, m in matches.iterrows():
        home_adv = 0.0 if m["neutral"] else 1.0
        delta_elo = (m["home_elo_pre"] - m["away_elo_pre"]) / 100.0
        mat = score_matrix(model, m["home_team"], m["away_team"],
                           home_adv, delta_elo)
        p = np.array([
            np.tril(mat, -1).sum(),  # home win
            np.trace(mat),           # draw
            np.triu(mat, 1).sum(),   # away win
        ])
        p = p / p.sum()

        oc = _outcome_index(int(m["home_score"]), int(m["away_score"]))
        model_rps.append(rps(p, oc))
        model_brier.append(brier(p, oc))
        base_rps.append(rps(base_probs, oc))
        base_brier.append(brier(base_probs, oc))

        mp = _market_probs(odds, m) if odds is not None else None
        if mp is not None:
            mkt_rps.append(rps(mp, oc))
            mkt_brier.append(brier(mp, oc))
            n_market += 1

    res = {
        "tournament": name,
        "n_matches": int(len(matches)),
        "model_RPS": float(np.mean(model_rps)),
        "model_Brier": float(np.mean(model_brier)),
        "baseline_RPS": float(np.mean(base_rps)),
        "baseline_Brier": float(np.mean(base_brier)),
    }
    if n_market:
        res["market_RPS"] = float(np.mean(mkt_rps))
        res["market_Brier"] = float(np.mean(mkt_brier))
        res["n_market"] = n_market
    return res


def _market_probs(odds: pd.DataFrame, match) -> np.ndarray | None:
    """Convert bookmaker 1X2 odds to de-vigged probabilities, if available.

    Expects columns: date, home_team, away_team, odds_home, odds_draw,
    odds_away. Returns None when the match is not found.
    """
    try:
        sel = odds[
            (odds["home_team"] == match["home_team"])
            & (odds["away_team"] == match["away_team"])
        ]
        if sel.empty:
            return None
        r = sel.iloc[0]
        inv = np.array([1.0 / r["odds_home"], 1.0 / r["odds_draw"],
                        1.0 / r["odds_away"]])
        return inv / inv.sum()
    except Exception:  # noqa: BLE001
        return None


def run() -> int:
    print("=" * 70)
    print("STAGE 5: BACKTEST")
    print("=" * 70)
    results = load_results()

    configs = [
        ("Qatar 2022", "FIFA World Cup", "2022-11-20", "2022-12-18"),
        ("Euro 2024", "UEFA Euro", "2024-06-14", "2024-07-14"),
    ]

    rows = []
    for name, tour, start, end in configs:
        print(f"\nBacktesting {name} ...")
        r = backtest_tournament(name, tour, start, end, results)
        rows.append(r)
        if r["n_matches"] == 0:
            print(f"  no matches found for {tour} in [{start}, {end}].")
            continue
        print(f"  matches: {r['n_matches']}")
        print(f"  model    RPS={r['model_RPS']:.4f}  Brier={r['model_Brier']:.4f}")
        print(f"  baseline RPS={r['baseline_RPS']:.4f}  "
              f"Brier={r['baseline_Brier']:.4f}  (always 1-1)")
        if "market_RPS" in r:
            print(f"  market   RPS={r['market_RPS']:.4f}  "
                  f"Brier={r['market_Brier']:.4f}  (n={r['n_market']})")
        else:
            print("  market   n/a (no odds file at data/raw/odds.csv)")

    df = pd.DataFrame(rows)
    df.to_csv(f"{C.OUTPUTS_DIR}/backtest.csv", index=False)
    _write_markdown(df)
    print(f"\nWrote outputs/backtest.csv and outputs/backtest.md")
    print("Stage 5 complete.")
    return 0


def _write_markdown(df: pd.DataFrame):
    lines = ["# Backtest: Dixon-Coles vs naive baseline", ""]
    lines.append("Lower RPS / Brier is better. The model is trained only on "
                 "matches predating each tournament (no leakage). The naive "
                 "baseline always predicts a 1-1 draw.")
    lines.append("")
    lines.append("| Tournament | Matches | Model RPS | Baseline RPS | "
                 "Model Brier | Baseline Brier | Market RPS |")
    lines.append("|---|---|---|---|---|---|---|")
    for _, r in df.iterrows():
        if r["n_matches"] == 0:
            continue
        mkt = f"{r['market_RPS']:.4f}" if "market_RPS" in r and pd.notna(
            r.get("market_RPS")) else "n/a"
        lines.append(
            f"| {r['tournament']} | {int(r['n_matches'])} | "
            f"{r['model_RPS']:.4f} | {r['baseline_RPS']:.4f} | "
            f"{r['model_Brier']:.4f} | {r['baseline_Brier']:.4f} | {mkt} |")
    lines.append("")
    lines.append("_A market-odds benchmark is computed automatically when a "
                 "`data/raw/odds.csv` export (the-odds-api format) is present._")
    with open(f"{C.OUTPUTS_DIR}/backtest.md", "w") as fh:
        fh.write("\n".join(lines))


if __name__ == "__main__":
    sys.exit(run())
