# dash/app.py
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st

# ---------- config & chemins ----------
def _load_config_paths() -> Dict[str, str]:
    try:
        # on lit la config du moteur si dispo
        from engine.config.loader import load_config
        cfg = load_config()
        r = cfg.get("runtime", {})
        return {
            "DATA_DIR": r.get("data_dir") or "/notebooks/scalp_data/data",
            "REPORTS_DIR": r.get("reports_dir") or "/notebooks/scalp_data/reports",
        }
    except Exception:
        root = os.getenv("DATA_ROOT", "/notebooks/scalp_data")
        return {
            "DATA_DIR": str(Path(root) / "data"),
            "REPORTS_DIR": str(Path(root) / "reports"),
        }

PATHS = _load_config_paths()

def p_live() -> Path: return Path(PATHS["DATA_DIR"]) / "live"
def p_orders() -> Path: return p_live() / "orders.csv"
def p_signals() -> Path: return p_live() / "logs" / "signals.csv"
def p_watchlist() -> Path: return Path(PATHS["REPORTS_DIR"]) / "watchlist.yml"
def p_strategies() -> Path: return Path(__file__).resolve().parents[1] / "engine" / "config" / "strategies.yml"
def p_summary() -> Path: return Path(PATHS["REPORTS_DIR"]) / "summary.json"

# ---------- helpers IO ----------
@st.cache_data(show_spinner=False)
def load_json_file(path: Path) -> Dict:
    if not path.exists(): return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

@st.cache_data(show_spinner=False)
def load_csv_tail(path: Path, n: int = 1000) -> pd.DataFrame:
    if not path.exists(): return pd.DataFrame()
    try:
        # lecture efficace tail n lignes
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            block = 4096
            data = b""
            while len(data.splitlines()) <= n + 1 and f.tell() > 0:
                step = min(block, f.tell())
                f.seek(-step, os.SEEK_CUR)
                data = f.read(step) + data
                f.seek(-step, os.SEEK_CUR)
            s = data.decode("utf-8", errors="ignore")
        df = pd.read_csv(pd.compat.StringIO(s))
        return df.tail(n).reset_index(drop=True)
    except Exception:
        try:
            return pd.read_csv(path).tail(n).reset_index(drop=True)
        except Exception:
            return pd.DataFrame()

@st.cache_data(show_spinner=False)
def load_signals() -> pd.DataFrame:
    df = load_csv_tail(p_signals(), n=5000)
    if not df.empty:
        # ts en ms → datetime
        df["ts"] = pd.to_datetime(df["ts"], unit="ms")
    return df

@st.cache_data(show_spinner=False)
def load_orders() -> pd.DataFrame:
    df = load_csv_tail(p_orders(), n=2000)
    if not df.empty:
        df["ts"] = pd.to_datetime(df["ts"], unit="ms")
    return df

# ---------- UI ----------
st.set_page_config(page_title="Scalp Dashboard", layout="wide")
st.title("⚡ Scalp — Dashboard")

with st.sidebar:
    st.subheader("Paramètres")
    refresh_sec = st.number_input("Auto-refresh (sec)", min_value=0, max_value=120, value=10, step=1)
    if refresh_sec > 0:
        st.autorefresh = st.experimental_rerun  # alias doux
        st.experimental_set_query_params(_=int(pd.Timestamp.now().timestamp()))
        st.experimental_data_editor  # no-op; évite un warning IDE
        st.experimental_rerun  # pas déclenché ici; déclenché par autorefresh ci-dessous
        st.experimental_memo
        st_autorefresh = st.experimental_rerun
        st.empty()
    page = st.radio("Vue", ["Overview", "Watchlist", "Strategies", "Live: Signals", "Live: Orders"], index=0)

    st.caption(f"DATA_DIR: {PATHS['DATA_DIR']}")
    st.caption(f"REPORTS_DIR: {PATHS['REPORTS_DIR']}")

