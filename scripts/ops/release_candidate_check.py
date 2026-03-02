from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def _run(command: list[str], cwd: str, env: dict[str, str] | None = None, timeout_sec: int = 300) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        out = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        return proc.returncode == 0, out.strip()
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def _step_compileall(repo_root: str) -> dict:
    ok, out = _run([sys.executable, "-m", "compileall", "backend", "scripts"], cwd=repo_root)
    return {"step": "compileall", "ok": ok, "details": out[-4000:]}


def _step_preflight(repo_root: str) -> dict:
    env = os.environ.copy()
    env["APP_ENV"] = env.get("APP_ENV", "prod")
    env["DB_URL"] = env.get("DB_URL", "sqlite:///./backend/data/app.db")
    env["PRIMARY_MODEL_ID"] = env.get("PRIMARY_MODEL_ID", "ivrit-ai/whisper-large-v3")
    ok, out = _run(
        [sys.executable, "scripts/ops/preflight_check.py", "--recordings-path", "Recordings Examples"],
        cwd=repo_root,
        env=env,
    )
    return {"step": "preflight", "ok": ok, "details": out[-4000:]}


def _step_api_smoke(repo_root: str) -> dict:
    script = r'''
import json
import os
import tempfile
import wave
from pathlib import Path

os.environ['APP_ENV'] = 'prod'
os.environ['DB_URL'] = 'sqlite:///./data/rc_check.db'
os.environ['PRIMARY_MODEL_ID'] = 'ivrit-ai/whisper-large-v3'
os.environ['RATE_LIMIT_ENABLED'] = 'false'

from app.main import app
from app.database import init_db
from fastapi.testclient import TestClient

init_db()
client = TestClient(app)

boot = client.post('/auth/bootstrap', json={
    'tenant_name': 'rc-tenant',
    'email': 'rc@demo.local',
    'password': 'Passw0rd!123'
})
if boot.status_code not in (200, 400):
    raise RuntimeError(f'bootstrap_failed:{boot.status_code}:{boot.text}')

login = client.post('/auth/login', json={
    'tenant_name': 'rc-tenant',
    'email': 'rc@demo.local',
    'password': 'Passw0rd!123'
})
if login.status_code != 200:
    raise RuntimeError(f'login_failed:{login.status_code}:{login.text}')

token = login.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

checks = {}
for path in ['/health/live','/health/ready','/health','/perf/summary','/metrics','/auth/me','/queue/stats']:
    r = client.get(path, headers=headers if path.startswith('/auth') or path.startswith('/queue') else None)
    checks[path] = r.status_code
    if r.status_code != 200:
        raise RuntimeError(f'endpoint_failed:{path}:{r.status_code}:{r.text}')

fd, wav = tempfile.mkstemp(suffix='.wav')
os.close(fd)
with wave.open(wav, 'wb') as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(16000)
    w.writeframes(b'\x00\x00' * 1600)

j = client.post('/jobs', json={'file_path': wav, 'priority': 100}, headers=headers)
if j.status_code != 200:
    raise RuntimeError(f'create_job_failed:{j.status_code}:{j.text}')

Path(wav).unlink(missing_ok=True)
print(json.dumps({'ok': True, 'checks': checks, 'job_id': j.json().get('id')}))
'''
    ok, out = _run([sys.executable, "-c", script], cwd=os.path.join(repo_root, "backend"))
    return {"step": "api_smoke", "ok": ok, "details": out[-4000:]}


def _step_worker_manager(repo_root: str) -> dict:
    ok, out = _run(
        [sys.executable, "worker_manager.py", "--max-ticks", "2", "--node-id", "rc-node"],
        cwd=os.path.join(repo_root, "backend"),
    )
    return {"step": "worker_manager_smoke", "ok": ok, "details": out[-4000:]}


