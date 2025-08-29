from __future__ import annotations
import csv, json, time, os, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    import yaml  # pip install pyyaml (déjà présent normalement)
except Exception:
    print("ERROR: pyyaml manquant: /opt/scalp/venv/bin/pip install pyyaml", file=sys.stderr)
    sys.exit(1)

def read_last_timestamp(csv_path: Path) -> datetime | None:
    try:
        with csv_path.open("r", newline="") as f:
            r = csv.DictReader(f)
            last = None
            for row in r:
                last = row
            if not last:
                return None
            # colonnes attendues: timestamp (ms) OU datetime (ISO)
            if "datetime" in last and last["datetime"]:
                # ex: 2025-08-28 19:02:00+00:00
                # tolère aussi sans timezone
                try:
                    dt = datetime.fromisoformat(last["datetime"])
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt.astimezone(timezone.utc)
                except Exception:
                    pass
            ts = last.get("timestamp") or last.get("ts")
            if ts:
                # Bitget CSV: ms
                ms = int(float(ts))
                # si c'est en secondes, ça reste correct car ms//1000
                if ms > 10_000_000_000:  # heuristique: ms
                    sec = ms // 1000
                else:
                    sec = ms
                return datetime.fromtimestamp(sec, tz=timezone.utc)
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"WARN read {csv_path.name}: {e}", file=sys.stderr)
    return None

def main():
    cfg = yaml.safe_load(Path("/opt/scalp/site/config.yaml").read_text())
    data_dir = Path(cfg["data_dir"])
    active_dir = Path(cfg.get("active_dir", "/opt/scalp/site/active"))
    pairs = cfg["pairs"]; tfs = cfg["tfs"]
    fresh_minutes = cfg["fresh_minutes"]

    now = datetime.now(timezone.utc)

    # Totaux
    counters = {"MIS": 0, "OLD": 0, "DAT": 0, "OK": 0}
    # Matrice pour le heatmap
    matrix = []  # [{pair, tf, status, age_min, last_dt, path}]

    for pair in pairs:
        for tf in tfs:
            csv_path = data_dir / f"{pair}-{tf}.csv"
            last_dt = read_last_timestamp(csv_path)
            active_flag = (active_dir / f"{pair}-{tf}.active").exists()
            if not last_dt:
                status = "MIS"  # no data
                age_min = None
            else:
                age = now - last_dt
                age_min = int(age.total_seconds() // 60)
                fresh_limit = int(fresh_minutes.get(tf, 10))
                if age_min > fresh_limit:
                    status = "OLD"  # stale
                else:
                    status = "OK" if active_flag else "DAT"

            counters[status] += 1
            matrix.append({
                "pair": pair, "tf": tf, "status": status,
                "age_min": age_min, "last_dt": last_dt.isoformat() if last_dt else None,
                "csv": str(csv_path)
            })

    out = {
        "generated_at": int(time.time()),
        "status": "ok",
        "counters": counters,
        "matrix": matrix,
    }
    out_dir = Path("/opt/scalp/site/out"); out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "dashboard.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"written {out_dir/'dashboard.json'}", file=sys.stderr)

if __name__ == "__main__":
    main()
