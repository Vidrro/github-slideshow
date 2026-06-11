#!/usr/bin/env python3
"""End-to-end pipeline: ingest -> features -> model -> predict -> backtest.

Usage:
    python run_all.py            # full pipeline
    python run_all.py --no-backtest
"""
from __future__ import annotations

import sys

from src import ingest, features, model as model_mod, predict, backtest


def main(argv: list[str]) -> int:
    for stage in (ingest.run, features.run, model_mod.run, predict.run):
        rc = stage()
        if rc != 0:
            print(f"Pipeline halted at {stage.__module__} (rc={rc}).")
            return rc
    if "--no-backtest" not in argv:
        backtest.run()
    print("\nAll stages complete. See outputs/ for predictions and backtest.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