def _step_ops_backup_restore(repo_root: str) -> dict:
    backup_cmd = [
        sys.executable,
        "scripts/ops/backup_sqlite.py",
        "--db-path",
        "backend/data/app.db",
        "--out-dir",
        "data/backups_rc",
    ]
    ok1, out1 = _run(backup_cmd, cwd=repo_root)

    backup_files = sorted(Path(repo_root, "data", "backups_rc").glob("app_*.sqlite"))
    if not ok1 or not backup_files:
        return {"step": "ops_backup_restore", "ok": False, "details": (out1 or "backup_missing")[-4000:]}

    restore_cmd = [
        sys.executable,
        "scripts/ops/restore_sqlite.py",
        "--backup-path",
        str(backup_files[-1]),
        "--target-db-path",
        "backend/data/rc_restore.db",
        "--force",
    ]
    ok2, out2 = _run(restore_cmd, cwd=repo_root)
    ok = ok1 and ok2
    return {"step": "ops_backup_restore", "ok": ok, "details": ((out1 + "\n" + out2).strip())[-4000:]}


def _step_ops_migration(repo_root: str) -> dict:
    cmd = [
        sys.executable,
        "scripts/ops/migrate_sqlite_to_postgres.py",
        "--sqlite-url",
        "sqlite:///./backend/data/app.db",
        "--postgres-url",
        "sqlite:///./data/rc_migration_target.db",
        "--truncate-target",
    ]
    ok, out = _run(cmd, cwd=repo_root)
    return {"step": "ops_migration_dry", "ok": ok, "details": out[-4000:]}


def _wait_http_ok(url: str, timeout_sec: int = 15) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.25)
    return False


def _step_perf_report(repo_root: str) -> dict:
    backend_dir = os.path.join(repo_root, "backend")
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8110"],
        cwd=backend_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        if not _wait_http_ok("http://127.0.0.1:8110/health", timeout_sec=15):
            return {"step": "perf_cost_report", "ok": False, "details": "server_not_ready"}

        ok, out = _run(
            [
                sys.executable,
                "scripts/ops/perf_cost_report.py",
                "--base-url",
                "http://127.0.0.1:8110",
                "--monthly-budget",
                "1000",
                "--json-out",
                "data/release/perf_cost_report.json",
                "--md-out",
                "data/release/perf_cost_report.md",
            ],
            cwd=repo_root,
        )
        return {"step": "perf_cost_report", "ok": ok, "details": out[-4000:]}
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except Exception:
            server.kill()


def _to_markdown(report: dict) -> str:
    lines = [
        "# Release Candidate Report",
        "",
        f"- generated_at_utc: `{report['generated_at_utc']}`",
        f"- overall_status: `{report['overall_status']}`",
        "",
        "## Steps",
        "",
    ]
    for step in report["steps"]:
        status = "PASS" if step["ok"] else "FAIL"
        lines.append(f"- `{step['step']}`: **{status}**")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- Primary model policy remains `ivrit-ai/whisper-large-v3`.")
    lines.append("- This report is generated by `scripts/ops/release_candidate_check.py`.")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Stage-10 release candidate checks")
    parser.add_argument("--repo-root", type=str, default=".")
    parser.add_argument("--json-out", type=str, default="data/release/release_candidate_report.json")
    parser.add_argument("--md-out", type=str, default="data/release/release_candidate_report.md")
    args = parser.parse_args()

    repo_root = str(Path(args.repo_root).resolve())

    steps = [
        _step_compileall(repo_root),
        _step_preflight(repo_root),
        _step_api_smoke(repo_root),
        _step_worker_manager(repo_root),
        _step_ops_backup_restore(repo_root),
        _step_ops_migration(repo_root),
        _step_perf_report(repo_root),
    ]

    overall_ok = all(s["ok"] for s in steps)
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "overall_status": "pass" if overall_ok else "fail",
        "steps": steps,
    }

    out_json = Path(args.json_out)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    out_md = Path(args.md_out)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_to_markdown(report), encoding="utf-8")

    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not overall_ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
