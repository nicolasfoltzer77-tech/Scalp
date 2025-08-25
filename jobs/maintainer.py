from engine.config.loader import load_config

def _cfg_vals():
    cfg = load_config()
    wl = cfg.get("watchlist", {})
    mt = cfg.get("maintainer", {})
    return {
        "top": int(wl.get("top", 10)),
        "score_tf": str(wl.get("score_tf", "5m")),
        "tfs": [str(x) for x in (wl.get("backfill_tfs") or ["1m","5m","15m"])],
        "limit": int(wl.get("backfill_limit", 1500)),
        "interval": int(mt.get("interval_secs", 43200)),
    }

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    # laisser les flags CLI pour override ponctuel
    ap.add_argument("--top", type=int, default=None)
    ap.add_argument("--score-tf", type=str, default=None)
    ap.add_argument("--tfs", type=str, default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--interval", type=int, default=None)
    ap.add_argument("--once", action="store_true")
    ns = ap.parse_args(argv)

    base = _cfg_vals()
    top = ns.top if ns.top is not None else base["top"]
    score_tf = ns["score_tf"] if ns.score_tf else base["score_tf"]
    tfs = [t.strip() for t in (ns.tfs or ",".join(base["tfs"])).split(",") if t.strip()]
    limit = ns.limit if ns.limit is not None else base["limit"]
    interval = ns.interval if ns.interval is not None else base["interval"]

    if ns.once:
        run_once(top, score_tf, tfs, limit)
        return 0
    while True:
        try:
            run_once(top, score_tf, tfs, limit)
        except Exception as e:
            print(f"[maintainer] erreur: {e}")
        time.sleep(max(300, interval))