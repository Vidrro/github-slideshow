"""Stage 1 - Data ingestion and cleaning.

Primary source is the martj42 international-results dataset (the one published
on Kaggle and mirrored on GitHub raw).  We also *attempt* to enrich with live
Elo ratings from eloratings.net and a current FIFA ranking, but those sites are
frequently unreachable from sandboxed/CI environments (they return HTTP 403 to
non-browser clients).  When that happens we degrade gracefully: the model
derives its own Elo ratings from match history in `features.py`, so the
pipeline never hard-fails on a blocked enrichment source.

Run as a script to (re)download everything:

    python -m src.ingest
"""
from __future__ import annotations

import io
import sys
import time

import pandas as pd
import requests

from . import config as C

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _download(url: str, dest: str, retries: int = 4) -> bool:
    """Download `url` to `dest` with exponential backoff. Returns success."""
    delay = 2.0
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=60)
            resp.raise_for_status()
            with open(dest, "wb") as fh:
                fh.write(resp.content)
            print(f"  [ok]   {url} -> {dest} ({len(resp.content):,} bytes)")
            return True
        except Exception as exc:  # noqa: BLE001 - we want to keep going
            print(f"  [warn] attempt {attempt}/{retries} failed for {url}: {exc}")
            if attempt < retries:
                time.sleep(delay)
                delay *= 2
    print(f"  [skip] giving up on {url}")
    return False


# --------------------------------------------------------------------------
# 1. Match results (required)
# --------------------------------------------------------------------------
def download_results() -> bool:
    """Download results / shootouts / goalscorers from the martj42 mirror."""
    print("Downloading match results (martj42)...")
    ok = _download(C.RESULTS_URL, C.RESULTS_CSV)
    # The auxiliary files are nice-to-have, not required.
    _download(C.SHOOTOUTS_URL, C.SHOOTOUTS_CSV)
    _download(C.GOALSCORERS_URL, C.GOALSCORERS_CSV)
    return ok


def load_results() -> pd.DataFrame:
    """Load and lightly clean the results table."""
    df = pd.read_csv(C.RESULTS_CSV)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    # `neutral` arrives as the strings TRUE/FALSE.
    df["neutral"] = (
        df["neutral"].astype(str).str.upper().map({"TRUE": True, "FALSE": False})
    )
    for col in ("home_score", "away_score"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["date", "home_team", "away_team"])
    # Canonicalise a few team names so history and fixtures line up.
    df["home_team"] = df["home_team"].map(canonical_team)
    df["away_team"] = df["away_team"].map(canonical_team)
    return df.sort_values("date").reset_index(drop=True)


# A handful of countries appear under different names across decades; keep the
# names that the 2026 fixtures use.
_TEAM_ALIASES = {
    "Czechoslovakia": "Czech Republic",
    "Korea Republic": "South Korea",
    "Korea DPR": "North Korea",
    "IR Iran": "Iran",
    "Türkiye": "Turkey",
    "China PR": "China",
    "USA": "United States",
    "Cabo Verde": "Cape Verde",
}


def canonical_team(name: str) -> str:
    if not isinstance(name, str):
        return name
    name = name.strip()
    return _TEAM_ALIASES.get(name, name)


