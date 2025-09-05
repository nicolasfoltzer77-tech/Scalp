#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import os, time, json, logging
from typing import List, Dict, Any, Optional, Iterable

from engine.signals.strategy_bridge import evaluate_for
from engine.strategies.runner import load_strategies
from engine.utils.signal_sink import append_signal
from tools.load_pairs import load_pairs  # ← pairs.txt

LOG = logging.getLogger("pipeline")

REPORTS_DIR = "/opt/scalp/reports"

def _as_float(x) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None

def _normalize_ohlcv_from_any(data: Iterable) -> List[List[float]]:
    """
    Rend une liste de [ts, o, h, l, c, v] (ou proche),
    à partir de différents formats possibles (list de list, list de dict, etc.).
    On ne garde que ts et close si besoin (les autres champs peuvent rester 0.0).
    """
    out: List[List[float]] = []
    for row in data:
        ts: Optional[float] = None
        close: Optional[float] = None
        o = h = l = v = None

        if isinstance(row, dict):
            # tolère plusieurs conventions
            ts = _as_float(row.get("ts") or row.get("time") or row.get("t"))
            close = _as_float(row.get("close") or row.get("c"))
            o = _as_float(row.get("open") or row.get("o"))
            h = _as_float(row.get("high") or row.get("h"))
            l = _as_float(row.get("low") or row.get("l"))
            v = _as_float(row.get("volume") or row.get("v"))
        elif isinstance(row, (list, tuple)) and len(row) >= 5:
            # [ts, open, high, low, close, (volume...)]
            ts = _as_float(row[0])
            o  = _as_float(row[1])
            h  = _as_float(row[2])
            l  = _as_float(row[3])
            close = _as_float(row[4])
            if len(row) >= 6:
                v = _as_float(row[5])

        if ts is None or close is None:
            continue

        out.append([
            ts,
            o if o is not None else 0.0,
            h if h is not None else 0.0,
            l if l is not None else 0.0,
            close,
            v if v is not None else 0.0,
        ])

    # tri par timestamp au cas où
    out.sort(key=lambda r: r[0])
    return out

def _load_local_ohlcv(symbol: str, tf: str, limit: int = 300) -> Optional[List[List[float]]]:
    """
    Charge /opt/scalp/reports/{SYMBOL}_{tf}.json (tolérant aux formats)
    et renvoie une liste normalisée de bougies.
    """
    path = os.path.join(REPORTS_DIR, f"{symbol.upper()}_{tf}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        # quelques structures courantes : liste brute, {"candles":[...]}, {"data":[...]}
        if isinstance(raw, dict):
            for k in ("candles", "data", "klines", "rows"):
                if k in raw and isinstance(raw[k], list):
                    raw = raw[k]
                    break
        if not isinstance(raw, list):
            return None
        ohlcv = _normalize_ohlcv_from_any(raw)
        if not ohlcv:
            return None
        return ohlcv[-limit:]
    except Exception as e:
        LOG.warning("load ohlcv local failed %s %s: %s", symbol, tf, e)
        return None

class PipelineScheduler:
    """
    Boucle principale : évalue (symbol × tf), écrit les signaux CSV,
    et recharge la watchlist depuis pairs.txt toutes les N secondes.
    """

    def __init__(
        self,
        symbols: Optional[List[str]] = None,
        tfs: Optional[List[str]] = None,
        interval_sec: float = 5.0,
        reload_pairs_sec: float = 60.0,
        logger: Optional[logging.Logger] = None,
    ):
        self.tfs = tfs or ["1m","5m","15m"]
        self.interval = interval_sec
        self.reload_pairs_sec = reload_pairs_sec
        self.log = logger or LOG

        cfg: Dict[str, Any] = load_strategies()
        self._CFG: Dict[str, Any] = cfg
        self._STRATS: List[Dict[str, Any]] = cfg.get("strategies", [])

        self.symbols: List[str] = symbols or load_pairs()
        self._last_reload = 0.0

        self.log.info("Scheduler prêt | symbols=%s | tfs=%s | interval=%.1fs | reload_pairs=%.0fs",
                      self.symbols, self.tfs, self.interval, self.reload_pairs_sec)

    def _maybe_reload_pairs(self):
        now = time.time()
        if now - self._last_reload < self.reload_pairs_sec:
            return
        self._last_reload = now
        new_pairs = load_pairs()
        if not new_pairs:
            return
        if new_pairs != self.symbols:
            self.log.info("Watchlist mise à jour (%d → %d paires)", len(self.symbols), len(new_pairs))
            self.symbols = new_pairs

    def _eval_once(self, symbol: str, tf: str) -> Dict[str, Any]:
        # ← NOUVEAU : on charge l’ohlcv local et on le passe au bridge
        ohlcv = _load_local_ohlcv(symbol, tf)
        res = evaluate_for(symbol=symbol, tf=tf,
                           strategies=self._STRATS, config=self._CFG,
                           ohlcv=ohlcv, logger=self.log)

        sig = res.get("combined", "HOLD")
        try:
            items   = res.get("items", [])
            details = ";".join(f"{i.get('name')}={i.get('signal')}" for i in items)[:512]

            # S'il y a des métriques, on les conserve côté sink (signal_sink_factored.py)
            metrics = res.get("metrics") or {}
            append_signal({
                "symbol": symbol, "tf": tf, "signal": sig, "details": details,
                "metrics": metrics
            })
        except Exception:
            pass

        self.log.info("pipe-%s-%s sig=%s", symbol, tf, sig)
        return res

    def run(self) -> None:
        self.log.info("Bot démarré avec %s / %s", self.symbols, self.tfs)
        while True:
            self._maybe_reload_pairs()
            t0 = time.time()
            for s in self.symbols:
                for tf in self.tfs:
                    try:
                        self._eval_once(s, tf)
                    except Exception as e:
                        self.log.error("pipeline task error: %s", e, exc_info=True)
            time.sleep(max(0.0, self.interval - (time.time() - t0)))
