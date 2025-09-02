# api/server.py
from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse
from pathlib import Path
import json, os, time
from typing import List, Dict, Any

app = FastAPI(title="Scalp FastAPI")

# ---------- Utilitaires ----------
ROOT = Path("/opt/scalp").resolve()
REPORTS = ROOT / "reports"
WATCHLIST_JSON = REPORTS / "watchlist.json"

def _read_watchlist_symbols() -> List[str]:
    """
    Essaie de lire reports/watchlist.json.
    Retourne une liste de symboles (ex: ["BTCUSDT","ETHUSDT",...]).
    """
    try:
        if WATCHLIST_JSON.exists():
            data = json.loads(WATCHLIST_JSON.read_text())
            # format attendu dans tes captures: {"symbols":[...], "items":[...]}
            if isinstance(data, dict):
                if "symbols" in data and isinstance(data["symbols"], list):
                    return [s for s in data["symbols"] if isinstance(s, str)]
                if "items" in data and isinstance(data["items"], list):
                    out = []
                    for it in data["items"]:
                        s = it.get("sym") or it.get("symbol")
                        if isinstance(s, str):
                            out.append(s)
                    return out
    except Exception:
        pass
    # fallback sûr
    return ["BTCUSDT","ETHUSDT"]

def _pct_change_from_ohlcv(rows: List[List[float]]) -> float | None:
    """
    rows: [[ts,open,high,low,close,volume,...], ...] trié du plus ancien au plus récent.
    Retourne la variation % close[-1] vs close[-2].
    """
    try:
        if len(rows) < 2:
            return None
        c0 = float(rows[-2][4])
        c1 = float(rows[-1][4])
        if c0 == 0:
            return None
        return (c1 - c0) / c0 * 100.0
    except Exception:
        return None

# Tentative d’import du fetch OHLCV via tes adapters
_get_ohlcv = None
try:
    # chemin le plus probable dans ton arbo
    from engine.adapters.bitget.ohlcv import get_ohlcv as _get_ohlcv  # type: ignore
except Exception:
    try:
        from engine.adapters.market_data import get_ohlcv as _get_ohlcv  # type: ignore
    except Exception:
        _get_ohlcv = None

def _fetch_ohlcv_safe(symbol: str, tf: str, limit: int=2) -> List[List[float]] | None:
    """
    Récupère OHLCV de façon tolérante.
    """
    if _get_ohlcv is None:
        return None
    try:
        # signature habituelle: get_ohlcv(symbol, timeframe, limit=…)
        rows = _get_ohlcv(symbol, tf, limit=limit)  # type: ignore
        # s’assure que c’est une liste de listes
        if isinstance(rows, list) and rows and isinstance(rows[-1], (list, tuple)):
            return rows
    except Exception:
        pass
    return None

def _compute_heatmap(symbols: List[str]) -> List[Dict[str, Any]]:
    """
    Calcule la heatmap pour chaque symbole et TF parmi ["1m","5m","15m"].
    Renvoie: [{"sym":"BTCUSDT","base":"BTC","tf":{"1m": +0.12, "5m": -0.4, "15m": None}}, ...]
    """
    out = []
    for s in symbols[:36]:  # limite raisonnable pour le dash
        base = s.replace("USDT","")
        tf_map: Dict[str, float | None] = {}
        for tf in ("1m","5m","15m"):
            rows = _fetch_ohlcv_safe(s, tf, limit=2)
            pct = _pct_change_from_ohlcv(rows) if rows else None
            tf_map[tf] = None if pct is None else round(pct, 3)
        out.append({"sym": s, "base": base, "tf": tf_map})
    return out

def _get_balance_usdt() -> float | None:
    """
    Essaie de récupérer le solde USDT. Reste tolérant si non configuré.
    """
    try:
        # essaie un import simple; adapte si tu as un compteur maison
        from engine.adapters.bitget.account import get_balance  # type: ignore
        bal = get_balance("USDT")  # doit retourner un float ou dict
        if isinstance(bal, (int,float)):
            return float(bal)
        if isinstance(bal, dict):
            # cherche quelques clés communes
            for k in ("available","free","balance","total"):
                if k in bal and isinstance(bal[k], (int,float)):
                    return float(bal[k])
    except Exception:
        pass
    return None

# ---------- Endpoints existants minimalistes ----------
@app.get("/api/ping")
def ping():
    return {"ok": True, "utc": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())}

# /api/state enrichi (mode/risk déjà gérés côté worker; on lit le fichier state.json si présent)
@app.get("/api/state", response_class=JSONResponse)
def state():
    state_file = ROOT / "var" / "state.json"
    payload: Dict[str, Any] = {}
    if state_file.exists():
        try:
            payload = json.loads(state_file.read_text())
        except Exception:
            payload = {}

    # Enrichissements
    payload["mode"] = payload.get("mode") or "real"
    payload["risk_level"] = payload.get("risk_level") or 2
    payload["risk_profile"] = payload.get("risk_profile") or "modéré"

    # Balance (si dispo)
    bal = _get_balance_usdt()
    payload["balance"] = None if bal is None else round(bal, 2)

    # host + horodatage
    payload["host"] = os.uname().nodename
    payload["utc"] = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    return payload

# Ces deux endpoints doivent déjà exister chez toi.
# On les conserve via un import souple; sinon on renvoie du sample minimal.
def _read_json_list(path: Path) -> list:
    try:
        return json.loads(path.read_text())
    except Exception:
        return []

@app.get("/api/signals", response_class=JSONResponse)
def signals():
    # lit dernier dossier /opt/scalp/var/signals/YYYYMMDD/signals.json (si présent)
    base = ROOT / "var" / "signals"
    if not base.exists():
        return []
    try:
        days = sorted([d for d in base.iterdir() if d.is_dir()], reverse=True)
        for d in days:
            f = d / "signals.json"
            if f.exists():
                return _read_json_list(f)
    except Exception:
        pass
    return []

@app.get("/api/positions", response_class=JSONResponse)
def positions():
    base = ROOT / "var" / "positions"
    if not base.exists():
        return []
    try:
        days = sorted([d for d in base.iterdir() if d.is_dir()], reverse=True)
        for d in days:
            f = d / "positions.json"
            if f.exists():
                return _read_json_list(f)
    except Exception:
        pass
    return []

# --- Nouvelle heatmap ---
@app.get("/api/heatmap", response_class=JSONResponse)
def heatmap():
    symbols = _read_watchlist_symbols()
    data = _compute_heatmap(symbols)
    return {"symbols": symbols, "items": data, "utc": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())}

# page de garde simple (sert le dashboard via Nginx)
@app.get("/", response_class=PlainTextResponse)
def root():
    return "OK"
