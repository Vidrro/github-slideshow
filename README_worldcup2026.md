# World Cup 2026 score predictor — Dixon-Coles

A Python project that predicts scorelines and tournament outcomes for the 2026
FIFA World Cup (11 June 2026; Mexico / USA / Canada) using a **weighted
Dixon-Coles bivariate Poisson** model, refittable daily as results come in.

## Quick start

```bash
pip install -r requirements.txt
python run_all.py          # ingest → features → model → predict → backtest
```

### Windows / PowerShell (un solo paso)

Si el proyecto aún no está en tu PC, primero clónalo y entra a la carpeta:

```powershell
cd D:\Downloads\ClaudeCodeTest
git clone --branch claude/world-cup-2026-predictions-95bmpj https://github.com/Vidrro/github-slideshow.git
cd github-slideshow
```

Luego ejecuta el script de arranque. Crea un entorno aislado (`.venv`), instala
las dependencias, corre la pipeline y abre el dashboard — y **siempre se ejecuta
desde la carpeta correcta**, así que no verás errores de "No such file":

```powershell
.\setup.ps1
```

Si PowerShell bloquea el script por la política de ejecución:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

Scripts auxiliares (también a prueba de la carpeta de trabajo):

| Script | Qué hace |
|---|---|
| `.\setup.ps1` | Instala todo, corre la pipeline y lanza el dashboard (primera vez) |
| `.\dashboard.ps1` | Solo abre el dashboard |
| `.\update.ps1` | Actualización diaria: reingiere resultados y regenera predicciones |


Outputs land in `outputs/`:

| File | Contents |
|---|---|
| `predictions.md` | Human-readable summary (opening day, title race, all matches) |
| `group_predictions.csv` | Per-match most-likely score, top-3 scores, P(W/D/L) |
| `tournament_simulation.csv` | P(advance), P(semifinal), P(champion) per team |
| `backtest.csv` / `backtest.md` | RPS & Brier vs Qatar 2022 / Euro 2024 |

During the tournament, run the daily refresh:

```bash
python update.py           # re-ingest results, refit, regenerate pending forecasts
```

## Interactive dashboard

A Streamlit dashboard visualises the forecasts and updates as the tournament
progresses:

```bash
python run_all.py                    # produce the model + outputs at least once
python -m streamlit run dashboard.py
```

(The `python -m streamlit` form works even when the `streamlit` script is not
on PATH — a common situation on Windows/PowerShell. The commands are identical
in PowerShell, cmd and bash.)

Three views:

- **Próximos partidos** — the upcoming group-stage fixtures with their most
  likely scoreline, possible scores (top-3) and P(win/draw/loss). Matches drop
  off the list as they are played.
- **Carrera por el título** — Monte Carlo probabilities (advance / semifinal /
  champion) per nation, as sortable bar charts and a full table.
- **Predicción por partido** — pick any fixture to see the most likely score,
  the top-3 scorelines, P(win/draw/loss), and the full score-probability
  heatmap. Played matches show the real result alongside the forecast.

### Public deployment (open from any PC)

The app self-bootstraps: on a fresh host with no model artefacts it downloads
the data, fits the model and generates predictions on first load. That makes it
deployable to **Streamlit Community Cloud** (free, always-on public URL) in a
few clicks:

1. Sign in at <https://share.streamlit.io> with the GitHub account that owns
   this repo.
2. **Create app → Deploy a public app from GitHub**.
3. Repository `Vidrro/github-slideshow`, branch
   `claude/world-cup-2026-predictions-95bmpj`, main file `dashboard.py`.
4. **Deploy**. After the first build you get a permanent URL like
   `https://<tu-app>.streamlit.app`, reachable from any device.

To redeploy daily numbers without local work, run `python update.py` (or
`.\update.ps1`), commit and push `outputs/`; Streamlit Cloud redeploys on push.

**Instant temporary link** (your PC must stay on): with the dashboard running on
port 8501, expose it with a tunnel, e.g. `npx localtunnel --port 8501` or
`cloudflared tunnel --url http://localhost:8501`.

The sidebar tracks group-stage progress (matches played) and offers a reload
button. After running `python update.py` each day, reload the page to see the
refreshed numbers — the cache is keyed on the output files' modification time.

## The model

For a match between home team *i* and away team *j*:

```
log(λ_home) = μ + attack_i − defense_j + γ·home + β·ΔElo
log(λ_away) = μ + attack_j − defense_i           − β·ΔElo
```

- **Goals** are Poisson with the **Dixon-Coles** low-score dependence
  correction `τ_ρ` on the 0-0, 1-0, 0-1 and 1-1 cells.
- **Exponential time weighting** (half-life ≈ 2 years) so recent matches
  dominate; only matches since 2018 are used.
- **Home advantage** `γ` applies only on non-neutral venues — i.e. Mexico, the
  USA and Canada in their own stadiums; everyone else plays neutral.
- **ΔElo** is each team's pre-match Elo gap, computed from full match history.
- Fitted by **maximum likelihood** (`scipy.optimize`, L-BFGS-B with an analytic
  gradient) with ridge shrinkage on team strengths and a sum-to-zero constraint.

## Pipeline stages (`src/`)

| Module | Role |
|---|---|
| `ingest.py` | Download/clean the martj42 results dataset; best-effort Elo/FIFA/odds; infer the 12 groups from the fixture graph |
| `features.py` | Compute running Elo; build the time-weighted, Elo-augmented training frame |
| `model.py` | Dixon-Coles MLE (value + analytic gradient) |
| `predict.py` | Score matrices, match reports, 10,000-tournament Monte Carlo |
| `backtest.py` | RPS / Brier vs Qatar 2022 & Euro 2024 and a naive 1-1 baseline |

## Data sources

1. **martj42 "International football results 1872–present"** — the dataset
   published on Kaggle, mirrored on GitHub raw (used directly so no Kaggle API
   key is required). It already ships the 72 WC2026 group fixtures.
2. **eloratings.net** — scraped best-effort; the site blocks bots (HTTP 403)
   from most CI/sandbox environments, so the model derives its own Elo from
   match history as a robust fallback. The scraper activates automatically
   wherever the site is reachable.
3. **FIFA ranking** — optional drop-in at `data/raw/fifa_ranking.csv`.
4. **Betting odds** — optional drop-in at `data/raw/odds.csv` (the-odds-api
   1X2 export). When present, `backtest.py` reports a market-odds RPS/Brier
   benchmark automatically.

## Backtest results

Trained only on pre-tournament data (no leakage), 1X2 forecasts scored by
Ranked Probability Score (lower is better):

| Tournament | Matches | Model RPS | Baseline (1-1) RPS |
|---|---|---|---|
| Qatar 2022 | 64 | ~0.22 | ~0.38 |
| Euro 2024 | 51 | ~0.19 | ~0.33 |

The model comfortably beats the naive baseline and lands in the range of
published bookmaker-grade forecasts.

## Notes & simplifications

- The knockout bracket snake-seeds the 32 qualifiers (12 winners, 12
  runners-up, 8 best third-placed teams) by group-stage performance, rather
  than reproducing FIFA's exact third-place-combination slotting table. This is
  a transparent stand-in that keeps the advancement probabilities sound.
- Knockout ties are treated as neutral-venue; draws are resolved ~50/50
  (penalties).
- Group ranking uses points → goal difference → goals for → drawing of lots.
