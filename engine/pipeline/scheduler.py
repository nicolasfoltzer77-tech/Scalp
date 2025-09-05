from __future__ import annotations
import os, time, logging
from typing import List, Dict, Any, Optional

from engine.signals.strategy_bridge import evaluate_for
from engine.strategies.runner import load_strategies
from engine.utils.signal_sink import append_signal                # CSV legacy
from engine.utils.signal_sink_factored import append_signal_factored  # NEW
from tools.load_pairs import load_pairs  # ← pairs.txt

LOG = logging.getLogger("pipeline")

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

        # stratégies/config
        cfg: Dict[str, Any] = load_strategies()
        self._CFG: Dict[str, Any] = cfg
        self._STRATS: List[Dict[str, Any]] = cfg.get("strategies", [])

        # pairs initiales
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
        if new_pairs and new_pairs != self.symbols:
            self.log.info("Watchlist mise à jour (%d → %d paires)", len(self.symbols), len(new_pairs))
            self.symbols = new_pairs

    def _eval_once(self, symbol: str, tf: str, ohlcv: Optional[List[List[float]]] = None) -> Dict[str, Any]:
        res: Dict[str, Any] = {}
        try:
            res = evaluate_for(symbol=symbol, tf=tf,
                               strategies=self._STRATS, config=self._CFG,
                               ohlcv=ohlcv, logger=self.log)

            items = res.get("items", []) or []
            meta  = res.get("meta", {}) or {}
            combined = str(res.get("combined", "HOLD")).upper()

            # ==== extraction ====
            def pick(names):  # helper
                ns = {n.lower() for n in names}
                for it in items:
                    if str(it.get("name","")).lower() in ns:
                        return it
                return {}

            rsi_it = pick(["rsi","rsi_reversion"])
            sma_it = pick(["sma_cross_fast","sma_fast","ma_cross_fast"])
            ema_it = pick(["ema_trend","ema","trend"])

            rsi_val = rsi_it.get("value")
            ema_slope = ema_it.get("slope", ema_it.get("value"))

            def sig_to_factor(sig: str) -> int:
                s = (sig or "HOLD").upper()
                if s == "BUY": return +1
                if s == "SELL": return -1
                return 0

            # RSI
            if isinstance(rsi_val,(int,float)):
                if rsi_val < 30:    rsi_factor = +1
                elif rsi_val > 70:  rsi_factor = -1
                else:               rsi_factor = 0
            else:
                rsi_factor = sig_to_factor(rsi_it.get("signal"))

            sma_factor = sig_to_factor(sma_it.get("signal"))

            # EMA
            if isinstance(ema_slope,(int,float)):
                if ema_slope > 0:   ema_factor = +1
                elif ema_slope < 0: ema_factor = -1
                else:               ema_factor = 0
            else:
                ema_factor = sig_to_factor(ema_it.get("signal"))

            score = rsi_factor + sma_factor + ema_factor

            if score >= 2:   side = "BUY"
            elif score <= -2: side = "SELL"
            else:            side = "HOLD"

            # legacy CSV
            parts = []
            if sma_it: parts.append(f"sma_cross_fast={sma_it.get('signal','HOLD')}".upper())
            if rsi_it: parts.append(f"rsi={rsi_it.get('signal','HOLD')}".upper())
            if ema_it: parts.append(f"ema_trend={ema_it.get('signal','HOLD')}".upper())
            append_signal({"symbol": symbol, "tf": tf, "signal": side, "details": ";".join(parts)})

            # nouveau CSV factorisé
            notes = ""
            if not items: notes = "no_items"
            if meta.get("bars_loaded") in (0, None) and meta.get("data_ok") is False:
                notes = (notes + ";no_ohlcv").strip(";")

            append_signal_factored({
                "symbol": symbol, "tf": tf, "side": side, "score": score,
                "rsi_value": rsi_val, "rsi_factor": rsi_factor,
                "sma_fast_factor": sma_factor,
                "ema_trend_slope": ema_slope, "ema_trend_factor": ema_factor,
                "notes": notes,
            })

            self.log.info("pipe %s-%s: side=%s score=%+d [rsi=%s/%+d sma=%+d ema=%s/%+d]",
                          symbol, tf, side, score,
                          ("{:.2f}".format(rsi_val) if isinstance(rsi_val,(int,float)) else "-"),
                          rsi_factor, sma_factor,
                          ("{:.4f}".format(ema_slope) if isinstance(ema_slope,(int,float)) else "-"),
                          ema_factor)

        except Exception as e:
            self.log.error("pipeline error %s-%s: %s", symbol, tf, e, exc_info=True)
            append_signal_factored({
                "symbol": symbol, "tf": tf, "side": "HOLD", "score": 0,
                "rsi_value": "", "rsi_factor": 0, "sma_fast_factor": 0,
                "ema_trend_slope": "", "ema_trend_factor": 0,
                "notes": f"exception={type(e).__name__}",
            })
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
