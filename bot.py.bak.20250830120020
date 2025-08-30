# bot.py
from __future__ import annotations
import os, signal, threading, time, yaml, json
from pathlib import Path
from engine.pipelines import Pipeline

CFG = yaml.safe_load(Path("/opt/scalp/engine/config/config.yaml").read_text(encoding="utf-8"))["runtime"]
DATA_DIR    = CFG["data_dir"]
REPORTS_DIR = CFG["reports_dir"]
EXEC_EN     = bool(CFG.get("exec_enabled", True))
TF_LIST     = CFG["tf_list"]

def load_symbols() -> list[str]:
    # 1) watchlist si dispo
    wl = Path(REPORTS_DIR) / "watchlist.json"
    if wl.exists():
        try:
            obj = json.loads(wl.read_text(encoding="utf-8"))
            syms = obj.get("symbols") or []
            if syms:
                print(f"[bot] using watchlist symbols: {syms}")
                return syms
        except Exception:
            pass
    # 2) fallback: union manuel + cfg.symbols (unique)
    manual = CFG.get("manual_symbols", [])
    base   = CFG.get("symbols", [])
    res = []
    for s in manual + base:
        if s not in res: res.append(s)
    print(f"[bot] using fallback symbols: {res}")
    return res

def build_dashboard_and_publish():
    os.environ["REPORTS_DIR"] = REPORTS_DIR
    os.environ["DASH_HTML"] = "/opt/scalp/dashboard.html"
    os.system("/opt/scalp/venv/bin/python /opt/scalp/jobs/generate_dashboard.py")
    os.system("/opt/scalp/venv/bin/python /opt/scalp/tools/watch_dashboard_and_publish.py --once")

def main():
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
    Path(REPORTS_DIR).mkdir(parents=True, exist_ok=True)

    SYMBOLS = load_symbols()

    threads = []
    for sym in SYMBOLS:
        for tf in TF_LIST:
            p = Pipeline(sym, tf, DATA_DIR, REPORTS_DIR, EXEC_EN)
            t = threading.Thread(target=p.run, kwargs={"interval_sec": 10}, daemon=True)
            t._pipe = p  # type: ignore
            threads.append(t)

    for t in threads: t.start()

    stop = False
    def _sig(*_): 
        nonlocal stop; stop = True
    signal.signal(signal.SIGINT, _sig); signal.signal(signal.SIGTERM, _sig)

    while not stop:
        time.sleep(30)
        build_dashboard_and_publish()

    for t in threads: getattr(t, "_pipe").stop()  # type: ignore
    for t in threads: t.join(timeout=2)
    build_dashboard_and_publish()
    print("[bot] stopped.")

if __name__ == "__main__":
    main()
