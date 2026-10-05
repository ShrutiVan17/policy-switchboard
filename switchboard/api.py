"""Typed FastAPI entry point for the local fictional-data demo."""
from contextlib import closing
from datetime import datetime, timezone
import json
import secrets
import sqlite3
import time
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from .engine import POLICIES, enforce, resolve
from .evals import run
from .release_gate import load_experiments
from . import server

app = FastAPI(title="Policy Switchboard", version="1.1.0",
              description="Fictional customer-policy lab. Verified rules delivery, measured LoRA research, shadow inference and release gates.")
bearer = HTTPBearer(auto_error=False)


class EnforcementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    message: str = Field(min_length=1, max_length=6000)
    version: str = "v1"
    tenant: str | None = None
    context: dict = Field(default_factory=dict)
    ticket_id: str | None = Field(default=None,min_length=1,max_length=64,pattern=r'^[A-Za-z0-9_.-]+$')


class EvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["full", "triage"] = "full"


def authenticated_tenant(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    tenant = server.TOKENS.get(credentials.credentials) if credentials else None
    if not tenant:
        raise HTTPException(401, "Valid tenant API key required")
    return tenant


@app.middleware("http")
async def demo_boundary(request: Request, call_next):
    if request.method == "POST":
        origin = request.headers.get("origin")
        port = request.url.port or 80
        allowed={f"http://127.0.0.1:{port}",f"http://localhost:{port}"}
        if server.PUBLIC_ORIGIN:allowed.add(server.PUBLIC_ORIGIN)
        if origin and origin not in allowed:
            return JSONResponse({"error":"Cross-origin request denied"}, status_code=403)
        try:
            size = int(request.headers.get("content-length", "0"))
        except ValueError:
            size = 0
        if size <= 0 or size > 32768:
            return JSONResponse({"error":"Request body must be 1–32768 bytes"}, status_code=400)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    # Swagger UI uses its own CDN scripts; keep the strict policy on app surfaces.
    if request.url.path not in {"/docs", "/redoc"}:
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'"
    return response


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return JSONResponse({"error":exc.detail}, status_code=exc.status_code)


@app.get("/api/health")
def health():
    return {"status":"ok", "api_framework":"FastAPI", "backend":"deterministic", "trained_model":False,
            "shadow_adapters_available":all((server.ROOT/f'models/evidence-{t}-{v}/run_manifest.json').exists() for t,v in [('harbor','v1'),('harbor','v2'),('cedar','v1')]),"model_delivery_enabled":False}


@app.get("/api/demo-config")
def demo_config():
    if server.PROFILE!='demo' or set(server.TOKENS)!={'demo-harbor-key','demo-cedar-key'}:
        raise HTTPException(404,'Demo credentials unavailable')
    return {"keys":{tenant:key for key,tenant in server.TOKENS.items()},'public_demo':bool(server.PUBLIC_ORIGIN),
            "policies":[p.public() for p in POLICIES.values()], "local_demo":True}


@app.get("/api/experiments")
def experiments(tenant=Depends(authenticated_tenant)):
    try:return load_experiments(server.ROOT)
    except (OSError,ValueError,TypeError,KeyError):
        raise HTTPException(503,'Measured reports unavailable; release approval withheld') from None


def trusted_context(body,tenant):
    if server.PROFILE=='demo': return body.context
    if body.context: raise HTTPException(400,'Caller-supplied business context is forbidden in service mode')
    if not body.ticket_id: raise HTTPException(400,'A tenant-owned support ticket is required')
    try:
        from .context_store import read
        return read(server.TRUSTED_DB,tenant,body.ticket_id)
    except LookupError:
        raise HTTPException(404,'Ticket not found for authenticated tenant') from None
    except (OSError,sqlite3.Error):
        raise HTTPException(503,'Trusted context unavailable; delivery withheld') from None


@app.post("/api/enforce")
def check(body: EnforcementRequest, tenant=Depends(authenticated_tenant)):
    if body.tenant is not None and body.tenant != tenant:
        raise HTTPException(403, "Tenant does not match authenticated key")
    start = time.perf_counter()
    try:
        result = enforce(body.message, trusted_context(body,tenant), tenant, body.version)
    except (ValueError, TypeError) as exc:
        raise HTTPException(400, str(exc)) from None
    result.update(evidence_id="ev_"+secrets.token_hex(8),
                  created_at=datetime.now(timezone.utc).isoformat(),
                  latency_ms=round((time.perf_counter()-start)*1000, 3))
    try:
        server.record(result)
    except (OSError, sqlite3.Error):
        raise HTTPException(503, "Evidence storage unavailable; output withheld") from None
    return result


@app.post('/api/shadow')
def shadow_check(body: EnforcementRequest, tenant=Depends(authenticated_tenant)):
    if body.tenant is not None and body.tenant != tenant:
        raise HTTPException(403, 'Tenant does not match authenticated key')
    try:resolve(tenant,body.version)
    except ValueError:raise HTTPException(400,'Unknown tenant policy version') from None
    if not (server.ROOT/f'models/evidence-{tenant}-{body.version}/run_manifest.json').exists():
        raise HTTPException(503, 'Trained adapter is not provisioned for this policy')
    try:
        from ml.evidence_runtime import shadow
        return shadow(body.message,trusted_context(body,tenant),tenant,body.version)
    except ValueError as exc:
        raise HTTPException(400,str(exc)) from None
    except (ImportError,OSError,RuntimeError,KeyError):
        raise HTTPException(503,'Research model unavailable; delivery remains disabled') from None


@app.get("/api/evidence")
def evidence(tenant=Depends(authenticated_tenant)):
    if server.PROFILE=='demo' and server.PUBLIC_ORIGIN:return {'events':[]}
    if not server.DB.exists():
        return {"events":[]}
    try:
        with closing(sqlite3.connect(server.DB)) as conn:
            events = [json.loads(row[0]) for row in conn.execute(
                "SELECT payload FROM evidence WHERE tenant=? ORDER BY rowid DESC LIMIT 30", (tenant,))]
    except (OSError, sqlite3.Error):
        raise HTTPException(503, "Evidence storage unavailable") from None
    return {"events":events}


@app.post("/api/evaluate")
def evaluate(body: EvaluationRequest, tenant=Depends(authenticated_tenant)):
    with server.EVAL_LOCK:
        return run(body.mode, server.CACHE)


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(server.ROOT/"web"/"index.html")


@app.get("/app.js", include_in_schema=False)
def javascript():
    return FileResponse(server.ROOT/"web"/"app.js", media_type="application/javascript")


@app.get("/styles.css", include_in_schema=False)
def css():
    return FileResponse(server.ROOT/"web"/"styles.css", media_type="text/css")
