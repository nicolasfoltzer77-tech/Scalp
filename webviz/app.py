# -*- coding: utf-8 -*-
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse, JSONResponse

RTVIZ_VER = "rtviz-1.0"

app = FastAPI(title="SCALP – Visualisation", version=RTVIZ_VER)

@app.get("/viz/test")
def viz_test():
    return {"ok": True, "ver": RTVIZ_VER}

@app.get("/viz/hello")
def viz_hello():
    return PlainTextResponse("hello from rtviz", media_type="text/plain")

# Routers plug-in (on essaie d'importer, si échec on ignore → le core démarre)
def _try_include(path, router_name, prefix=""):
    try:
        mod = __import__(path, fromlist=[router_name])
        app.include_router(getattr(mod, router_name), prefix=prefix)
    except Exception as e:
        # exposer une info de debug légère sans casser le run
        @app.get(f"{prefix or ''}/__{path.replace('.','_')}_disabled")
        def _disabled():
            return JSONResponse({"ok": False, "module": path, "reason": str(e)})

_try_include("webviz.routes.signals", "router", prefix="/api")
_try_include("webviz.routes.history", "router", prefix="/api")
_try_include("webviz.routes.heatmap", "router", prefix="/viz")
_try_include("webviz.routes.stream",  "router", prefix="/viz")
_try_include("webviz.routes.demo",    "router", prefix="/viz")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("webviz.app:app", host="127.0.0.1", port=8100, log_level="info")
