# -*- coding: utf-8 -*-
"""
Pré-chauffe léger du cache OHLCV.

Objectif: ne PAS bloquer le lancement. On log juste un statut "warmup OK"
pour chaque symbole, et on s'assure que le dossier data existe.
Si tu veux rebrancher un vrai downloader plus tard, expose simplement une
fonction `prewarm_cache(cfg, symbols, timeframe, out_dir)` avec la même
signature.
"""
from __future__ import annotations
from pathlib import Path
from typing import Iterable


def prewarm_cache(cfg: dict, symbols: Iterable[str], timeframe: str, out_dir: str | Path) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for sym in symbols:
        # Marqueur vide; permet à d’autres services de voir que le symbole est "préparé"
        (out / f"{sym}-{timeframe}.csv").touch(exist_ok=True)
        print(f"[cache] warmup OK for {sym}")