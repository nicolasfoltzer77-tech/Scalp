def _load_local_ohlcv(symbol: str, tf: str, limit: int = 300) -> Optional[List[List[float]]]:
    """
    Charge un report {symbol}_{tf}.json qui peut être :
    - un vrai JSON (list/dict) → parse via json.load()
    - un CSV déguisé (valeurs séparées par des virgules) → parse manuellement
    """
    path = os.path.join(REPORTS_DIR, f"{symbol.upper()}_{tf}.json")
    if not os.path.exists(path):
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            txt = f.read().strip()

        # tentative JSON
        try:
            raw = json.loads(txt)
        except Exception:
            raw = None

        if raw is None:
            # fallback CSV-like
            rows = []
            for line in txt.splitlines():
                parts = line.strip().split(",")
                if len(parts) < 5:
                    continue
                try:
                    ts     = float(parts[0])
                    close  = float(parts[4])
                    o = float(parts[4]) if parts[4] else 0.0
                    h = float(parts[5]) if len(parts) > 5 else 0.0
                    l = float(parts[6]) if len(parts) > 6 else 0.0
                    v = float(parts[7]) if len(parts) > 7 else 0.0
                    rows.append([ts,o,h,l,close,v])
                except Exception:
                    continue
            return rows[-limit:] if rows else None

        # sinon c’est un vrai JSON
        if isinstance(raw, dict):
            for k in ("candles","data","klines","rows"):
                if k in raw and isinstance(raw[k], list):
                    raw = raw[k]
                    break
        if not isinstance(raw, list):
            return None
        return _normalize_ohlcv_from_any(raw)[-limit:]

    except Exception as e:
        LOG.warning("load ohlcv local failed %s %s: %s", symbol, tf, e)
        return None
