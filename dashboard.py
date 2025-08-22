# dashboard.py
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd
import streamlit as st

# ------------------------------------------------------------
# Réglages
# ------------------------------------------------------------
LOG_DIR = Path("scalp/live/logs")  # emplacement des CSV créés par l'orchestrateur
REFRESH_SECS = 5                   # auto-refresh UI
MAX_ROWS_SHOW = 2000               # clamp mémoire


# ------------------------------------------------------------
# Utilitaires lecture robuste CSV
# ------------------------------------------------------------
def _safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
        # clamp pour éviter d’exploser en RAM si les logs deviennent énormes
        if len(df) > MAX_ROWS_SHOW:
            df = df.tail(MAX_ROWS_SHOW).reset_index(drop=True)
        return df
    except Exception:
        # fichier en cours d’écriture → on réessaiera au prochain tick
        return pd.DataFrame()


def load_logs() -> Dict[str, pd.DataFrame]:
    return {
        "signals": _safe_read_csv(LOG_DIR / "signals.csv"),
        "orders": _safe_read_csv(LOG_DIR / "orders.csv"),
        "fills": _safe_read_csv(LOG_DIR / "fills.csv"),
        "positions": _safe_read_csv(LOG_DIR / "positions.csv"),
    }


def _format_ts_ms_to_str(df: pd.DataFrame, col: str = "ts") -> pd.DataFrame:
    if col in df.columns:
        try:
            df[col] = pd.to_datetime(df[col], unit="ms")
        except Exception:
            try:
                df[col] = pd.to_datetime(df[col])
            except Exception:
                pass
    return df


# ------------------------------------------------------------
# Métriques & agrégats simples
# ------------------------------------------------------------
def compute_activity_metrics(df_orders: pd.DataFrame, df_fills: pd.DataFrame) -> Tuple[float, float, int]:
    """
    Retourne: (volume notionnel approx, fees cumulés, nb fills)
    - notionnel approx = somme(|price * qty|) sur les fills (indépendant du sens)
    - fees = somme(fee) si dispo
    """
    notional = 0.0
    fees = 0.0
    n_fills = 0

    if not df_fills.empty:
        # normalisation colonnes
        price_col = next((c for c in ["price", "fillPrice", "fill_px"] if c in df_fills.columns), None)
        qty_col = next((c for c in ["qty", "size", "fillQty", "fill_sz"] if c in df_fills.columns), None)
        fee_col = next((c for c in ["fee", "fillFee"] if c in df_fills.columns), None)

        if price_col and qty_col:
            notional = float((df_fills[price_col].abs() * df_fills[qty_col].abs()).sum())
            n_fills = int(len(df_fills))
        if fee_col:
            fees = float(df_fills[fee_col].fillna(0).sum())

    return notional, fees, n_fills


def last_positions_snapshot(df_positions: pd.DataFrame) -> pd.DataFrame:
    """Dernier état par symbole (state/qty/entry)."""
    if df_positions.empty:
        return df_positions
    df = df_positions.copy()
    df = _format_ts_ms_to_str(df, "ts")
    # on prend le dernier enregistrement par symbol
    last = df.sort_values("ts").groupby("symbol", as_index=False).tail(1)
    return last.sort_values("symbol").reset_index(drop=True)


def recent_signals(df_signals: pd.DataFrame, limit: int = 30) -> pd.DataFrame:
    if df_signals.empty:
        return df_signals
    df = df_signals.copy()
    df = _format_ts_ms_to_str(df, "ts")
    df = df.sort_values("ts", ascending=False).head(limit)
    return df.reset_index(drop=True)


def recent_orders(df_orders: pd.DataFrame, limit: int = 30) -> pd.DataFrame:
    if df_orders.empty:
        return df_orders
    df = df_orders.copy()
    df = _format_ts_ms_to_str(df, "ts")
    df = df.sort_values("ts", ascending=False).head(limit)
    # petites colonnes utiles en premier
    cols = [c for c in ["ts", "symbol", "side", "status", "price", "sl", "tp", "risk_pct", "order_id"] if c in df.columns]
    other = [c for c in df.columns if c not in cols]
    return df[cols + other]