# --------------------------------------------------------------------------
# 2. Elo ratings from eloratings.net (best-effort)
# --------------------------------------------------------------------------
def scrape_elo() -> pd.DataFrame | None:
    """Scrape the current world Elo table.

    eloratings.net renders its table from a JS blob, and also blocks non-browser
    clients.  We try the documented endpoints; on any failure we return None and
    the pipeline falls back to Elo computed from match history.
    """
    print("Attempting to scrape eloratings.net (best-effort)...")
    try:
        resp = requests.get(C.ELO_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        print(f"  [skip] eloratings.net unreachable ({exc}); will derive Elo "
              "from match history instead.")
        return None

    try:
        from bs4 import BeautifulSoup  # local import keeps bs4 optional

        soup = BeautifulSoup(resp.text, "html.parser")
        rows = []
        for tr in soup.select("table tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(cells) >= 3 and cells[2].replace(",", "").isdigit():
                rows.append({"team": canonical_team(cells[1]),
                             "elo": float(cells[2].replace(",", ""))})
        if not rows:
            print("  [skip] could not parse an Elo table from the response.")
            return None
        df = pd.DataFrame(rows)
        df.to_csv(C.ELO_CSV, index=False)
        print(f"  [ok]   scraped {len(df)} Elo ratings.")
        return df
    except Exception as exc:  # noqa: BLE001
        print(f"  [skip] failed to parse eloratings.net ({exc}).")
        return None


# --------------------------------------------------------------------------
# 3. FIFA ranking (best-effort)
# --------------------------------------------------------------------------
def load_fifa_ranking() -> pd.DataFrame | None:
    """Load a current FIFA ranking if one was placed in data/raw/fifa_ranking.csv.

    The official endpoint requires browser-like access; rather than ship a stale
    scrape we treat this as an optional drop-in file. The model does not depend
    on it (Elo carries the strength prior), so its absence is non-fatal.
    """
    import os

    if os.path.exists(C.FIFA_CSV):
        try:
            df = pd.read_csv(C.FIFA_CSV)
            print(f"  [ok]   loaded FIFA ranking ({len(df)} rows).")
            return df
        except Exception as exc:  # noqa: BLE001
            print(f"  [warn] could not read {C.FIFA_CSV}: {exc}")
    print("  [skip] no FIFA ranking file present (optional).")
    return None


# --------------------------------------------------------------------------
# 4. Betting odds (best-effort benchmark)
# --------------------------------------------------------------------------
def load_odds() -> pd.DataFrame | None:
    """Load 1X2 odds if present in data/raw/odds.csv (the-odds-api export).

    Used purely as a calibration benchmark in backtest.py. Optional.
    """
    import os

    if os.path.exists(C.ODDS_CSV):
        try:
            df = pd.read_csv(C.ODDS_CSV)
            print(f"  [ok]   loaded odds ({len(df)} rows).")
            return df
        except Exception as exc:  # noqa: BLE001
            print(f"  [warn] could not read {C.ODDS_CSV}: {exc}")
    print("  [skip] no odds file present (optional benchmark).")
    return None


# --------------------------------------------------------------------------
# 5. World Cup 2026 fixtures + group inference
# --------------------------------------------------------------------------
def extract_fixtures_and_groups(results: pd.DataFrame | None = None):
    """Pull the 72 group-stage fixtures of WC2026 and infer the 12 groups.

    The fixture list ships inside the results file with NA scores. The groups
    are recovered as connected components of the "played each other" graph: a
    group of four is a clique of 6 matches, so each component is exactly one
    group.
    """
    if results is None:
        results = load_results()

    mask = (
        (results["tournament"] == "FIFA World Cup")
        & (results["date"] >= "2026-06-01")
        & (results["date"] <= "2026-06-27")
    )
    fx = results[mask].copy()
    fx = fx.sort_values("date").reset_index(drop=True)

    # Connected components -> groups
    from collections import defaultdict

    adj: dict[str, set] = defaultdict(set)
    for _, r in fx.iterrows():
        adj[r["home_team"]].add(r["away_team"])
        adj[r["away_team"]].add(r["home_team"])

    seen: set[str] = set()
    components = []
    for team in adj:
        if team in seen:
            continue
        stack, comp = [team], set()
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x)
            comp.add(x)
            stack.extend(adj[x] - seen)
        components.append(sorted(comp))

    components.sort()  # alphabetical, gives stable A,B,C... labels
    group_rows = []
    team_to_group = {}
    for i, comp in enumerate(components):
        label = chr(ord("A") + i)
        for t in comp:
            group_rows.append({"group": label, "team": t})
            team_to_group[t] = label
    groups_df = pd.DataFrame(group_rows)
    fx["group"] = fx["home_team"].map(team_to_group)

    keep = ["date", "home_team", "away_team", "home_score", "away_score",
            "city", "country", "neutral", "group"]
    fx[keep].to_csv(C.FIXTURES_CSV, index=False)
    groups_df.to_csv(C.GROUPS_CSV, index=False)
    print(f"  [ok]   {len(fx)} fixtures, {len(components)} groups -> "
          f"{C.FIXTURES_CSV}, {C.GROUPS_CSV}")
    return fx[keep], groups_df


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------
def run() -> int:
    print("=" * 70)
    print("STAGE 1: INGEST")
    print("=" * 70)
    if not download_results():
        print("FATAL: could not download the core results dataset.")
        return 1

    results = load_results()
    print(f"Loaded {len(results):,} matches "
          f"({results['date'].min().date()} .. {results['date'].max().date()})")

    scrape_elo()          # optional
    load_fifa_ranking()   # optional
    load_odds()           # optional

    fx, groups = extract_fixtures_and_groups(results)
    n_played = fx["home_score"].notna().sum()
    print(f"WC2026: {len(fx)} group fixtures, {n_played} already played.")
    print("Stage 1 complete.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
