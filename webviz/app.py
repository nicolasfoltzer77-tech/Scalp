from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
import os, csv, time, glob

app = FastAPI(title="scalp-webviz")

BASE = "/opt/scalp/webviz"
DASH = "/opt/scalp/var/dashboard"   # signals.csv, signals_f.csv
KLINES = "/opt/scalp/data/klines"   # fichiers de données

# --------- Static + index ----------
app.mount("/static", StaticFiles(directory=BASE), name="static")

@app.get("/", include_in_schema=False)
def index():
    return FileResponse(os.path.join(BASE, "index.html"))

@app.get("/hello", include_in_schema=False)
def hello():
    return PlainTextResponse("hello from rtviz")

# --------- Helpers ----------
def _read_signals_csv():
    """
    Lit /opt/scalp/var/dashboard/signals_f.csv si présent,
    sinon /opt/scalp/var/dashboard/signals.csv.
    Retourne une liste de dicts pour le front.
    """
    # préférence au factorisé si dispo
    candidate = os.path.join(DASH, "signals_f.csv")
    if not os.path.exists(candidate):
        candidate = os.path.join(DASH, "signals.csv")

    if not os.path.exists(candidate):
        return []

    rows = []
    with open(candidate, newline="", encoding="utf-8") as f:
        # Schémas possibles:
        #  a) ts,symbol,tf,signal,details
        #  b) ts,symbol,tf,side,rsi,ema_fast,ema_slow,score,entry (factorisé)
        header = next(csv.reader([f.readline()]))
        f.seek(0)

        # Si pas d'entête, on force un schéma par défaut
        # (le DictReader avec fieldnames explicit)
        def dicts(fieldnames):
            return csv.DictReader(f, fieldnames=fieldnames)

        if "side" in header or "score" in header:
            # factorisé
            r = csv.DictReader(f)
            for rec in r:
                try:
                    ts = int(float(rec.get("ts", time.time())))
                except Exception:
                    ts = int(time.time())
                rows.append({
                    "ts": ts,
                    "sym": rec.get("symbol","").replace("USDT",""),
                    "tf": rec.get("tf",""),
                    "side": rec.get("side","HOLD"),
                    "score": float(rec.get("score", 0) or 0),
                    "entry": rec.get("entry",""),
                })
        else:
            # format simple (ts,symbol,tf,signal,details)
            for rec in dicts(["ts","symbol","tf","signal","details"]):
                try:
                    ts = int(float(rec.get("ts", time.time())))
                except Exception:
                    ts = int(time.time())
                rows.append({
                    "ts": ts,
                    "sym": rec.get("symbol","").replace("USDT",""),
                    "tf": rec.get("tf",""),
                    "side": (rec.get("signal","HOLD") or "HOLD").upper(),
                    "score": 0,
                    "entry": rec.get("details",""),
                })
    # on limite pour l’UI
    return rows[-300:]

# --------- API: signals (deux chemins pour être béton) ----------
@app.get("/signals")
@app.get("/api/signals")
def get_signals():
    try:
        return _read_signals_csv()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# --------- API: état des data (onglet Data) ----------
@app.get("/api/data_status")
def data_status():
    now = time.time()
    status = {}
    for path in glob.glob(os.path.join(KLINES, "*.csv")):
        name = os.path.basename(path).replace(".csv", "")   # ex: BTCUSDT_1m
        try:
            age = now - os.path.getmtime(path)
        except Exception:
            age = None
        if age is None:
            state = "gris"
        elif age < 120:
            state = "vert"
        elif age < 600:
            state = "orange"
        else:
            state = "rouge"
        status[name] = {"file": path, "age_sec": int(age) if age is not None else None, "state": state}
    return status
