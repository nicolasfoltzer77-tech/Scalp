import csv, json, os
from typing import List, Optional

DATA_DIR    = "/opt/scalp/data/klines"
REPORTS_DIR = "/opt/scalp/reports"

def _load_local_ohlcv(symbol: str, tf: str, limit: int = 300) -> Optional[List[List[float]]]:
    """
    Retourne une liste de candles [ts, open, high, low, close, vol].
    Sources acceptées, par ordre de priorité :
      1) /opt/scalp/data/klines/{SYM}_{TF}.csv
      2) /opt/scalp/reports/{SYM}_{TF}.json
         - vrai JSON (list/dict avec clé 'candles'/'data'/'klines'/'rows')
         - CSV-like (lignes de nombres séparés par ',')
         - snapshot (dict avec 'position', 'order', etc.) => ignoré (None)
    """
    sym = symbol.upper()
    # 1) CSV de klines si présent
    csv_path = os.path.join(DATA_DIR, f"{sym}_{tf}.csv")
    if os.path.exists(csv_path):
        out: List[List[float]] = []
        try:
            with open(csv_path, newline="", encoding="utf-8") as f:
                r = csv.reader(f)
                for row in r:
                    # accepte ts, o, h, l, c, v (au minimum ts & close)
                    if len(row) < 5:
                        continue
                    try:
                        ts = float(row[0]); o = float(row[1]); h = float(row[2]); l = float(row[3]); c = float(row[4])
                        v = float(row[5]) if len(row) > 5 else 0.0
                        out.append([ts,o,h,l,c,v])
                    except Exception:
                        continue
            if out:
                return out[-limit:]
        except Exception:
            pass  # on tente la source 2

    # 2) Fichier reports
    rpt_path = os.path.join(REPORTS_DIR, f"{sym}_{tf}.json")
    if not os.path.exists(rpt_path):
        return None

    try:
        with open(rpt_path, "r", encoding="utf-8") as f:
            txt = f.read().strip()

        # a) essai JSON
        is_json = txt.startswith("{") or txt.startswith("[")
        if is_json:
            try:
                raw = json.loads(txt)
            except Exception:
                raw = None

            # snapshot ? on détecte 'position'/'order' et pas de liste de candles
            if isinstance(raw, dict) and ("position" in raw or "order" in raw) and not any(
                k in raw for k in ("candles","data","klines","rows")
            ):
                return None

            # dict avec sous-clé liste
            if isinstance(raw, dict):
                for k in ("candles","data","klines","rows"):
                    if k in raw and isinstance(raw[k], list):
                        raw = raw[k]
                        break

            # liste déjà normalisée ?
            if isinstance(raw, list):
                out: List[List[float]] = []
                for it in raw:
                    try:
                        # accepte plusieurs schémas
                        if isinstance(it, dict):
                            ts = float(it.get("ts") or it.get("time") or it.get("t"))
                            o  = float(it.get("open")  or it.get("o"))
                            h  = float(it.get("high")  or it.get("h"))
                            l  = float(it.get("low")   or it.get("l"))
                            c  = float(it.get("close") or it.get("c"))
                            v  = float(it.get("vol")   or it.get("volume") or it.get("v") or 0.0)
                        else:
                            # type liste/tuple
                            ts,o,h,l,c = map(float, it[:5])
                            v = float(it[5]) if len(it) > 5 else 0.0
                        out.append([ts,o,h,l,c,v])
                    except Exception:
                        continue
                return out[-limit:] if out else None

        # b) fallback CSV-like (chaque ligne = valeurs séparées par des virgules)
        out: List[List[float]] = []
        for line in txt.splitlines():
            parts = [p.strip() for p in line.split(",")]
            # essaie de repérer au minimum ts & close en 5ème position
            if len(parts) < 5:
                continue
            try:
                ts = float(parts[0])
                # certains reports ont des colonnes meta au début (symbol, tf, side)
                # on tente de trouver 4 nombres consécutifs pour o,h,l,c
                nums = [float(p) for p in parts if p.replace(".","",1).replace("-","",1).isdigit()]
                # on prend la fin si > 4 valeurs
                if len(nums) >= 5:
                    # dernier schéma: ... o,h,l,c,(v)
                    c = nums[-2] if len(nums) == 5 else nums[-2]
                    # on prend 4 dernières avant volume présumé
                    o,h,l,c = nums[-5:-1]
                    v = nums[-1] if len(nums) >= 6 else 0.0
                    out.append([ts,o,h,l,c,v])
            except Exception:
                continue
        return out[-limit:] if out else None

    except Exception:
        return None

