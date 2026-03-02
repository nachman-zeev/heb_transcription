from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone


def _fetch_text(url: str, timeout_sec: float) -> str:
    req = urllib.request.Request(url=url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _fetch_json(url: str, timeout_sec: float) -> dict:
    payload = _fetch_text(url, timeout_sec)
    return json.loads(payload)


def parse_prometheus_text(text: str) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        name = parts[0].strip()
        val = parts[-1].strip()
        try:
            metrics[name] = float(val)
        except ValueError:
            continue
    return metrics


def collect_runtime_snapshot(base_url: str, timeout_sec: float = 5.0) -> dict:
    base = base_url.rstrip("/")
    ts = datetime.now(timezone.utc).isoformat()

    health = _fetch_json(f"{base}/health", timeout_sec)
    metrics_text = _fetch_text(f"{base}/metrics", timeout_sec)
    metrics = parse_prometheus_text(metrics_text)

    queue = (health.get("details") or {}).get("queue") or {}
    completed = float(metrics.get("app_jobs_completed_total", 0.0))
    failed = float(metrics.get("app_jobs_failed_total", 0.0))
    dead_letter = float(metrics.get("app_jobs_dead_letter_total", 0.0))

    terminal = max(1.0, completed + failed)
    error_ratio = failed / terminal

    return {
        "timestamp_utc": ts,
        "health_status": health.get("status", "unknown"),
        "queue": {
            "queued": int(queue.get("queued", 0) or 0),
            "processing": int(queue.get("processing", 0) or 0),
            "retry_wait": int(queue.get("retry_wait", 0) or 0),
            "dead_letter": int(queue.get("dead_letter", 0) or 0),
        },
        "workers_online": int((health.get("details") or {}).get("workers_online", 0) or 0),
        "resources": (health.get("details") or {}).get("resources") or {},
        "metrics": {
            "jobs_completed_total": int(completed),
            "jobs_failed_total": int(failed),
            "jobs_dead_letter_total": int(dead_letter),
            "retries_scheduled_total": int(metrics.get("app_retries_scheduled_total", 0.0)),
            "uptime_seconds": float(metrics.get("app_uptime_seconds", 0.0)),
            "error_ratio": float(error_ratio),
        },
    }


def collect_runtime_snapshot_safe(base_url: str, timeout_sec: float = 5.0) -> tuple[dict | None, str | None]:
    try:
        return collect_runtime_snapshot(base_url=base_url, timeout_sec=timeout_sec), None
    except urllib.error.HTTPError as exc:
        return None, f"http_error:{exc.code}"
    except Exception as exc:  # noqa: BLE001
        return None, f"collection_error:{exc}"
