# engine/live/health.py
from __future__ import annotations
from typing import Dict, List, Tuple
import re

# codes ANSI simples
_COL = {"k":"\x1b[30m","r":"\x1b[31m","g":"\x1b[32m","o":"\x1b[33m","x":"\x1b[0m"}

def _short(sym: str) -> str:
    s = sym.upper().replace("_","")
    return s[:-4] if s.endswith("USDT") else s

def _center(t: str, w: int) -> str:
    pad = max(0, w-len(t)); return " "*(pad//2) + t + " "*(pad-pad//2)

class HealthBoard:
    """Affichage console: tableau PAIR × TF avec MIS/OLD/DAT/OK."""
    def __init__(self, state):
        self.state = state
        self._legend_once = False

    def banner(self) -> None:
        print("\x1b[2J\x1b[H", end="")
        print("=== ORCHESTRATOR ===")

    def _render_table(self) -> str:
        syms = self.state.symbols
        tfs  = self.state.tfs
        header = ["PAIR", *tfs]
        rows: List[List[str]] = []
        counts = {"k":0,"r":0,"o":0,"g":0}

        for s in syms:
            line = [_short(s)]
            for tf in tfs:
                lbl, col = self.state.grid.get((s, tf), ("MIS","k"))
                counts[col] = counts.get(col,0) + 1
                cell = f"{_COL[col]}{lbl}{_COL['x']}"
                line.append(cell)
            rows.append(line)

        # largeurs visibles (sans ANSI)
        def vislen(x: str) -> int:
            return len(re.sub(r"\x1b\[[0-9;]*m","",x))

        widths = [max(vislen(r[i]) for r in [header]+rows) for i in range(len(header))]

        def fmt(row: List[str]) -> str:
            out=[]
            for i,v in enumerate(row):
                w=widths[i]
                if "\x1b[" in v:
                    plain = re.sub(r"\x1b\[[0-9;]*m","",v)
                    v = v.replace(plain, _center(plain, w))
                else:
                    v = _center(v, w)
                out.append(v)
            return " | ".join(out)

        sep = ["-"*w for w in widths]
        table = "\n".join([fmt(header), fmt(sep), *[fmt(r) for r in rows]])
        legend = (f"{_COL['k']}MIS{_COL['x']}=no data • "
                  f"{_COL['r']}OLD{_COL['x']}=stale • "
                  f"{_COL['o']}DAT{_COL['x']}=data no strat • "
                  f"{_COL['g']}OK{_COL['x']}=ready")
        stats = f"stats • MIS={counts['k']} OLD={counts['r']} DAT={counts['o']} OK={counts['g']}"
        return f"{table}\n{legend}\n{stats}"

    def render(self) -> None:
        print("\x1b[2J\x1b[H", end="")
        print(self._render_table())