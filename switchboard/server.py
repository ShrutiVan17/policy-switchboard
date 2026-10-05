"""Loopback demo service. Standard library only; no external services or costs."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import sqlite3
import threading
import time
from urllib.parse import urlparse
from .engine import enforce, POLICIES
from .evals import run

ROOT = Path(__file__).resolve().parent.parent
PROFILE=os.environ.get('SWITCHBOARD_MODE','demo')
if PROFILE not in {'demo','service'}: raise RuntimeError('Mode must be demo or service')
if PROFILE=='service' and any(len(os.environ.get(name,''))<32 for name in ('HARBOR_API_KEY','CEDAR_API_KEY')):
    raise RuntimeError('Service mode requires distinct tenant keys of at least 32 characters')
TOKENS = {os.environ.get("HARBOR_API_KEY", "demo-harbor-key"): "harbor",
          os.environ.get("CEDAR_API_KEY", "demo-cedar-key"): "cedar"}
if len(TOKENS) != 2:
    raise RuntimeError("Tenant keys must differ")
DB = ROOT / "artifacts" / "evidence.sqlite"
TRUSTED_DB=ROOT/'artifacts/trusted-context.sqlite'
CACHE = {}
EVAL_LOCK = threading.Lock()


def record(result):
    DB.parent.mkdir(exist_ok=True)
    with closing(sqlite3.connect(DB)) as conn, conn:
        conn.execute("CREATE TABLE IF NOT EXISTS evidence (id TEXT PRIMARY KEY, tenant TEXT, created_at TEXT, payload TEXT)")
        logged = json.loads(json.dumps(result))
        for finding in logged["findings"]:
            if finding["policy_id"] == "SECRET-01":
                finding["span"]["text"] = "[REDACTED]"
        conn.execute("INSERT INTO evidence VALUES (?,?,?,?)", (result["evidence_id"], result["tenant"], result["created_at"], json.dumps(logged)))


class Handler(BaseHTTPRequestHandler):
    def send_json(self, value, status=200):
        body = json.dumps(value, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def tenant(self):
        key = self.headers.get("Authorization", "")
        return TOKENS.get(key.removeprefix("Bearer ")) if key.startswith("Bearer ") else None

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/health":
            return self.send_json({"status":"ok", "backend":"deterministic", "trained_model":False})
        if path == "/api/demo-config":
            if PROFILE!='demo' or set(TOKENS)!={'demo-harbor-key','demo-cedar-key'}:
                return self.send_json({'error':'Demo credentials unavailable'},404)
            return self.send_json({"keys": {tenant: key for key, tenant in TOKENS.items()},
                                   "policies":[p.public() for p in POLICIES.values()], "local_demo":True})
        if path == "/api/evidence":
            tenant = self.tenant()
            if not tenant:
                return self.send_json({"error":"Valid tenant API key required"}, 401)
            if not DB.exists():
                return self.send_json({"events":[]})
            with closing(sqlite3.connect(DB)) as conn:
                events = [json.loads(row[0]) for row in conn.execute("SELECT payload FROM evidence WHERE tenant=? ORDER BY rowid DESC LIMIT 30", (tenant,))]
            return self.send_json({"events":events})
        files = {"/":"index.html", "/app.js":"app.js", "/styles.css":"styles.css"}
        if path not in files:
            return self.send_json({"error":"Not found"}, 404)
        file = ROOT / "web" / files[path]
        body = file.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", {".html":"text/html", ".js":"application/javascript", ".css":"text/css"}[file.suffix] + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        path = urlparse(self.path).path
        # Prevent cross-origin browser requests to a localhost service.
        origin = self.headers.get("Origin")
        if origin and origin not in {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}:
            return self.send_json({"error":"Cross-origin request denied"}, 403)
        tenant = self.tenant()
        if not tenant:
            return self.send_json({"error":"Valid tenant API key required"}, 401)
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > 32768:
                raise ValueError("Request body must be 1–32768 bytes")
            self.connection.settimeout(5)
            body = json.loads(self.rfile.read(size), parse_constant=lambda x: (_ for _ in ()).throw(ValueError("Nonfinite JSON number")))
            if not isinstance(body, dict):
                raise ValueError("Request must be an object")
            if body.get("tenant", tenant) != tenant:
                return self.send_json({"error":"Tenant does not match authenticated key"}, 403)
            if path == "/api/enforce":
                if set(body) - {"tenant", "version", "message", "context"}:
                    raise ValueError("Unknown request fields")
                t = time.perf_counter()
                result = enforce(body.get("message"), body.get("context", {}), tenant, body.get("version", "v1"))
                result.update(evidence_id="ev_"+secrets.token_hex(8), created_at=datetime.now(timezone.utc).isoformat(),
                              latency_ms=round((time.perf_counter()-t)*1000, 3))
                record(result)
                return self.send_json(result)
            if path == "/api/evaluate":
                with EVAL_LOCK:
                    result = run(body.get("mode", "full"), CACHE)
                return self.send_json(result)
            return self.send_json({"error":"Not found"}, 404)
        except (ValueError, TypeError) as exc:
            return self.send_json({"error":str(exc)}, 400)
        except (OSError, sqlite3.Error):
            return self.send_json({"error":"Service unavailable; output withheld"}, 503)


def main():
    if PROFILE=='service': raise SystemExit('Service mode requires the FastAPI entry point')
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Policy Switchboard: http://127.0.0.1:{args.port} (local fictional-data demo)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
