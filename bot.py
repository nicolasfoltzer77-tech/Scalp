# bot.py
#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Any, Dict, Iterable, Optional, Sequence

# -----------------------------------------------------------------------------
# Logging de base
# -----------------------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("bot")

# -----------------------------------------------------------------------------
# Chargement config (paramètres généraux YAML + secrets .env)
# sitecustomize.py est importé automatiquement par Python si présent sur le
# PYTHONPATH et, dans ce repo, il charge /notebooks/.env, normalise les aliases
# et déclenche un pré‑flight qui écrit un READY.json si tout va bien.
# -----------------------------------------------------------------------------
try:
    from scalper.config.loader import load_config  # type: ignore
except Exception as exc:  # pragma: no cover
    log.error("Impossible d'importer scalper.config.loader.load_config: %s", exc)
    raise


# -----------------------------------------------------------------------------
# Petits utilitaires
# -----------------------------------------------------------------------------
def _comma_split(val: Optional[str]) -> list[str]:
    if not val:
        return []
    return [s.strip() for s in val.split(",") if s.strip()]


def check_config() -> None:
    """
    Vérif locale non bloquante des secrets critiques.
    Le pré‑flight global (sitecustomize.py) s'occupe déjà de stopper si manquant.
    """
    for key in ("BITGET_ACCESS_KEY", "BITGET_SECRET_KEY"):
        if not os.getenv(key):
            logging.getLogger("bot.config").info("Missing %s", key)


def _has_orchestrator() -> bool:
    try:
        import scalper.live.orchestrator  # noqa: F401
        return True
    except Exception:
        return False


# -----------------------------------------------------------------------------
# Construction de l’exchange (CCXT si possible -> fallback REST)
# -----------------------------------------------------------------------------
def _build_exchange(cfg: Dict[str, Any]):
    """
    Retourne (exchange, backend_name)
    - backend 'ccxt' si scalper.exchange.bitget_ccxt est dispo
    - backend 'rest' sinon (scalper.bitget_client.BitgetFuturesClient)
    """
    access = cfg.get("secrets", {}).get("bitget", {}).get("access") or ""
    secret = cfg.get("secrets", {}).get("bitget", {}).get("secret") or ""
    passphrase = cfg.get("secrets", {}).get("bitget", {}).get("passphrase") or ""
    runtime = cfg.get("runtime") or {}
    data_dir = str(runtime.get("data_dir", "/notebooks/data"))

    # CCXT async
    try:
        from scalper.exchange.bitget_ccxt import BitgetExchange  # type: ignore
        ex = BitgetExchange(
            api_key=access,
            secret=secret,
            password=passphrase,
            data_dir=data_dir,
        )
        log.info("Exchange initialisé: CCXT")
        return ex, "ccxt"
    except Exception as exc:
        log.warning("CCXT indisponible (%s) — on bascule REST", exc)

    # REST interne
    from scalper.bitget_client import BitgetFuturesClient  # type: ignore
    base_url = os.getenv("BITGET_BASE_URL", "https://api.bitget.com")
    ex = BitgetFuturesClient(
        access_key=access,
        secret_key=secret,
        passphrase=passphrase,
        base_url=base_url,
        paper_trade=bool(runtime.get("paper_trade", True)),
    )
    log.info("Exchange initialisé: REST")
    return ex, "rest"


# -----------------------------------------------------------------------------
# Chemin principal: orchestrateur live
# -----------------------------------------------------------------------------
async def _run_with_orchestrator(cfg: Dict[str, Any]) -> None:
    """
    Démarre l’orchestrateur live si disponible.
    Modules attendus (présents dans le repo) :
      - scalper/live/orchestrator.py : RunConfig, run_orchestrator
      - scalper/live/notify.py      : build_notifier_and_commands
    """
    from scalper.live.orchestrator import RunConfig, run_orchestrator  # type: ignore
    from scalper.live.notify import build_notifier_and_commands        # type: ignore

    runtime = cfg.get("runtime") or {}
    strategy = cfg.get("strategy") or {}

    # Watchlist : si allowed_symbols vide -> fallback par défaut
    allowed: Sequence[str] = runtime.get("allowed_symbols") or []
    symbols = list(allowed) if allowed else ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    run_cfg = RunConfig(
        symbols=symbols,
        timeframe=strategy.get("live_timeframe", "1m"),
        refresh_secs=int(runtime.get("refresh_secs", 5)),
        cache_dir=str(runtime.get("data_dir", "/notebooks/data")),
    )

    exchange, backend = _build_exchange(cfg)
    notifier, cmd_stream = await build_notifier_and_commands(cfg)

    log.info(
        "Orchestrateur: backend=%s timeframe=%s symbols=%s",
        backend, run_cfg.timeframe, ",".join(run_cfg.symbols),
    )
    await run_orchestrator(exchange, run_cfg, notifier, cmd_stream)


# -----------------------------------------------------------------------------
# Fallback minimal: scan pairs + log (si orchestrateur indisponible)
# -----------------------------------------------------------------------------
def _fallback_scan_once(cfg: Dict[str, Any]) -> None:
    """
    Mode secouru (pour ne pas planter si l’orchestrateur n’est pas importable).
    Utilise le client REST + pairs.py pour un scan et log d’activité.
    """
    from scalper.bitget_client import BitgetFuturesClient  # type: ignore
    from scalper.pairs import get_trade_pairs, select_top_pairs  # type: ignore

    access = cfg.get("secrets", {}).get("bitget", {}).get("access") or ""
    secret = cfg.get("secrets", {}).get("bitget", {}).get("secret") or ""
    passphrase = cfg.get("secrets", {}).get("bitget", {}).get("passphrase") or ""
    runtime = cfg.get("runtime") or {}

    client = BitgetFuturesClient(
        access_key=access,
        secret_key=secret,
        passphrase=passphrase,
        base_url=os.getenv("BITGET_BASE_URL", "https://api.bitget.com"),
        paper_trade=bool(runtime.get("paper_trade", True)),
    )
    pairs = get_trade_pairs(client) or []
    top = select_top_pairs(client, top_n=10) or []
    top_symbols = [p.get("symbol", "?") for p in top]
    log.info("Scanner: total_pairs=%d top10=%s", len(pairs), ",".join(top_symbols))


# -----------------------------------------------------------------------------
# Entrée CLI
# -----------------------------------------------------------------------------
def main(argv: Optional[Iterable[str]] = None) -> int:
    # Vérif locale (info) des secrets critiques
    check_config()

    # Charge la config fusionnée (config.yaml + .env)
    cfg = load_config()

    if _has_orchestrator():
        try:
            asyncio.run(_run_with_orchestrator(cfg))
            return 0
        except KeyboardInterrupt:
            log.info("Arrêt demandé (Ctrl+C)")
            return 0
        except SystemExit as exc:
            return int(getattr(exc, "code", 1) or 1)
        except Exception as exc:
            log.exception("Erreur orchestrateur: %s", exc)
            return 1
    else:
        log.warning("Orchestrateur indisponible — mode scanner minimal.")
        try:
            _fallback_scan_once(cfg)
            return 0
        except Exception as exc:
            log.exception("Erreur scanner: %s", exc)
            return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))