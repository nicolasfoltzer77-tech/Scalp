# bot.py
from __future__ import annotations
import os, signal, threading, time, yaml
from pathlib import Path
from engine.pipelines import Pipeline

# Chargement conf
CFG = yaml.safe_load(Path("/opt/scalp/engine/config/config.yaml").read_text(encoding="utf-8"))["runtime"]
DATA_DIR    = CFG["data_dir"]
REPORTS_DIR = CFG["reports_dir"]
SYMBOLS     = CFG["symbols"]
TF_LIST     = CFG["tf_list"]
EXEC_EN     = bool(CFG.get("exec_enabled", True))

def build_dashboard_and_publish():
    # 1) (Re)générer le dashboard
    os.environ["REPORTS_DIR"] = REPORTS_DIR
    os.environ["DASH_HTML"] = "/opt/scalp/dashboard.html"
    os.system("/opt/scalp/.venv/bin/python /opt/scalp/jobs/generate_dashboard.py")
    # 2) Publier vers GitHub Pages (docs/index.html + push hard-reset)
    os.system("/opt/scalp/.venv/bin/python /opt/scalp/tools/watch_dashboard_and_publish.py --once")

def main():
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
    Path(REPORTS_DIR).mkdir(parents=True, exist_ok=True)

    # Crée un pipeline par (symbol, tf)
    threads = []
    for sym in SYMBOLS:
        for tf in TF_LIST:
            p = Pipeline(sym, tf, DATA_DIR, REPORTS_DIR, EXEC_EN)
            t = threading.Thread(target=p.run, kwargs={"interval_sec": 10}, daemon=True)
            t._pipe = p  # type: ignore
            threads.append(t)

    # Démarre
    for t in threads: t.start()

    # boucle de maintenance: build dashboard toutes les 30s
    stop = False
    def _sig(*_): 
        nonlocal stop; stop = True
    signal.signal(signal.SIGINT, _sig); signal.signal(signal.SIGTERM, _sig)

    while not stop:
        time.sleep(30)
        build_dashboard_and_publish()

    # arrêt propre
    for t in threads: getattr(t, "_pipe").stop()  # type: ignore
    for t in threads: t.join(timeout=2)
    build_dashboard_and_publish()
    print("[bot] stopped.")

if __name__ == "__main__":
    main()
