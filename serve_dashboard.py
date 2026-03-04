from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def serve(directory: str | Path = "analysis_output", host: str = "0.0.0.0", port: int = 8085) -> None:
    root = Path(directory).resolve()
    root.mkdir(parents=True, exist_ok=True)
    handler = partial(SimpleHTTPRequestHandler, directory=str(root))
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Serving dashboard from {root} on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve analysis_output dashboard over HTTP")
    parser.add_argument("--directory", default="analysis_output", help="Directory to serve")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8085, help="Bind port")
    args = parser.parse_args()
    serve(directory=args.directory, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
