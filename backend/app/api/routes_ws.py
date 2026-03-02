from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import Job
from app.security import resolve_token_user
from app.services.heartbeat import count_online_workers


router = APIRouter(tags=["ws"])


def _build_payload(tenant_id: int) -> dict:
    with SessionLocal() as db:
        queued = int(db.scalar(select(func.count(Job.id)).where(Job.tenant_id == tenant_id, Job.status == "queued")) or 0)
        processing = int(db.scalar(select(func.count(Job.id)).where(Job.tenant_id == tenant_id, Job.status == "processing")) or 0)
        retry_wait = int(db.scalar(select(func.count(Job.id)).where(Job.tenant_id == tenant_id, Job.status == "retry_wait")) or 0)
        completed = int(db.scalar(select(func.count(Job.id)).where(Job.tenant_id == tenant_id, Job.status == "completed")) or 0)
        failed = int(db.scalar(select(func.count(Job.id)).where(Job.tenant_id == tenant_id, Job.status == "failed")) or 0)
        dead_letter = int(db.scalar(select(func.count(Job.id)).where(Job.tenant_id == tenant_id, Job.status == "dead_letter")) or 0)

        workers_online = count_online_workers(db)

        recent = list(
            db.execute(
                select(Job.id, Job.status, Job.source_filename, Job.queued_at, Job.completed_at)
                .where(Job.tenant_id == tenant_id)
                .order_by(Job.created_at.desc())
                .limit(20)
            ).all()
        )

    return {
        "type": "tenant_update",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "queue": {
            "queued": queued,
            "processing": processing,
            "retry_wait": retry_wait,
            "completed": completed,
            "failed": failed,
            "dead_letter": dead_letter,
        },
        "workers_online": workers_online,
        "recent_jobs": [
            {
                "id": r.id,
                "status": r.status,
                "source_filename": r.source_filename,
                "queued_at": r.queued_at.isoformat() if r.queued_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            }
            for r in recent
        ],
    }


@router.websocket("/ws/tenant")
async def tenant_ws(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401)
        return

    with SessionLocal() as db:
        user = resolve_token_user(db, token)

    if not user:
        await websocket.close(code=4401)
        return

    tenant_id = user.tenant_id
    await websocket.accept()

    try:
        while True:
            payload = _build_payload(tenant_id)
            await websocket.send_json(payload)
            await asyncio.sleep(2.0)
    except WebSocketDisconnect:
        return
