#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

# IMPORTANT : sitecustomize.py est importé automatiquement si présent sur le PYTHONPATH.
# Dans ce repo, il charge /notebooks/.env, normalise les aliases, précharge la config
# et effectue un pré-flight (écrit un READY.json si tout est OK). 

# ---------- Logging de base ----------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("bot")

# ---------- Config ----------
try:
    from scalper.config.loader import load_config
except Exception as exc:
    log.error("Impossible d'importer scalper.config.loader.load_config: %s", exc)
    raise

def check_config() -> None:
    """
    Vérifie uniquement la présence des secrets critiques (pas les paramètres généraux).
    Le pré-flight global est déjà exécuté par sitecustomize.py ; cette vérif reste locale.
    """
    missing = []
    if not os.getenv("BITGET_ACCESS_KEY"):
        missing.append("BITGET_ACCESS_KEY")
    if not os.getenv("BITGET_SECRET_KEY"):
        missing.append("BITGET_SECRET_KEY")
    for k in missing:
        log.info("Missing %s", k)

# ---------- Utilitaires internes ----------
def _comma_split(val: Optional[str]) -> Iterable[str]:
    if not val:
        return []
    return [s.strip() for s in val.split(",") if s.strip()]

# ---------- Intégrations disponibles (souples) ----------
def _has_orchestrator() -> bool:
    try:
        # orchestrateur live présent dans scalper/live/orchestrator.py (vu dans ton dump) 
        import scalper.live.orchestrator  # noqa:F401
        return True
    except Exception:
        return False

def _build_exchange(cfg: Dict[str, Any]):
    """
    Construit l'exchange de manière robuste :
    1) On essaye la couche CCXT asynchrone si dispo (scalper.exchange.bitget_ccxt).
    2) Sinon on retombe sur le client REST interne (scalper.bitget_client).
    Les deux modules existent dans ton arborescence. 
    """
    # Essai CCXT
    try:
        from scalper.exchange.bitget_ccxt import BitgetExchange  # 
        access = cfg["secrets"]["bitget"]["access"]
        secret = cfg["secrets"]["bitget"]["secret"]
        password = cfg["secrets"]["bitget"]["passphrase"]
        data_dir = (cfg.get("runtime") or {}).get("data_dir", "/notebooks/data")
        ex = BitgetExchange(
            api_key=access or "",
            secret=secret or "",
            password=password or "",
            data_dir=str(data_dir),
        )
        log.info("Exchange: BitgetExchange (ccxt) initialisé")
        return ex, "ccxt"
    except Exception as exc:
        log.warning("CCXT indisponible ou erreur init (%s) — fallback REST", exc)

    # Fallback REST
    from scalper.bitget_client import BitgetFuturesClient  # 
    base_url = os.getenv("BITGET_BASE_URL", "https://api.bitget.com")
    ex = BitgetFuturesClient(
        access_key=cfg["secrets"]["bitget"]["access"] or "",
        secret_key=cfg["secrets"]["bitget"]["secret"] or "",
        passphrase=cfg["secrets"]["bitget"]["passphrase"] or "",
        base_url=base_url,
        paper_trade=(cfg.get("runtime") or {}).get("paper_trade", True),
    )
    log.info("Exchange: BitgetFuturesClient (REST) initialisé")
    return ex, "rest"

async def _run_with_orchestrator(cfg: Dict[str, Any]) -> None:
    """
    Chemin "complet" : utilise l’orchestrateur live si présent.
    Le package scalper/live/* est bien présent dans le repo. 
    """
    from scalper.live.orchestrator import run_orchestrator, RunConfig  # 
    from scalper.live.notify import build_notifier_and_commands  # 

    runtime = cfg.get("runtime") or {}
    strategy = cfg.get("strategy") or {}

    # Déterminer la watchlist
    allowed = runtime.get("allowed_symbols") or []
    symbols = allowed if allowed else ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    run_cfg = RunConfig(
        symbols=symbols,
        timeframe=strategy.get("live_timeframe", "1m"),
        refresh_secs=int(runtime.get("refresh_secs", 5)),
        cache_dir=str(runtime.get("data_dir", "/notebooks/data")),
    )

    exchange, backend = _build_exchange(cfg)
    notifier, cmd_stream = await build_notifier_and_commands(cfg)

    log.info("Démarrage orchestrateur (backend=%s, tf=%s, symbols=%s)",
             backend, run_cfg.timeframe, ",".join(run_cfg.symbols))
    await run_orchestrator(exchange, run_cfg, notifier, cmd_stream)

def _select_pairs_and_tick(cfg: Dict[str, Any]) -> None:
    """
    Chemin minimaliste (fallback) si orchestrateur non disponible :
    - utilise pairs.py / strategy.py pour scanner et logguer.
    Tous ces modules existent dans ton dépôt. 
    """
    from scalper.pairs import select_top_pairs, get_trade_pairs  # 
    from scalper.bitget_client import BitgetFuturesClient  # 

    client = BitgetFuturesClient(
        access_key=cfg["secrets"]["bitget"]["access"] or "",
        secret_key=cfg["secrets"]["bitget"]["secret"] or "",
        passphrase=cfg["secrets"]["bitget"]["passphrase"] or "",
        base_url=os.getenv("BITGET_BASE_URL", "https://api.bitget.com"),
        paper_trade=(cfg.get("runtime") or {}).get("paper_trade", True),
    )
    pairs = get_trade_pairs(client)
    top = select_top_pairs(client, top_n=10)
    log.info("Pairs totales=%d / Top10=%s", len(pairs or []), ",".join([p.get("symbol","?") for p in (top or [])]))

def main(argv: Optional[Iterable[str]] = None) -> int:
    # Petit rappel local (non bloquant) des secrets critiques
    check_config()

    # Charger la configuration fusionnée (config.yaml + .env)
    cfg = load_config()

    # Si orchestrateur dispo → chemin principal ; sinon fallback
    if _has_orchestrator():
        try:
            asyncio.run(_run_with_orchestrator(cfg))
            return 0
        except KeyboardInterrupt:
            log.info("Arrêt demandé par l'utilisateur (Ctrl+C)")
            return 0
        except SystemExit as exc:
            return int(getattr(exc, "code", 1) or 1)
        except Exception as exc:
            log.exception("Erreur run_orchestrator: %s", exc)
            return 1
    else:
        log.warning("Orchestrateur indisponible — exécution en mode scanner minimal.")
        try:
            _select_pairs_and_tick(cfg)
            return 0
        except Exception as exc:
            log.exception("Erreur fallback scanner: %s", exc)
            return 1

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))