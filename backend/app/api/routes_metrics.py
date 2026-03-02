from __future__ import annotations

from fastapi import APIRouter, Response

from app.services.metrics_store import runtime_metrics


router = APIRouter(tags=["metrics"])


@router.get("/metrics")
def metrics() -> Response:
    payload = runtime_metrics.as_prometheus()
    return Response(content=payload, media_type="text/plain; version=0.0.4; charset=utf-8")