# déclencheur auto-refresh léger
if refresh_sec > 0:
    st.experimental_set_query_params(ts=int(pd.Timestamp.now().timestamp()))
    st_autorefresh_id = st.experimental_singleton(lambda: 0)
    st.experimental_rerun

# ---------- PAGES ----------
if page == "Overview":
    c1, c2, c3, c4 = st.columns(4)
    wl = load_json_file(p_watchlist())
    strat = load_json_file(p_strategies())
    sig = load_signals()
    ords = load_orders()

    c1.metric("Watchlist", len(wl.get("top", [])))
    c2.metric("Strategies", len((strat.get("strategies") or {})))
    c3.metric("Signals (tail)", len(sig))
    c4.metric("Orders (tail)", len(ords))

    st.markdown("### Fichiers")
    status = [
        ("watchlist.yml", p_watchlist(), p_watchlist().exists()),
        ("strategies.yml", p_strategies(), p_strategies().exists()),
        ("signals.csv", p_signals(), p_signals().exists()),
        ("orders.csv", p_orders(), p_orders().exists()),
        ("summary.json", p_summary(), p_summary().exists()),
    ]
    st.table(pd.DataFrame([{"file": n, "path": str(p), "exists": ok} for n, p, ok in status]))

    st.markdown("### Derniers signaux (aperçu)")
    st.dataframe(sig.tail(30), use_container_width=True)

elif page == "Watchlist":
    doc = load_json_file(p_watchlist())
    top = pd.DataFrame(doc.get("top", []))
    if top.empty:
        st.warning(f"Watchlist vide ou introuvable: {p_watchlist()}")
    else:
        top = top.sort_values("score", ascending=False).reset_index(drop=True)
        st.subheader("Top (score volume+volatilité)")
        st.dataframe(top, use_container_width=True)
        c1, c2 = st.columns(2)
        with c1:
            if {"symbol", "vol_usd_24h"}.issubset(top.columns):
                st.bar_chart(top.set_index("symbol")["vol_usd_24h"])
        with c2:
            if {"symbol", "atr_pct_24h"}.issubset(top.columns):
                st.bar_chart((top.set_index("symbol")["atr_pct_24h"] * 100).rename("ATR %"))

elif page == "Strategies":
    doc = load_json_file(p_strategies())
    strat = pd.DataFrame([
        {"pair_tf": k, **v} for k, v in (doc.get("strategies") or {}).items()
    ])
    if strat.empty:
        st.info("Aucune stratégie promue. Lance les jobs backtest + promote.")
    else:
        st.subheader("Stratégies promues (par pair:TF)")
        st.dataframe(strat.sort_values("pair_tf"), use_container_width=True)

elif page == "Live: Signals":
    df = load_signals()
    if df.empty:
        st.warning(f"Aucun signal (fichier introuvable ou vide): {p_signals()}")
    else:
        syms = sorted(df["symbol"].unique().tolist())
        sym = st.selectbox("Symbole", syms, index=0)
        tf = st.selectbox("Timeframe", sorted(df["tf"].unique().tolist()), index=0)
        d = df[(df["symbol"] == sym) & (df["tf"] == tf)].copy()
        d = d.sort_values("ts")
        st.line_chart(d.set_index("ts")["price"], height=300)
        st.dataframe(d.tail(200), use_container_width=True)

elif page == "Live: Orders":
    df = load_orders()
    if df.empty:
        st.info(f"Aucun ordre encore. (paper mode ?) Fichier: {p_orders()}")
    else:
        st.subheader("Journal des ordres")
        st.dataframe(df.tail(200), use_container_width=True)
        # stats rapides
        buys = (df["action"] == "BUY").sum()
        sells = (df["action"] == "SELL").sum()
        st.caption(f"BUY: {buys} • SELL: {sells}")

# pied de page
st.write("---")
st.caption("Scalp Dashboard • Streamlit • auto-refresh paramétrable • fichiers hors repo")