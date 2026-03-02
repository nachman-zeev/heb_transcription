from __future__ import annotations

import argparse
import json
from pathlib import Path

from slo_monitor import collect_runtime_snapshot_safe


DEFAULT_POLICY = {
    "max_queued": 500,
    "max_retry_wait": 200,
    "max_dead_letter": 20,
    "max_error_ratio": 0.20,
    "min_workers_online": 1,
    "max_cpu_percent": 95.0,
    "max_ram_percent": 95.0,
}


def _load_policy(policy_file: str) -> dict:
    p = Path(policy_file)
    if not p.exists():
        return dict(DEFAULT_POLICY)

    data = json.loads(p.read_text(encoding="utf-8"))
    out = dict(DEFAULT_POLICY)
    for k in DEFAULT_POLICY:
        if k in data:
            out[k] = data[k]
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate alert policies from runtime snapshot")
    parser.add_argument("--base-url", type=str, default="http://127.0.0.1:8080")
    parser.add_argument("--timeout-sec", type=float, default=5.0)
    parser.add_argument("--policy-file", type=str, default="config/alert_policy.json")
    parser.add_argument("--json-out", type=str, default="")
    args = parser.parse_args()

    policy = _load_policy(args.policy_file)

    snapshot, err = collect_runtime_snapshot_safe(args.base_url, timeout_sec=max(0.2, args.timeout_sec))
    if err:
        out = {"status": "alert", "alerts": [f"collection_failed:{err}"], "policy": policy}
        print(json.dumps(out, ensure_ascii=False))
        if args.json_out:
            Path(args.json_out).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        raise SystemExit(2)

    alerts: list[str] = []
    q = snapshot.get("queue") or {}
    m = snapshot.get("metrics") or {}
    r = snapshot.get("resources") or {}

    if snapshot.get("health_status") != "ok":
        alerts.append("health_not_ok")

    if int(q.get("queued", 0)) > int(policy["max_queued"]):
        alerts.append(f"queued_too_high:{q.get('queued')}>{policy['max_queued']}")

    if int(q.get("retry_wait", 0)) > int(policy["max_retry_wait"]):
        alerts.append(f"retry_wait_too_high:{q.get('retry_wait')}>{policy['max_retry_wait']}")

    if int(q.get("dead_letter", 0)) > int(policy["max_dead_letter"]):
        alerts.append(f"dead_letter_too_high:{q.get('dead_letter')}>{policy['max_dead_letter']}")

    if float(m.get("error_ratio", 0.0)) > float(policy["max_error_ratio"]):
        alerts.append(f"error_ratio_too_high:{m.get('error_ratio')}>{policy['max_error_ratio']}")

    if int(snapshot.get("workers_online", 0)) < int(policy["min_workers_online"]):
        alerts.append(f"workers_online_too_low:{snapshot.get('workers_online')}<{policy['min_workers_online']}")

    if float(r.get("cpu_percent", 0.0)) > float(policy["max_cpu_percent"]):
        alerts.append(f"cpu_too_high:{r.get('cpu_percent')}>{policy['max_cpu_percent']}")

    if float(r.get("ram_percent", 0.0)) > float(policy["max_ram_percent"]):
        alerts.append(f"ram_too_high:{r.get('ram_percent')}>{policy['max_ram_percent']}")

    out = {
        "status": "ok" if not alerts else "alert",
        "alerts": alerts,
        "policy": policy,
        "snapshot": snapshot,
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))

    if args.json_out:
        p = Path(args.json_out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    if alerts:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
