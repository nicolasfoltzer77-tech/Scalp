# jobs/backfill_worker.py
from __future__ import annotations
import time, json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

import yaml
from jobs.recover_data import recover_bitget  # on réutilise le récupérateur existant

def load_cfg() -> Dict:
    return yaml.safe_load(Path("/opt/scalp/engine/config/config.yaml").read_text(encoding="utf-8"))["runtime"]

def now_ms() -> int: return int(time.time()*1000)

def read_first_ts(jsonl: Path) -> Optional[int]:
    if not jsonl.exists(): return None
    try:
        with jsonl.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                return int(json.loads(line)["t"])
    except Exception:
        return None
    return None

def list_symbols(cfg: Dict) -> List[str]:
    wl = Path(cfg["reports_dir"]) / "watchlist.json"
    if wl.exists():
        try:
            return [s for s in json.loads(wl.read_text(encoding="utf-8")).get("symbols", []) if s]
        except Exception:
            pass
    # fallback
    return list(dict.fromkeys(cfg.get("manual_symbols", []) + cfg.get("symbols", [])))

def backfill_for_symbol(cfg: Dict, sym: str, tf: str, minutes_target: int, pause_sec: float):
    data_dir = Path(cfg["data_dir"])
    path = data_dir / sym / tf / "ohlcv.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    first = read_first_ts(path)
    # si aucun fichier -> backfill complet sur la fenêtre cible
    if first is None:
        since = now_ms() - minutes_target*60_000
        print(f"[backfill] {sym} {tf} -> initial fill ~{minutes_target} min")
        recover_bitget(data_dir, [sym], [tf], since_ms=since, minutes=None, limit_per_call=1000, pause_sec=pause_sec)
    else:
        # top-up incrémental (recover_data détecte la dernière bougie et continue)
        print(f"[backfill] {sym} {tf} -> incremental")
        recover_bitget(data_dir, [sym], [tf], since_ms=None, minutes=None, limit_per_call=1000, pause_sec=pause_sec)

def run_once():
    cfg = load_cfg()
    targets: Dict[str,int] = cfg.get("backfill",{}).get("target_minutes",{}) or {}
    pause = float(cfg.get("backfill",{}).get("pause_sec",0.2))
    max_workers = int(cfg.get("backfill",{}).get("max_parallel",2))
    tfs = [t for t in cfg["tf_list"] if t in targets]
    syms = list_symbols(cfg)
    if not syms or not tfs:
        print("[backfill] rien à faire."); return
    print(f"[backfill] start once | syms={len(syms)} tfs={tfs} workers={max_workers}")
    tasks = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        for s in syms:
            for tf in tfs:
                tasks.append(ex.submit(backfill_for_symbol, cfg, s, tf, int(targets[tf]), pause))
        for fut in as_completed(tasks):
            try: fut.result()
            except Exception as e: print("[backfill] WARN:", e)
    print("[backfill] done once.")

def run_forever():
    cfg = load_cfg()
    refresh = int(cfg.get("backfill",{}).get("refresh_every_min", 15))
    while True:
        t0 = time.time()
        run_once()
        dt = time.time() - t0
        sleep_s = max(60*refresh - dt, 5)
        print(f"[backfill] sleep {int(sleep_s)}s")
        time.sleep(sleep_s)

if __name__ == "__main__":
    run_once()