def recent_fills(df_fills: pd.DataFrame, limit: int = 50) -> pd.DataFrame:
    if df_fills.empty:
        return df_fills
    df = df_fills.copy()
    df = _format_ts_ms_to_str(df, "ts")
    df = df.sort_values("ts", ascending=False).head(limit)
    cols = [c for c in ["ts", "symbol", "order_id", "trade_id", "price", "qty", "fee"] if c in df.columns]
    other = [c for c in df.columns if c not in cols]
    return df[cols + other]


# ------------------------------------------------------------
# UI
# ------------------------------------------------------------
st.set_page_config(page_title="ScalpBot Dashboard", layout="wide")
st.title("📊 ScalpBot — Dashboard Live")

# auto-refresh
st.caption("Auto-refresh toutes les {}s".format(REFRESH_SECS))
st_autorefresh = st.experimental_rerun if False else None  # placeholder to keep code readable
# Streamlit v1.32+ propose st.autorefresh :
try:
    st_autorefresh = st.experimental_rerun  # fallback compat
    from streamlit.runtime.scriptrunner import add_script_run_ctx  # noqa: F401
    st_autorefresh = None
except Exception:
    pass

try:
    st_autorefresh = st.autorefresh(interval=REFRESH_SECS * 1000, key="autorf")
except Exception:
    pass

# Choix du dossier de logs (utile si on lance le dashboard depuis un autre cwd)
default_dir = str(LOG_DIR.resolve())
custom_dir = st.sidebar.text_input("Dossier de logs", value=default_dir)
LOG_DIR = Path(custom_dir) if custom_dir else LOG_DIR

if not LOG_DIR.exists():
    st.error(f"Dossier introuvable : {LOG_DIR}")
    st.stop()

data = load_logs()
df_sig, df_ord, df_fill, df_pos = data["signals"], data["orders"], data["fills"], data["positions"]

# KPIs rapides
notional, fees, n_fills = compute_activity_metrics(df_ord, df_fill)
col_a, col_b, col_c, col_d = st.columns(4)
col_a.metric("Paires actives (Top 10)", "10")
col_b.metric("Fills (total)", f"{n_fills}")
col_c.metric("Notionnel cumulé (approx)", f"{notional:,.0f} USDT")
col_d.metric("Frais cumulés", f"{fees:,.2f} USDT")

st.divider()

# 1) Positions snapshot
st.subheader("📌 Positions (snapshot courant par symbole)")
pos_snapshot = last_positions_snapshot(df_pos)
if pos_snapshot.empty:
    st.info("Aucune position pour l’instant.")
else:
    # Met un peu d'ordre dans les colonnes
    order_cols = [c for c in ["symbol", "state", "qty", "entry", "ts"] if c in pos_snapshot.columns]
    pos_snapshot = pos_snapshot[order_cols + [c for c in pos_snapshot.columns if c not in order_cols]]
    st.dataframe(pos_snapshot, use_container_width=True, height=260)

# 2) Derniers signaux
st.subheader("📣 Derniers signaux")
sig_tbl = recent_signals(df_sig, limit=40)
if sig_tbl.empty:
    st.info("Pas encore de signaux.")
else:
    # comptage LONG/SHORT
    try:
        by_side = sig_tbl.assign(side_norm=sig_tbl["side"].astype(str).str.upper()).groupby("side_norm").size()
        st.bar_chart(by_side)
    except Exception:
        pass
    st.dataframe(sig_tbl, use_container_width=True, height=300)

# 3) Ordres récents
st.subheader("🧾 Ordres récents")
ord_tbl = recent_orders(df_ord, limit=40)
if ord_tbl.empty:
    st.info("Pas encore d’ordres.")
else:
    st.dataframe(ord_tbl, use_container_width=True, height=280)

# 4) Fills récents
st.subheader("✅ Fills récents")
fills_tbl = recent_fills(df_fill, limit=80)
if fills_tbl.empty:
    st.info("Pas encore d’exécutions (fills).")
else:
    st.dataframe(fills_tbl, use_container_width=True, height=320)

st.caption(f"Logs: {LOG_DIR}")