#!/usr/bin/env python3
"""Interactive dashboard for the World Cup 2026 Dixon-Coles predictor.

Streamlit app with two focus views:

  1. "Carrera por el título" — Monte Carlo probabilities (advance / semifinal /
     champion) per nation, updating as results come in.
  2. "Predicción por partido" — most likely score, top-3 scorelines, P(W/D/L)
     and the full score-probability heatmap for any fixture.

The app reads the artefacts produced by the pipeline (outputs/*.csv,
data/processed/*) and recomputes score matrices live from the fitted model, so
re-running `python update.py` during the tournament is reflected on reload.

Run locally:

    pip install -r requirements.txt
    python run_all.py            # produce model + outputs at least once
    python -m streamlit run dashboard.py
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import config as C
from src.model import DixonColesModel
from src.predict import score_matrix, load_fixtures_with_features

# --------------------------------------------------------------------------
# Data access (cached). Cache keys include file mtimes so a fresh update.py
# run invalidates them automatically.
# --------------------------------------------------------------------------
SIM_CSV = os.path.join(C.OUTPUTS_DIR, "tournament_simulation.csv")
PRED_CSV = os.path.join(C.OUTPUTS_DIR, "group_predictions.csv")


def _mtime(path: str) -> float:
    return os.path.getmtime(path) if os.path.exists(path) else 0.0


@st.cache_data
def load_simulation(_mt: float) -> pd.DataFrame:
    return pd.read_csv(SIM_CSV)


@st.cache_data
def load_group_predictions(_mt: float) -> pd.DataFrame:
    return pd.read_csv(PRED_CSV)


@st.cache_data
def load_fixtures(_mt: float) -> pd.DataFrame:
    return load_fixtures_with_features()


@st.cache_resource
def load_model(_mt: float) -> DixonColesModel:
    return DixonColesModel.load()


def artefacts_present() -> bool:
    return all(os.path.exists(p) for p in
               (SIM_CSV, PRED_CSV, C.PARAMS_JSON, C.FIXTURES_CSV))


# --------------------------------------------------------------------------
# Views
# --------------------------------------------------------------------------
def view_title_race(sim: pd.DataFrame):
    st.subheader("🏆 Carrera por el título")
    st.caption("Probabilidades estimadas por simulación Monte Carlo "
               f"({C.N_SIMULATIONS:,} torneos).")

    metric_label = {
        "p_champion": "Campeón",
        "p_semifinal": "Llegar a semifinales",
        "p_advance": "Pasar de grupo",
    }
    col1, col2 = st.columns([1, 1])
    with col1:
        metric = st.selectbox("Métrica", list(metric_label),
                              format_func=lambda k: metric_label[k])
    with col2:
        top_n = st.slider("Número de selecciones", 5, len(sim), 16)

    ranked = sim.sort_values(metric, ascending=False).head(top_n).copy()
    ranked = ranked.iloc[::-1]  # plotly horizontal bars read bottom-up

    fig = px.bar(
        ranked, x=metric, y="team", orientation="h",
        color=metric, color_continuous_scale="Tealgrn",
        labels={metric: metric_label[metric], "team": ""},
        text=ranked[metric].map(lambda v: f"{v:.1%}"),
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        xaxis_tickformat=".0%", coloraxis_showscale=False,
        height=max(350, 26 * top_n), margin=dict(l=10, r=30, t=10, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Tabla completa")
    show = sim.sort_values("p_champion", ascending=False).copy()
    for c in ("p_advance", "p_semifinal", "p_champion"):
        show[c] = (show[c] * 100).round(1)
    show = show.rename(columns={
        "team": "Selección", "group": "Grupo",
        "p_advance": "Pasar grupo (%)", "p_semifinal": "Semis (%)",
        "p_champion": "Campeón (%)"})
    st.dataframe(show, use_container_width=True, hide_index=True)


def view_match(preds: pd.DataFrame, fixtures: pd.DataFrame,
               model: DixonColesModel):
    st.subheader("⚽ Predicción por partido")

    groups = sorted(preds["group"].dropna().unique())
    col1, col2 = st.columns([1, 2])
    with col1:
        group = st.selectbox("Grupo", groups)
    gmatches = preds[preds["group"] == group].reset_index(drop=True)
    labels = [f"{r.home} vs {r.away}" for r in gmatches.itertuples()]
    with col2:
        pick = st.selectbox("Partido", range(len(labels)),
                            format_func=lambda i: labels[i])
    row = gmatches.iloc[pick]
    home, away = row["home"], row["away"]

    # Locate fixture features (home_adv, delta_elo) and any played result.
    fx = fixtures[(fixtures["home_team"] == home)
                  & (fixtures["away_team"] == away)]
    fx = fx.iloc[0] if len(fx) else None
    home_adv = float(fx["home_adv"]) if fx is not None else 0.0
    delta_elo = float(fx["delta_elo"]) if fx is not None else 0.0

    # Headline metrics.
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Marcador más probable", row["most_likely"])
    c2.metric(f"Gana {home}", f"{row['p_home_win']:.0%}")
    c3.metric("Empate", f"{row['p_draw']:.0%}")
    c4.metric(f"Gana {away}", f"{row['p_away_win']:.0%}")

    if fx is not None and pd.notna(fx.get("home_score")):
        st.success(f"Resultado real: {home} {int(fx['home_score'])}–"
                   f"{int(fx['away_score'])} {away}")

    left, right = st.columns([1, 1])
    with left:
        st.markdown("#### Top-3 marcadores")
        st.markdown(f"- **{row['top1']}**\n- {row['top2']}\n- {row['top3']}")
        st.caption(f"Goles esperados (λ): {home} {row['lambda_home']:.2f} · "
                   f"{away} {row['lambda_away']:.2f}")

    with right:
        st.markdown("#### Matriz de probabilidad de marcador")
        mat = score_matrix(model, home, away, home_adv, delta_elo)
        n = 7  # display up to 6-6
        sub = mat[:n, :n]
        fig = go.Figure(data=go.Heatmap(
            z=sub * 100,
            x=[str(i) for i in range(n)],
            y=[str(i) for i in range(n)],
            colorscale="Tealgrn",
            colorbar=dict(title="%"),
            hovertemplate=(f"{home} %{{y}} – %{{x}} {away}"
                           "<br>%{z:.1f}%<extra></extra>"),
        ))
        fig.update_layout(
            xaxis_title=f"Goles {away}", yaxis_title=f"Goles {home}",
            yaxis_autorange="reversed", height=380,
            margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)


# --------------------------------------------------------------------------
# App
# --------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="Mundial 2026 · Predicciones",
                       page_icon="⚽", layout="wide")
    st.title("⚽ Mundial 2026 — Predicciones Dixon-Coles")

    if not artefacts_present():
        st.error("Faltan artefactos del modelo. Ejecuta primero:\n\n"
                 "```bash\npython run_all.py\n```")
        st.stop()

    sim = load_simulation(_mtime(SIM_CSV))
    preds = load_group_predictions(_mtime(PRED_CSV))
    fixtures = load_fixtures(_mtime(C.FIXTURES_CSV))
    model = load_model(_mtime(C.PARAMS_JSON))

    # Tournament progress header.
    played = fixtures["home_score"].notna().sum()
    total = len(fixtures)
    with st.sidebar:
        st.header("Estado del torneo")
        st.metric("Partidos de grupo jugados", f"{int(played)}/{total}")
        st.progress(played / total if total else 0.0)
        st.caption("Corre `python update.py` cada día para reingerir "
                   "resultados, reestimar el modelo y regenerar las "
                   "predicciones; luego recarga esta página.")
        if st.button("🔄 Recargar datos"):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.rerun()

    tab1, tab2 = st.tabs(["🏆 Carrera por el título", "⚽ Predicción por partido"])
    with tab1:
        view_title_race(sim)
    with tab2:
        view_match(preds, fixtures, model)


if __name__ == "__main__":
    main()
