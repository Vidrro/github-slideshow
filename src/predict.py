"""Stage 4 - Predictions: score matrices and Monte Carlo tournament simulation.

Provides, for any fixture:
  * the full score-probability matrix (Dixon-Coles corrected),
  * the most likely score, the top-3 scorelines, and P(win/draw/loss);

and for the whole tournament:
  * a 10,000-run Monte Carlo that estimates each nation's probability of
    advancing from its group, reaching the semifinals, and lifting the trophy.

Group membership is the 12 components inferred in ingest.py. The knockout
bracket is approximated by snake-seeding the 32 qualifiers (12 group winners,
12 runners-up, 8 best third-placed teams) by group-stage performance, then
running single elimination. The exact official slotting of third-placed teams
is a complex fixed table; snake-seeding is a transparent, defensible stand-in.

Run as a script (writes outputs/):

    python -m src.predict
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from . import config as C
from .features import current_elo
from .model import DixonColesModel, _poisson_logpmf


# --------------------------------------------------------------------------
# Score matrix
# --------------------------------------------------------------------------
def score_matrix(model: DixonColesModel, home: str, away: str,
                 home_adv: float, delta_elo: float,
                 max_goals: int = C.MAX_GOALS) -> np.ndarray:
    """Return the (max_goals+1)x(max_goals+1) score-probability matrix.

    Entry [h, a] = P(home scores h, away scores a), with the Dixon-Coles
    low-score correction applied and the matrix renormalised to sum to 1.
    """
    lam_h, lam_a = model.expected_goals(home, away, home_adv, delta_elo)
    rho = model.params["rho"]

    goals = np.arange(max_goals + 1)
    ph = np.exp(_poisson_logpmf(goals, lam_h))
    pa = np.exp(_poisson_logpmf(goals, lam_a))
    mat = np.outer(ph, pa)

    # Dixon-Coles correction on the four low-score cells.
    mat[0, 0] *= 1.0 - lam_h * lam_a * rho
    mat[0, 1] *= 1.0 + lam_h * rho
    mat[1, 0] *= 1.0 + lam_a * rho
    mat[1, 1] *= 1.0 - rho

    mat = np.clip(mat, 0.0, None)
    return mat / mat.sum()


def match_report(model: DixonColesModel, home: str, away: str,
                 home_adv: float, delta_elo: float) -> dict:
    """Human-readable summary for a single fixture."""
    mat = score_matrix(model, home, away, home_adv, delta_elo)
    lam_h, lam_a = model.expected_goals(home, away, home_adv, delta_elo)

    p_home = float(np.tril(mat, -1).sum())   # h > a
    p_away = float(np.triu(mat, 1).sum())    # a > h
    p_draw = float(np.trace(mat))

    flat = mat.flatten()
    order = np.argsort(flat)[::-1]
    top3 = []
    for idx in order[:3]:
        h, a = divmod(int(idx), mat.shape[1])
        top3.append((f"{h}-{a}", float(flat[idx])))

    best_h, best_a = divmod(int(order[0]), mat.shape[1])
    return {
        "home": home, "away": away,
        "lambda_home": round(lam_h, 3), "lambda_away": round(lam_a, 3),
        "most_likely": f"{best_h}-{best_a}",
        "top3": top3,
        "p_home_win": round(p_home, 4),
        "p_draw": round(p_draw, 4),
        "p_away_win": round(p_away, 4),
    }


# --------------------------------------------------------------------------
# Fixture helpers
# --------------------------------------------------------------------------
def load_fixtures_with_features() -> pd.DataFrame:
    fx = pd.read_csv(C.FIXTURES_CSV, parse_dates=["date"])
    elo = current_elo()
    fx["home_elo"] = fx["home_team"].map(elo).fillna(C.ELO_INIT)
    fx["away_elo"] = fx["away_team"].map(elo).fillna(C.ELO_INIT)
    fx["delta_elo"] = (fx["home_elo"] - fx["away_elo"]) / 100.0
    fx["home_adv"] = (~fx["neutral"].astype(bool)).astype(float)
    return fx


# --------------------------------------------------------------------------
# Monte Carlo tournament
# --------------------------------------------------------------------------
def _sample_scores(mat: np.ndarray, n: int, rng: np.random.Generator):
    """Draw n (home_goals, away_goals) pairs from a score matrix."""
    flat = mat.flatten()
    idx = rng.choice(len(flat), size=n, p=flat)
    ncol = mat.shape[1]
    return idx // ncol, idx % ncol


class _KnockoutCache:
    """Caches W/D/L probabilities per (home, away) ordered pair (neutral)."""

    def __init__(self, model: DixonColesModel, elo: pd.Series):
        self.model = model
        self.elo = elo
        self._c: dict[tuple[str, str], tuple[float, float, float]] = {}

    def wdl(self, a: str, b: str) -> tuple[float, float, float]:
        key = (a, b)
        if key not in self._c:
            de = (self.elo.get(a, C.ELO_INIT) - self.elo.get(b, C.ELO_INIT)) / 100.0
            mat = score_matrix(self.model, a, b, 0.0, de)  # neutral knockouts
            p_a = float(np.tril(mat, -1).sum())
            p_d = float(np.trace(mat))
            p_b = float(np.triu(mat, 1).sum())
            self._c[key] = (p_a, p_d, p_b)
        return self._c[key]

    def winner(self, a: str, b: str, u: float, coin: float) -> str:
        p_a, p_d, _ = self.wdl(a, b)
        if u < p_a:
            return a
        if u < p_a + p_d:        # draw -> penalties, ~50/50
            return a if coin < 0.5 else b
        return b


def _seed_order(n: int) -> list[int]:
    """Standard single-elimination seeding order for a bracket of size n.

    Returns 0-based seed indices arranged so seed 0 meets the weakest seeds
    earliest and the top seeds can only meet in the final.
    """
    order = [0, 1]
    while len(order) < n:
        m = len(order) * 2
        order = [x for s in order for x in (s, m - 1 - s)]
    return order


def simulate_tournament(model: DixonColesModel,
                        n_sims: int = C.N_SIMULATIONS,
                        seed: int = C.RANDOM_SEED) -> pd.DataFrame:
    """Run the Monte Carlo and return per-team advancement probabilities."""
    rng = np.random.default_rng(seed)
    fx = load_fixtures_with_features()
    groups = pd.read_csv(C.GROUPS_CSV)
    elo = current_elo()

    group_of = dict(zip(groups["team"], groups["group"]))
    teams = sorted(group_of)
    tidx = {t: i for i, t in enumerate(teams)}
    nteams = len(teams)

    # Pre-sample every group fixture's scoreline for all simulations at once.
    gh = np.zeros((len(fx), n_sims), dtype=np.int16)
    ga = np.zeros((len(fx), n_sims), dtype=np.int16)
    for k, row in fx.iterrows():
        mat = score_matrix(model, row["home_team"], row["away_team"],
                           row["home_adv"], row["delta_elo"])
        h, a = _sample_scores(mat, n_sims, rng)
        gh[k], ga[k] = h, a

    home_i = fx["home_team"].map(tidx).to_numpy()
    away_i = fx["away_team"].map(tidx).to_numpy()
    group_labels = sorted(set(group_of.values()))
    team_group_idx = np.array([group_labels.index(group_of[t]) for t in teams])

    cache = _KnockoutCache(model, elo)
    adv = np.zeros(nteams)
    semis = np.zeros(nteams)
    champ = np.zeros(nteams)

    # Pre-draw knockout randomness lazily per sim (small loop).
    for s in range(n_sims):
        pts = np.zeros(nteams)
        gd = np.zeros(nteams)
        gf = np.zeros(nteams)
        hs = gh[:, s]
        as_ = ga[:, s]
        for k in range(len(fx)):
            hi, ai = home_i[k], away_i[k]
            x, y = hs[k], as_[k]
            gf[hi] += x; gf[ai] += y
            gd[hi] += x - y; gd[ai] += y - x
            if x > y:
                pts[hi] += 3
            elif x < y:
                pts[ai] += 3
            else:
                pts[hi] += 1; pts[ai] += 1

        # Rank within each group by (pts, gd, gf, tiny noise for lots).
        noise = rng.random(nteams) * 1e-6
        key = pts + gd * 1e-3 + gf * 1e-6 + noise

        winners, runners, thirds = [], [], []
        for g in range(len(group_labels)):
            members = np.where(team_group_idx == g)[0]
            ordered = members[np.argsort(key[members])[::-1]]
            winners.append(ordered[0])
            runners.append(ordered[1])
            thirds.append(ordered[2])

        thirds = np.array(thirds)
        best_thirds = thirds[np.argsort(key[thirds])[::-1][:8]]

        qualifiers = list(winners) + list(runners) + list(best_thirds)
        adv[qualifiers] += 1

        # Seed the 32 qualifiers by group-stage strength and run single-elim.
        q_sorted = sorted(qualifiers, key=lambda t: key[t], reverse=True)
        order = _seed_order(32)
        bracket = [q_sorted[o] for o in order]  # length 32

        round_teams = bracket
        while len(round_teams) > 1:
            nxt = []
            for i in range(0, len(round_teams), 2):
                a, b = teams[round_teams[i]], teams[round_teams[i + 1]]
                w = cache.winner(a, b, rng.random(), rng.random())
                nxt.append(tidx[w])
            round_teams = nxt
            if len(round_teams) == 4:   # semifinalists determined
                for t in round_teams:
                    semis[t] += 1
        champ[round_teams[0]] += 1

    out = pd.DataFrame({
        "team": teams,
        "group": [group_of[t] for t in teams],
        "p_advance": adv / n_sims,
        "p_semifinal": semis / n_sims,
        "p_champion": champ / n_sims,
    }).sort_values("p_champion", ascending=False).reset_index(drop=True)
    return out


# --------------------------------------------------------------------------
# Output generation
# --------------------------------------------------------------------------
def generate_group_predictions(model: DixonColesModel) -> pd.DataFrame:
    fx = load_fixtures_with_features()
    rows = []
    for _, r in fx.iterrows():
        rep = match_report(model, r["home_team"], r["away_team"],
                           r["home_adv"], r["delta_elo"])
        rows.append({
            "date": r["date"].date(), "group": r["group"],
            "home": rep["home"], "away": rep["away"],
            "lambda_home": rep["lambda_home"], "lambda_away": rep["lambda_away"],
            "most_likely": rep["most_likely"],
            "top1": f"{rep['top3'][0][0]} ({rep['top3'][0][1]:.1%})",
            "top2": f"{rep['top3'][1][0]} ({rep['top3'][1][1]:.1%})",
            "top3": f"{rep['top3'][2][0]} ({rep['top3'][2][1]:.1%})",
            "p_home_win": rep["p_home_win"], "p_draw": rep["p_draw"],
            "p_away_win": rep["p_away_win"],
        })
    return pd.DataFrame(rows)


def run() -> int:
    print("=" * 70)
    print("STAGE 4: PREDICT")
    print("=" * 70)
    model = DixonColesModel.load()

    print("Generating group-stage match predictions...")
    preds = generate_group_predictions(model)
    preds.to_csv(f"{C.OUTPUTS_DIR}/group_predictions.csv", index=False)
    print(f"  wrote outputs/group_predictions.csv ({len(preds)} matches)")

    print(f"Running Monte Carlo ({C.N_SIMULATIONS:,} tournaments)...")
    sim = simulate_tournament(model)
    sim.to_csv(f"{C.OUTPUTS_DIR}/tournament_simulation.csv", index=False)
    print("  wrote outputs/tournament_simulation.csv")
    print("\nTop-10 title favourites:")
    show = sim.head(10).copy()
    for c in ("p_advance", "p_semifinal", "p_champion"):
        show[c] = (show[c] * 100).round(1).astype(str) + "%"
    print(show.to_string(index=False))

    _write_markdown(preds, sim)
    print(f"\nWrote outputs/predictions.md")
    print("Stage 4 complete.")
    return 0


def _write_markdown(preds: pd.DataFrame, sim: pd.DataFrame):
    lines = ["# World Cup 2026 - Dixon-Coles predictions", ""]
    lines.append(f"_Generated from data up to the latest available match. "
                 f"Model: weighted Dixon-Coles bivariate Poisson with Elo "
                 f"covariate._")
    lines.append("")

    # Inaugural matches highlighted.
    lines.append("## Opening day (11 June 2026)")
    lines.append("")
    opener = preds[preds["date"].astype(str) == "2026-06-11"]
    lines.append("| Match | Most likely | Top-3 scores | Home/Draw/Away |")
    lines.append("|---|---|---|---|")
    for _, r in opener.iterrows():
        lines.append(
            f"| {r['home']} vs {r['away']} | **{r['most_likely']}** | "
            f"{r['top1']}, {r['top2']}, {r['top3']} | "
            f"{r['p_home_win']:.0%} / {r['p_draw']:.0%} / {r['p_away_win']:.0%} |")
    lines.append("")

    lines.append("## Title race (Monte Carlo, "
                 f"{C.N_SIMULATIONS:,} simulations)")
    lines.append("")
    lines.append("| Team | Group | Advance | Semifinal | Champion |")
    lines.append("|---|---|---|---|---|")
    for _, r in sim.head(16).iterrows():
        lines.append(f"| {r['team']} | {r['group']} | {r['p_advance']:.0%} | "
                     f"{r['p_semifinal']:.0%} | {r['p_champion']:.1%} |")
    lines.append("")

    lines.append("## All group-stage match predictions")
    lines.append("")
    lines.append("| Group | Match | Most likely | H / D / A |")
    lines.append("|---|---|---|---|")
    for _, r in preds.iterrows():
        lines.append(f"| {r['group']} | {r['home']} vs {r['away']} | "
                     f"{r['most_likely']} | {r['p_home_win']:.0%} / "
                     f"{r['p_draw']:.0%} / {r['p_away_win']:.0%} |")
    lines.append("")

    with open(f"{C.OUTPUTS_DIR}/predictions.md", "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


if __name__ == "__main__":
    sys.exit(run())
