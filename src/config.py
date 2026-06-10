"""Shared configuration: paths, constants and model hyper-parameters.

Everything that more than one module needs to agree on lives here so the
pipeline (ingest -> features -> model -> predict/backtest/update) stays
consistent.
"""
from __future__ import annotations

import os

# --------------------------------------------------------------------------
# Filesystem layout
# --------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
OUTPUTS_DIR = os.path.join(ROOT, "outputs")

for _d in (RAW_DIR, PROCESSED_DIR, OUTPUTS_DIR):
    os.makedirs(_d, exist_ok=True)

# Raw data files
RESULTS_CSV = os.path.join(RAW_DIR, "results.csv")
SHOOTOUTS_CSV = os.path.join(RAW_DIR, "shootouts.csv")
GOALSCORERS_CSV = os.path.join(RAW_DIR, "goalscorers.csv")
ELO_CSV = os.path.join(RAW_DIR, "elo_ratings.csv")
FIFA_CSV = os.path.join(RAW_DIR, "fifa_ranking.csv")
ODDS_CSV = os.path.join(RAW_DIR, "odds.csv")

# Processed data files
TRAINING_CSV = os.path.join(PROCESSED_DIR, "training.csv")
ELO_HISTORY_CSV = os.path.join(PROCESSED_DIR, "elo_history.csv")
FIXTURES_CSV = os.path.join(PROCESSED_DIR, "fixtures_2026.csv")
GROUPS_CSV = os.path.join(PROCESSED_DIR, "groups_2026.csv")
PARAMS_JSON = os.path.join(PROCESSED_DIR, "model_params.json")

# --------------------------------------------------------------------------
# Data sources
# --------------------------------------------------------------------------
# martj42 "International football results from 1872 to present" (the dataset
# behind the Kaggle release).  Mirrored on GitHub raw, which is reachable
# without the Kaggle API.
MARTJ42_BASE = "https://raw.githubusercontent.com/martj42/international_results/master"
RESULTS_URL = f"{MARTJ42_BASE}/results.csv"
SHOOTOUTS_URL = f"{MARTJ42_BASE}/shootouts.csv"
GOALSCORERS_URL = f"{MARTJ42_BASE}/goalscorers.csv"

KAGGLE_DATASET = "martj42/international-football-results-from-1872-to-2017"
ELO_URL = "https://www.eloratings.net/"

# --------------------------------------------------------------------------
# Model hyper-parameters
# --------------------------------------------------------------------------
# Only use matches from this date onward for fitting (recent form / roster).
TRAIN_START = "2018-01-01"

# Exponential time weighting: a match `t` days old gets weight
#   w = 0.5 ** (t / HALF_LIFE_DAYS)
# Half-life of ~2 years per the spec.
HALF_LIFE_DAYS = 730.0

# Score matrix is truncated at this many goals per team.
MAX_GOALS = 10

# Ridge (L2) shrinkage on attack/defense strengths. The model carries a global
# Elo covariate (beta * dElo) that is collinear with team strength, and ~half of
# the 280+ teams have very few recent matches. Shrinking the per-team effects
# toward zero keeps sparse minnows from getting absurd estimates and makes the
# likelihood well-conditioned (so L-BFGS-B actually converges). Well-observed
# sides retain their signal.
L2_REG = 5.0

# The raw dataset mixes in non-FIFA/exotic sides (CONIFA, islands, one-off
# selections) that have a handful of matches and distort the fit. Keep only
# teams with at least this many matches in the training window. All 48 WC2026
# nations clear this easily.
MIN_TEAM_MATCHES = 20

# Hosts of the 2026 World Cup. They play as home (non-neutral) in their own
# venues; the fixture file already encodes this via the `neutral` flag, but we
# keep the set for reference and sanity checks.
HOST_TEAMS = {"Mexico", "United States", "Canada"}

# World Cup 2026 starts here; the inaugural matches are on this day.
TOURNAMENT_START = "2026-06-11"

# ELO model used to derive the dELO feature when scraping eloratings.net is not
# possible.  Standard Elo with goal-difference inflation.
ELO_INIT = 1500.0
ELO_K = 40.0
ELO_HOME_ADV = 65.0  # Elo points added to the home side before expectation
ELO_DECAY_TO_MEAN = 0.0  # no between-match regression by default

# Monte Carlo
N_SIMULATIONS = 10_000
RANDOM_SEED = 20260611
