#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, json, glob
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="SCALP — Backtest Dashboard", layout="wide")

st.title("SCALP — Backtest Dashboard")

reports_dir = st.sidebar.text_input("Reports dir", "/notebooks/scalp_data/reports")
signals_root = os.path.join(reports_dir, "signals")

# Summary
summary_path = os.path.join(reports_dir, "summary.json")
if not os.path.isfile(summary_path):
    st.warning("summary.json introuvable. Lance `python jobs/backtest.py` d'abord.")
    st.stop()

with open(summary_path, "r", encoding="utf-8") as f:
    summary = json.load(f)
rows = pd.DataFrame(summary.get("rows", []))
if rows.empty:
    st.info("Aucun résultat en base."); st.stop()

# Filtres
pairs = sorted(rows["pair"].unique().tolist())
tfs = sorted(rows["tf"].unique().tolist())
col1, col2, col3, col4 = st.columns(4)
with col1:
    pair_sel = st.multiselect("Paires", pairs, default=pairs)
with col2:
    tf_sel = st.multiselect("TF", tfs, default=tfs)
with col3:
    pf_min = st.number_input("PF min", value=1.2, step=0.1)
with col4:
    mdd_max = st.number_input("MDD max", value=0.30, step=0.05, format="%.2f")

f = rows[
    rows["pair"].isin(pair_sel)
    & rows["tf"].isin(tf_sel)
    & (rows["pf"] >= pf_min)
    & (rows["mdd"] <= mdd_max)
].copy()

st.subheader("Tableau des résultats filtrés")
st.dataframe(f.sort_values(["pf","sharpe","mdd"], ascending=[False, False, True]), use_container_width=True)

# Heatmap PF par paire/TF
st.subheader("Heatmap PF par paire / TF")
if not f.empty:
    pivot_pf = f.pivot_table(index="pair", columns="tf", values="pf", aggfunc="max")
    fig = px.imshow(pivot_pf, aspect="auto", color_continuous_scale="Viridis", origin="lower")
    st.plotly_chart(fig, use_container_width=True)

# Sélection pour signaux
st.subheader("Signaux & probas (p_buy) — Parquet")
pair_view = st.selectbox("Paire", pairs)
tf_view = st.selectbox("TF", tfs)
parquet_path = os.path.join(signals_root, pair_view, f"{tf_view}.parquet")
csv_fallback = os.path.join(signals_root, pair_view, f"{tf_view}.csv")

if os.path.isfile(parquet_path) or os.path.isfile(csv_fallback):
    if os.path.isfile(parquet_path):
        sig = pd.read_parquet(parquet_path)
    else:
        sig = pd.read_csv(csv_fallback)

    sig["dt"] = pd.to_datetime(sig["timestamp"], unit="ms", utc=True).dt.tz_convert("UTC")
    st.write(f"Fichier: {parquet_path if os.path.isfile(parquet_path) else csv_fallback} — {len(sig)} lignes")

    cols = st.multiselect("Colonnes à afficher", ["p_buy","state","entry_long","entry_set","close","sl","tp"], default=["p_buy","entry_long","close"])
    st.dataframe(sig[["dt"] + cols].tail(500), use_container_width=True)

    # Chart p_buy & close
    left, right = st.columns([2,1])
    with left:
        fig = px.line(sig.tail(2000), x="dt", y=["p_buy","close"], title="p_buy & close (échantillon)")
        st.plotly_chart(fig, use_container_width=True)
    with right:
        # distribution p_buy
        figh = px.histogram(sig, x="p_buy", nbins=30, title="Distribution p_buy")
        st.plotly_chart(figh, use_container_width=True)
else:
    st.info("Aucun fichier de signaux pour cette paire/TF. Active l'export dans backtest (--export-signals).")