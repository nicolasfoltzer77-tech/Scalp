from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.responses import Response
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
import httpx, uvicorn, os

API_BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000")

async def proxy_api(request: Request):
    # /api/... -> API_BASE/...
    upstream = API_BASE + request.url.path
    query = request.url.query
    if query: upstream += "?" + query
    body = await request.body()
    headers = dict(request.headers)
    # retire l'Host pour éviter des surprises
    headers.pop("host", None)
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.request(request.method, upstream, headers=headers, content=body)
    return Response(r.content, status_code=r.status_code, headers=dict(r.headers))

routes = [
    Route('/api/{path:path}', proxy_api, methods=['GET','POST','PUT','PATCH','DELETE','OPTIONS']),
    Mount('/', app=StaticFiles(directory='/opt/scalp/front401', html=True), name='static'),
]

app = Starlette(routes=routes)
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8088)
