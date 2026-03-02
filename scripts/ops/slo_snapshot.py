from __future__ import annotations

import argparse
import json
from pathlib import Path

from slo_monitor import collect_runtime_snapshot


def _to_markdown(snapshot: dict) -> str:
    q = snapshot.get("queue") or {}
    m = snapshot.get("metrics") or {}
    r = snapshot.get("resources") or {}

    lines = [
        "# SLO Snapshot",
        "",
        f"- timestamp_utc: `{snapshot.get('timestamp_utc')}`",
        f"- health_status: `{snapshot.get('health_status')}`",
        f"- workers_online: `{snapshot.get('workers_online')}`",
        "",
        "## Queue",
        "",
        f"- queued: `{q.get('queued', 0)}`",
        f"- processing: `{q.get('processing', 0)}`",
        f"- retry_wait: `{q.get('retry_wait', 0)}`",
        f"- dead_letter: `{q.get('dead_letter', 0)}`",
        "",
        "## Metrics",
        "",
        f"- jobs_completed_total: `{m.get('jobs_completed_total', 0)}`",
        f"- jobs_failed_total: `{m.get('jobs_failed_total', 0)}`",
        f"- jobs_dead_letter_total: `{m.get('jobs_dead_letter_total', 0)}`",
        f"- retries_scheduled_total: `{m.get('retries_scheduled_total', 0)}`",
        f"- error_ratio: `{m.get('error_ratio', 0.0):.4f}`",
        f"- uptime_seconds: `{m.get('uptime_seconds', 0.0):.2f}`",
        "",
        "## Resources",
        "",
        f"- cpu_percent: `{r.get('cpu_percent', 0.0)}`",
        f"- ram_percent: `{r.get('ram_percent', 0.0)}`",
        f"- gpu_available: `{r.get('gpu_available', False)}`",
        f"- gpu_memory_used_percent: `{r.get('gpu_memory_used_percent', 0.0)}`",
        f"- recommended_workers: `{r.get('recommended_workers', 0)}`",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate SLO snapshot report")
    parser.add_argument("--base-url", type=str, default="http://127.0.0.1:8080")
    parser.add_argument("--timeout-sec", type=float, default=5.0)
    parser.add_argument("--json-out", type=str, default="")
    parser.add_argument("--md-out", type=str, default="")
    args = parser.parse_args()

    snapshot = collect_runtime_snapshot(base_url=args.base_url, timeout_sec=max(0.2, args.timeout_sec))

    print(json.dumps(snapshot, indent=2, ensure_ascii=False))

    if args.json_out:
        p = Path(args.json_out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.md_out:
        p = Path(args.md_out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(_to_markdown(snapshot), encoding="utf-8")


if __name__ == "__main__":
    main()
