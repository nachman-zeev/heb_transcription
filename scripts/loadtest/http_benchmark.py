from __future__ import annotations

import argparse
import concurrent.futures
import statistics
import time
import urllib.error
import urllib.request


def _one_request(url: str, timeout_sec: float) -> tuple[bool, float, int]:
    start = time.perf_counter()
    code = 0
    try:
        req = urllib.request.Request(url=url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            code = int(resp.status)
            ok = 200 <= code < 300
    except urllib.error.HTTPError as e:
        code = int(e.code)
        ok = False
    except Exception:
        ok = False
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return ok, elapsed_ms, code


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = int((p / 100.0) * (len(sorted_vals) - 1))
    return float(sorted_vals[max(0, min(idx, len(sorted_vals) - 1))])


def run_load(base_url: str, endpoint: str, total_requests: int, concurrency: int, timeout_sec: float) -> int:
    url = base_url.rstrip("/") + endpoint

    latencies: list[float] = []
    ok_count = 0
    status_counts: dict[int, int] = {}

    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, concurrency)) as ex:
        futures = [ex.submit(_one_request, url, timeout_sec) for _ in range(total_requests)]
        for fut in concurrent.futures.as_completed(futures):
            ok, latency, code = fut.result()
            latencies.append(latency)
            if ok:
                ok_count += 1
            status_counts[code] = status_counts.get(code, 0) + 1

    total_time = max(1e-9, time.perf_counter() - started)
    rps = total_requests / total_time
    fail_count = total_requests - ok_count

    print(f"url={url}")
    print(f"requests_total={total_requests}")
    print(f"concurrency={concurrency}")
    print(f"ok={ok_count}")
    print(f"failed={fail_count}")
    print(f"rps={rps:.2f}")
    print(f"latency_ms_avg={statistics.fmean(latencies):.2f}" if latencies else "latency_ms_avg=0")
    print(f"latency_ms_p50={_percentile(latencies, 50):.2f}")
    print(f"latency_ms_p95={_percentile(latencies, 95):.2f}")
    print(f"latency_ms_p99={_percentile(latencies, 99):.2f}")
    print(f"status_counts={status_counts}")

    return 0 if fail_count == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Basic HTTP load test (Stage 5)")
    parser.add_argument("--base-url", type=str, default="http://127.0.0.1:8080")
    parser.add_argument("--endpoint", type=str, default="/health")
    parser.add_argument("--requests", type=int, default=500)
    parser.add_argument("--concurrency", type=int, default=30)
    parser.add_argument("--timeout-sec", type=float, default=5.0)
    args = parser.parse_args()

    raise SystemExit(
        run_load(
            base_url=args.base_url,
            endpoint=args.endpoint,
            total_requests=max(1, args.requests),
            concurrency=max(1, args.concurrency),
            timeout_sec=max(0.2, args.timeout_sec),
        )
    )


if __name__ == "__main__":
    main()
