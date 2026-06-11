"""Stage 3 - Dixon-Coles bivariate Poisson model (maximum likelihood).

Goal model
----------
For a match between home team i and away team j:

    log(lambda_home) = mu + attack_i - defense_j + gamma * home_adv + beta * dElo
    log(lambda_away) = mu + attack_j - defense_i                    - beta * dElo

where `home_adv` is 1 only when the home side truly plays at home (non-neutral),
`dElo` is the pre-match Elo difference (home - away) / 100, and goals are
Poisson with the Dixon-Coles low-score dependence correction tau_rho applied to
the (0-0, 1-0, 0-1, 1-1) cells.

The log-likelihood is weighted by the exponential time weights from
features.py, so recent matches dominate. Attacks are made identifiable with a
sum-to-zero penalty.

Run as a script:

    python -m src.model
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import gammaln

from . import config as C


# --------------------------------------------------------------------------
# Dixon-Coles low-score correction
# --------------------------------------------------------------------------
def dc_tau(home_goals, away_goals, lam_home, lam_away, rho):
    """Vectorised tau_rho correction factor (Dixon & Coles, 1997)."""
    hg = np.asarray(home_goals)
    ag = np.asarray(away_goals)
    tau = np.ones(np.broadcast(hg, ag, lam_home, lam_away).shape, dtype=float)

    m00 = (hg == 0) & (ag == 0)
    m01 = (hg == 0) & (ag == 1)
    m10 = (hg == 1) & (ag == 0)
    m11 = (hg == 1) & (ag == 1)

    lh = np.broadcast_to(lam_home, tau.shape)
    la = np.broadcast_to(lam_away, tau.shape)

    tau = np.where(m00, 1.0 - lh * la * rho, tau)
    tau = np.where(m01, 1.0 + lh * rho, tau)
    tau = np.where(m10, 1.0 + la * rho, tau)
    tau = np.where(m11, 1.0 - rho, tau)
    return tau


def _poisson_logpmf(k, lam):
    return k * np.log(lam) - lam - gammaln(k + 1.0)


# --------------------------------------------------------------------------
# Model
# --------------------------------------------------------------------------
class DixonColesModel:
    def __init__(self, teams: list[str]):
        self.teams = list(teams)
        self.index = {t: i for i, t in enumerate(self.teams)}
        self.n = len(self.teams)
        self.params: dict | None = None  # filled after fit/load

    # ---- parameter packing ------------------------------------------------
    def _unpack(self, theta):
        n = self.n
        attack = theta[:n]
        defense = theta[n:2 * n]
        rho, gamma, beta, mu = theta[2 * n:2 * n + 4]
        return attack, defense, rho, gamma, beta, mu

    def _lambdas(self, attack, defense, gamma, beta, mu, hi, ai, home_adv, delta_elo):
        log_lh = mu + attack[hi] - defense[ai] + gamma * home_adv + beta * delta_elo
        log_la = mu + attack[ai] - defense[hi] - beta * delta_elo
        return np.exp(log_lh), np.exp(log_la)

    # ---- objective (value + analytic gradient) ----------------------------
    def _neg_loglik(self, theta, hi, ai, hg, ag, home_adv, delta_elo, weight):
        n = self.n
        attack, defense, rho, gamma, beta, mu = self._unpack(theta)
        lam_h, lam_a = self._lambdas(attack, defense, gamma, beta, mu,
                                     hi, ai, home_adv, delta_elo)

        tau = dc_tau(hg, ag, lam_h, lam_a, rho)
        tau = np.clip(tau, 1e-10, None)  # guard against non-positive tau

        ll = (_poisson_logpmf(hg, lam_h)
              + _poisson_logpmf(ag, lam_a)
              + np.log(tau))
        wll = np.sum(weight * ll)

        sum_att, sum_def = attack.sum(), defense.sum()
        penalty = 1e3 * (sum_att ** 2 + sum_def ** 2)
        ridge = C.L2_REG * (np.sum(attack ** 2) + np.sum(defense ** 2))
        nll = -wll + penalty + ridge

        # ---- gradient -----------------------------------------------------
        # d tau / d{lam_h, lam_a, rho} per match (nonzero only in low cells).
        dtau_dlh = np.zeros_like(tau)
        dtau_dla = np.zeros_like(tau)
        dtau_drho = np.zeros_like(tau)
        m00 = (hg == 0) & (ag == 0)
        m01 = (hg == 0) & (ag == 1)
        m10 = (hg == 1) & (ag == 0)
        m11 = (hg == 1) & (ag == 1)
        dtau_dlh[m00] = -lam_a[m00] * rho
        dtau_dla[m00] = -lam_h[m00] * rho
        dtau_drho[m00] = -lam_h[m00] * lam_a[m00]
        dtau_dlh[m01] = rho
        dtau_drho[m01] = lam_h[m01]
        dtau_dla[m10] = rho
        dtau_drho[m10] = lam_a[m10]
        dtau_drho[m11] = -1.0

        # d loglik / d eta_home, d eta_away  (eta = log lambda)
        g_eta_h = weight * ((hg - lam_h) + lam_h / tau * dtau_dlh)
        g_eta_a = weight * ((ag - lam_a) + lam_a / tau * dtau_dla)
        g_rho = np.sum(weight * dtau_drho / tau)

        grad = np.zeros_like(theta)
        # attack_k: +g_eta_h where home, +g_eta_a where away
        np.add.at(grad, hi, g_eta_h)
        np.add.at(grad, ai, g_eta_a)
        # defense_k: -g_eta_h where away (def_j enters eta_h with -1),
        #            -g_eta_a where home (def_i enters eta_a with -1)
        np.add.at(grad, n + ai, -g_eta_h)
        np.add.at(grad, n + hi, -g_eta_a)
        grad[2 * n + 0] = g_rho                                  # rho
        grad[2 * n + 1] = np.sum(g_eta_h * home_adv)             # gamma
        grad[2 * n + 2] = np.sum(g_eta_h * delta_elo
                                 - g_eta_a * delta_elo)          # beta
        grad[2 * n + 3] = np.sum(g_eta_h + g_eta_a)              # mu

        # These are gradients of +loglik; objective uses -loglik.
        grad = -grad
        # Penalty + ridge gradients (apply to attack/defense blocks).
        grad[:n] += 2e3 * sum_att + 2 * C.L2_REG * attack
        grad[n:2 * n] += 2e3 * sum_def + 2 * C.L2_REG * defense

        return nll, grad

    # ---- fitting ----------------------------------------------------------
    def fit(self, train: pd.DataFrame, verbose: bool = True) -> "DixonColesModel":
        hi = train["home_team"].map(self.index).to_numpy()
        ai = train["away_team"].map(self.index).to_numpy()
        hg = train["home_score"].to_numpy(dtype=float)
        ag = train["away_score"].to_numpy(dtype=float)
        home_adv = train["home_adv"].to_numpy(dtype=float)
        delta_elo = train["delta_elo"].to_numpy(dtype=float)
        weight = train["weight"].to_numpy(dtype=float)

        n = self.n
        # Init: attacks/defenses from team mean goals, mild priors elsewhere.
        theta0 = np.zeros(2 * n + 4)
        theta0[2 * n + 0] = -0.05   # rho
        theta0[2 * n + 1] = 0.25    # gamma (home advantage)
        theta0[2 * n + 2] = 0.10    # beta  (Elo coefficient)
        theta0[2 * n + 3] = np.log(max(hg.mean(), 0.1))  # mu intercept

        bounds = (
            [(-3, 3)] * n          # attack
            + [(-3, 3)] * n        # defense
            + [(-0.2, 0.2)]        # rho (DC correction is small)
            + [(-1.0, 1.0)]        # gamma
            + [(-1.0, 1.0)]        # beta
            + [(-2.0, 2.0)]        # mu
        )

        res = minimize(
            self._neg_loglik,
            theta0,
            args=(hi, ai, hg, ag, home_adv, delta_elo, weight),
            method="L-BFGS-B",
            jac=True,  # _neg_loglik returns (value, gradient)
            bounds=bounds,
            options={"maxiter": 5000, "maxfun": 50000, "ftol": 1e-10,
                     "gtol": 1e-6},
        )

        attack, defense, rho, gamma, beta, mu = self._unpack(res.x)
        # Re-center so attacks/defenses sum exactly to zero.
        attack = attack - attack.mean()
        defense = defense - defense.mean()

        self.params = {
            "teams": self.teams,
            "attack": dict(zip(self.teams, attack.tolist())),
            "defense": dict(zip(self.teams, defense.tolist())),
            "rho": float(rho),
            "gamma": float(gamma),
            "beta": float(beta),
            "mu": float(mu),
            "neg_loglik": float(res.fun),
            "converged": bool(res.success),
            "n_matches": int(len(train)),
        }
        if verbose:
            print(f"  converged={res.success}  nll={res.fun:.1f}  "
                  f"gamma(home)={gamma:.3f}  beta(elo)={beta:.3f}  "
                  f"rho(DC)={rho:.3f}  mu={mu:.3f}")
        return self

    # ---- persistence ------------------------------------------------------
    def save(self, path: str = C.PARAMS_JSON):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.params, fh, indent=2)

    @classmethod
    def load(cls, path: str = C.PARAMS_JSON) -> "DixonColesModel":
        with open(path, encoding="utf-8") as fh:
            p = json.load(fh)
        m = cls(p["teams"])
        m.params = p
        return m

    # ---- prediction primitives -------------------------------------------
    def expected_goals(self, home: str, away: str, home_adv: float,
                       delta_elo: float) -> tuple[float, float]:
        """Return (lambda_home, lambda_away) for a fixture.

        Unknown teams fall back to a league-average (attack=defense=0) team.
        """
        p = self.params
        a = p["attack"]
        d = p["defense"]
        ah = a.get(home, 0.0)
        aa = a.get(away, 0.0)
        dh = d.get(home, 0.0)
        da = d.get(away, 0.0)
        log_lh = p["mu"] + ah - da + p["gamma"] * home_adv + p["beta"] * delta_elo
        log_la = p["mu"] + aa - dh - p["beta"] * delta_elo
        return float(np.exp(log_lh)), float(np.exp(log_la))


def run() -> int:
    print("=" * 70)
    print("STAGE 3: MODEL (Dixon-Coles MLE)")
    print("=" * 70)
    train = pd.read_csv(C.TRAINING_CSV, parse_dates=["date"])
    teams = sorted(set(train["home_team"]) | set(train["away_team"]))
    print(f"Fitting on {len(train):,} matches, {len(teams)} teams...")

    model = DixonColesModel(teams).fit(train)
    model.save()

    # Quick sanity: strongest attacks & defenses.
    att = pd.Series(model.params["attack"]).sort_values(ascending=False)
    dfn = pd.Series(model.params["defense"]).sort_values(ascending=False)
    print("\nTop-8 attack strength:")
    print(att.head(8).to_string())
    print("\nTop-8 defense strength (higher = concedes fewer):")
    print(dfn.head(8).to_string())
    print(f"\nWrote {C.PARAMS_JSON}")
    print("Stage 3 complete.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
