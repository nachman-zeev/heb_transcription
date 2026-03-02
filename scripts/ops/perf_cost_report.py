from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path


def _fetch_json(url: str, timeout_sec: float) -> dict:
    req = urllib.request.Request(url=url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _to_markdown(summary: dict, monthly_budget: float) -> str:
    queue = summary.get("queue") or {}
    throughput = summary.get("throughput") or {}
    cost = summary.get("cost") or {}

    hourly = float(throughput.get("audio_minutes_per_hour", 0.0) or 0.0)
    monthly_audio_minutes = hourly * 24.0 * 30.0
    per_min = float(cost.get("estimated_cost_per_audio_minute", 0.0) or 0.0)
    projected_monthly = monthly_audio_minutes * per_min

    budget_ratio = 0.0
    if monthly_budget > 0:
        budget_ratio = projected_monthly / monthly_budget

    lines = [
        "# Performance and Cost Report",
        "",
        f"- workers_online: `{summary.get('workers_online', 0)}`",
        f"- queue_queued: `{queue.get('queued', 0)}`",
        f"- queue_processing: `{queue.get('processing', 0)}`",
        f"- queue_retry_wait: `{queue.get('retry_wait', 0)}`",
        f"- realtime_factor: `{throughput.get('realtime_factor', 0.0):.4f}`",
        f"- audio_minutes_per_hour: `{hourly:.2f}`",
        f"- estimated_cost_per_audio_minute: `{per_min:.6f}` {cost.get('currency', 'USD')}",
        f"- projected_monthly_cost: `{projected_monthly:.2f}` {cost.get('currency', 'USD')}",
        f"- budget_ratio: `{budget_ratio:.4f}`",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate performance/cost report from /perf/summary")
    parser.add_argument("--base-url", type=str, default="http://127.0.0.1:8080")
    parser.add_argument("--timeout-sec", type=float, default=5.0)
    parser.add_argument("--monthly-budget", type=float, default=0.0)
    parser.add_argument("--json-out", type=str, default="")
    parser.add_argument("--md-out", type=str, default="")
    args = parser.parse_args()

    summary = _fetch_json(args.base_url.rstrip("/") + "/perf/summary", max(0.2, args.timeout_sec))

    out = {
        "summary": summary,
        "monthly_budget": float(args.monthly_budget),
    }

    print(json.dumps(out, indent=2, ensure_ascii=False))

    if args.json_out:
        p = Path(args.json_out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.md_out:
        p = Path(args.md_out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(_to_markdown(summary, float(args.monthly_budget)), encoding="utf-8")


if __name__ == "__main__":
    main()
