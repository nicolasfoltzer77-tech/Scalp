from flask import Flask, request, jsonify
import hmac, hashlib, os, subprocess, json, time

app = Flask(__name__)

def verify_signature(secret: bytes, payload: bytes, sig256: str) -> bool:
    if not sig256 or not sig256.startswith("sha256="):
        return False
    digest = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig256, f"sha256={digest}")

def run_sync():
    log = subprocess.run(
        ["/opt/scalp/bin/git-sync.sh"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=180
    )
    return log.returncode, log.stdout

@app.get("/ping")
def ping():
    return jsonify(ok=True, ts=int(time.time()))

@app.post("/gh")
def gh():
    # charge secret
    secret = (os.environ.get("WEBHOOK_SECRET") or "").encode()
    if not secret:
        return jsonify(ok=False, error="No secret configured"), 500

    # vérifie signature
    sig = request.headers.get("X-Hub-Signature-256", "")
    payload = request.get_data()  # brut
    if not verify_signature(secret, payload, sig):
        return jsonify(ok=False, error="bad signature"), 401

    event = request.headers.get("X-GitHub-Event", "unknown")
    try:
        body = json.loads(payload or b"{}")
    except Exception:
        body = {}

    # on ne déclenche que sur push (par défaut), mais on accepte ping
    if event not in ("push", "ping"):
        return jsonify(ok=True, skipped=f"event {event}")

    code, out = run_sync()
    return jsonify(ok=(code == 0), code=code, log=out[-4000:])  # renvoie fin du log
