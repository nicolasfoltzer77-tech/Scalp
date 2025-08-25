# engine/live/state.py
from __future__ import annotations
import time, subprocess
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

from engine.backtest.loader_csv import load_csv_ohlcv
from engine.config.loader import load_config
from engine.config.strategies import load_strategies

_TF_MIN = {"1m":1,"5m":5,"15m":15,"1h":60,"4h":240,"1d":1440}

def _is_fresh(now_ms: int, last_ms: Optional[int], tf: str, mult: float) -> bool:
    if last_ms is None: return False
    return (now_ms - last_ms) <= (mult * _TF_MIN.get(tf,1) * 60_000)

@dataclass
class Cell:
    lbl: str  # MIS/OLD/DAT/OK
    col: str  # k/r/o/g

class MarketState:
    """Gère l’état (fraîcheur des CSV + présence/validité des stratégies) et actions AUTO."""
    def __init__(self, symbols: List[str], tfs: List[str], data_dir: str, fresh_mult: float = 1.0):
        self.symbols = symbols
        self.tfs = tfs
        self.data_dir = data_dir
        self.fresh_mult = fresh_mult
        self.grid: Dict[Tuple[str,str], Tuple[str,str]] = {}  # (lbl, col)
        self._cooldowns: Dict[str, float] = {}  # clé → epoch

    def _last_ts_ms(self, symbol: str, tf: str) -> Optional[int]:
        try:
            rows = load_csv_ohlcv(self.data_dir, symbol, tf, max_rows=1)
            return int(rows[-1][0]) if rows else None
        except Exception:
            return None

    def _status_cell(self, strategies: Dict[str, Dict], symbol: str, tf: str) -> Tuple[str,str]:
        now = int(time.time()*1000)
        last = self._last_ts_ms(symbol, tf)
        if last is None:
            return ("MIS","k")
        if not _is_fresh(now, last, tf, self.fresh_mult):
            return ("OLD","r")
        s = strategies.get(f"{symbol}:{tf}")
        if s and not s.get("expired"):
            return ("OK ","g")
        return ("DAT","o")

    def refresh(self, strategies: Optional[Dict[str, Dict]] = None) -> None:
        if strategies is None:
            strategies = load_strategies()
        new_grid: Dict[Tuple[str,str], Tuple[str,str]] = {}
        for s in self.symbols:
            for tf in self.tfs:
                new_grid[(s, tf)] = self._status_cell(strategies, s, tf)
        self.grid = new_grid

    def ready_pairs(self) -> List[Tuple[str,str]]:
        """Retourne (symbol, tf) dont la cellule est OK (verte)."""
        return [(s,tf) for (s,tf),(lbl,col) in self.grid.items() if col == "g"]

    # ---------- AUTO ----------
    def _cool(self, key: str, cooldown_secs: int) -> bool:
        now = time.time()
        t0 = self._cooldowns.get(key, 0.0)
        if (now - t0) >= cooldown_secs:
            self._cooldowns[key] = now
            return True
        return False

    def _run(self, args: List[str]) -> int:
        p = subprocess.run(args, capture_output=True, text=True)
        if p.stdout: print(p.stdout.strip())
        if p.stderr: print(p.stderr.strip())
        return p.returncode

    def auto_actions(self, limit: int, cooldown: int) -> None:
        """Déclenche automatiquement refresh/backtest/promote selon l’état."""
        # 1) refresh par TF si on voit MIS/OLD
        for tf in self.tfs:
            if any(self.grid.get((s,tf),("",""))[0] in ("MIS","OLD") for s in self.symbols):
                key = f"refresh:{tf}"
                if self._cool(key, cooldown):
                    print(f"[auto] refresh tf={tf}")
                    self._run(["python","-m","jobs.refresh_pairs","--timeframe",tf,"--top","0","--backfill-tfs",tf,"--limit",str(limit)])

        # 2) backtest + promote si on observe au moins un DAT
        if any(lbl == "DAT" for (lbl, _c) in self.grid.values()):
            if self._cool("backtest", cooldown):
                print("[auto] backtest + promote")
                self._run(["python","-m","jobs.backtest","--from-watchlist","--tfs",",".join(self.tfs)])
                self._run(["python","-m","jobs.promote","--backup"])