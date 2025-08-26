#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Maintainer asynchrone :
- Worker refresh en continu (thread)
- Déclenche backtest (parallèle) + promote dès que les CSV sont assez frais
- Écrit status.json / last_errors.json pour le dashboard
"""

from __future__ import annotations
import os, sys, pathlib, time, json, yaml, subprocess, threading
from typing import Dict, List, Tuple, Optional

# -- bootstrap path repo
_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[1])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
import sitecustomize  # noqa: F401

CFG_PATH = os.path.join(_REPO_ROOT, "engine", "config", "config.yaml")

# ------------ utils ------------
def _read_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def write_json(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def ohlcv_path(data_dir: str, pair: str, tf: str) -> str:
    return os.path.join(data_dir, "ohlcv", pair, f"{tf}.csv")

def tf_minutes(tf: str) -> int:
    assert tf.endswith("m")
    return int(tf[:-1])

def file_age_minutes(path: str) -> float:
    try:
        return (time.time() - os.path.getmtime(path)) / 60.0
    except FileNotFoundError:
        return float("inf")

def list_pairs_from_watchlist(reports_dir: str) -> List[str]:
    p = os.path.join(reports_dir, "watchlist.yml")
    if not os.path.isfile(p): return []
    doc = _read_yaml(p)
    pairs = doc.get("pairs") or doc.get("watchlist") or []
    return [x for x in pairs if isinstance(x, str)]

# ------------ subprocess helpers ------------
def run_module_blocking(modname: str, *args, cwd: Optional[str] = None) -> Tuple[int, str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = _REPO_ROOT + (":" + env.get("PYTHONPATH","") if env.get("PYTHONPATH") else "")
    cp = subprocess.run([sys.executable, "-m", modname, *args],
                        cwd=cwd or _REPO_ROOT, env=env,
                        capture_output=True, text=True)
    return cp.returncode, cp.stdout or "", cp.stderr or ""

def run_module_detached(modname: str, *args, cwd: Optional[str] = None) -> subprocess.Popen:
    env = os.environ.copy()
    env["PYTHONPATH"] = _REPO_ROOT + (":" + env.get("PYTHONPATH","") if env.get("PYTHONPATH") else "")
    return subprocess.Popen([sys.executable, "-m", modname, *args],
                            cwd=cwd or _REPO_ROOT, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# ------------ status ------------
def compute_status(data_dir: str, reports_dir: str, tf_list: List[str], age_mult: int) -> Dict:
    counts = {"MIS":0, "OLD":0, "DAT":0, "OK":0}
    matrix = []

    promoted = {}
    strat_path = os.path.join(_REPO_ROOT, "engine", "config", "strategies.yml")
    if os.path.isfile(strat_path):
        doc = _read_yaml(strat_path) or {}
        for k, v in (doc.get("strategies") or {}).items():
            promoted[k] = v

    pairs = list_pairs_from_watchlist(reports_dir)
    for pair in pairs:
        row = {"pair": pair}
        for tf in tf_list:
            csvp = ohlcv_path(data_dir, pair, tf)
            if not os.path.isfile(csvp):
                st = "MIS"
            else:
                age_m = file_age_minutes(csvp)
                lifetime_m = age_mult * tf_minutes(tf)
                key = f"{pair}:{tf}"
                active = key in promoted and not promoted[key].get("expired", False)
                if age_m > lifetime_m:
                    st = "OLD"
                elif active:
                    st = "OK"
                else:
                    st = "DAT"
            counts[st] += 1
            row[tf] = st
        matrix.append(row)

    total_cells = sum(counts.values()) or 1
    fresh_cells = counts["DAT"] + counts["OK"]
    fresh_ratio = fresh_cells / total_cells

    return {
        "generated_at": int(time.time()),
        "counts": counts,
        "matrix": matrix,
        "fresh_ratio": fresh_ratio,
        "notes": "MIS=no data · OLD=stale · DAT=fresh CSV, no active strategy · OK=fresh CSV + active strategy"
    }

# ------------ refresh worker ------------
class RefreshWorker:
    def __init__(self, tf_for_backfill: List[str], topN: int, limit: int, every_secs: int):
        self.tf_for_backfill = tf_for_backfill
        self.topN = topN
        self.limit = limit
        self.every_secs = every_secs
        self._stop = threading.Event()
        self._proc: Optional[subprocess.Popen] = None

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._stop.set()
        if self._proc and self._proc.poll() is None:
            try: self._proc.terminate()
            except Exception: pass

    def _loop(self):
        while not self._stop.is_set():
            if self._proc is None or self._proc.poll() is not None:
                args = ["--timeframe","5m","--top",str(self.topN),
                        "--backfill-tfs", ",".join(self.tf_for_backfill),
                        "--limit", str(self.limit)]
                self._proc = run_module_detached("jobs.refresh_pairs", *args)
            self._stop.wait(self.every_secs)

# ------------ main orchestrator ------------
def main():
    cfg = _read_yaml(CFG_PATH)
    rt = cfg.get("runtime", {}) if isinstance(cfg, dict) else {}

    data_dir    = rt.get("data_dir", "/notebooks/scalp_data/data")
    reports_dir = rt.get("reports_dir", "/notebooks/scalp_data/reports")
    tf_list     = list(rt.get("tf_list", ["1m","5m","15m"]))
    age_mult    = int(rt.get("age_mult", 5))
    topN        = int(rt.get("topN", 10))

    auto_refresh            = bool(rt.get("auto_refresh", True))
    refresh_every_secs      = int(rt.get("refresh_every_secs", 30))
    backfill_limit          = int(rt.get("backfill_limit", 1500))
    min_fresh_ratio         = float(rt.get("min_fresh_ratio", 0.8))
    backtest_cooldown_secs  = int(rt.get("backtest_cooldown_secs", 120))
    max_workers             = int(rt.get("backtest_max_workers", 4))

    worker = RefreshWorker(tf_for_backfill=tf_list, topN=topN, limit=backfill_limit, every_secs=refresh_every_secs) if auto_refresh else None
    if worker: worker.start()

    last_bt_end = 0.0
    bt_running = False

    while True:
        # 1) statut courant
        stat = compute_status(data_dir, reports_dir, tf_list, age_mult)
        write_json(stat, os.path.join(reports_dir, "status.json"))

        c = stat["counts"]
        print(f"[maintainer] STATUS MIS={c['MIS']} OLD={c['OLD']} DAT={c['DAT']} OK={c['OK']} · fresh={stat['fresh_ratio']:.0%}")

        # 2) trigger backtest parallèle + promote
        now = time.time()
        if (not bt_running) and (now - last_bt_end >= backtest_cooldown_secs) and (stat["fresh_ratio"] >= min_fresh_ratio):
            bt_running = True
            print(f"[maintainer] Trigger backtest (max_workers={max_workers}) + promote…")
            rc_bt, out_bt, err_bt = run_module_blocking("jobs.backtest")
            if rc_bt != 0:
                print(f"[maintainer] WARN backtest RC={rc_bt} :: { (err_bt or out_bt)[-500:] }")
            # promote (sans --draft)
            src_next = os.path.join(reports_dir, "strategies.yml.next")
            rc_pr, out_pr, err_pr = run_module_blocking("jobs.promote", "--source", src_next)
            if rc_pr != 0:
                print(f"[maintainer] WARN promote RC={rc_pr} :: { (err_pr or out_pr)[-500:] }")

            # journal actions
            last = {
                "ts": int(time.time()),
                "backtest_rc": rc_bt, "backtest_err_tail": (err_bt or out_bt)[-800:],
                "promote_rc": rc_pr,  "promote_err_tail": (err_pr or out_pr)[-800:],
            }
            write_json(last, os.path.join(reports_dir, "last_errors.json"))

            last_bt_end = time.time()
            bt_running = False

        # 3) régénère dashboard.html
        run_module_blocking("tools.render_report")

        time.sleep(5)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[maintainer] stop.")
    except Exception as e:
        print(f"[maintainer] FATAL: {e}")
        sys.exit(1)