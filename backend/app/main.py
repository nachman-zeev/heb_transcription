from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes_auth import router as auth_router
from app.api.routes_dashboard import router as dashboard_router
from app.api.routes_health import router as health_router
from app.api.routes_jobs import router as jobs_router
from app.api.routes_metrics import router as metrics_router
from app.api.routes_perf import router as perf_router
from app.api.routes_queue import router as queue_router
from app.api.routes_ws import router as ws_router
from app.core.config import get_settings
from app.database import init_db
from app.middleware.production import (
    HttpsEnforcerMiddleware,
    RateLimitMiddleware,
    RequestIdMiddleware,
    SecurityHeadersMiddleware,
)


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.9.0")


@app.on_event("startup")
def startup_event() -> None:
    init_db()


app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(SecurityHeadersMiddleware, enabled=settings.security_headers_enabled)
app.add_middleware(HttpsEnforcerMiddleware, enforce_https=settings.enforce_https)
app.add_middleware(
    RateLimitMiddleware,
    enabled=settings.rate_limit_enabled,
    window_seconds=settings.rate_limit_window_seconds,
    max_requests=settings.rate_limit_max_requests,
    auth_max_requests=settings.rate_limit_auth_max_requests,
)


static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(static_dir / "index.html")


app.include_router(health_router)
app.include_router(metrics_router)
app.include_router(perf_router)
app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(queue_router)
app.include_router(dashboard_router)
app.include_router(ws_router)
