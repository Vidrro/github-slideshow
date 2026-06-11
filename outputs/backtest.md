# Backtest: Dixon-Coles vs naive baseline

Lower RPS / Brier is better. The model is trained only on matches predating each tournament (no leakage). The naive baseline always predicts a 1-1 draw.

| Tournament | Matches | Model RPS | Baseline RPS | Model Brier | Baseline Brier | Market RPS |
|---|---|---|---|---|---|---|
| Qatar 2022 | 64 | 0.2238 | 0.3828 | 0.6262 | 1.5312 | n/a |
| Euro 2024 | 51 | 0.1922 | 0.3333 | 0.6004 | 1.3333 | n/a |

_A market-odds benchmark is computed automatically when a `data/raw/odds.csv` export (the-odds-api format) is present._