#!/usr/bin/env python3
"""
PASS-7 — Load probe (real-HTTP).

Fires a configurable number of concurrent ``login → /me → /elins/preview
→ /me`` flows against a running ClarityOS HTTP server (default
``http://localhost:8080``) and prints aggregate latency + error
metrics.

This script is **observational**. It changes no runtime state beyond
what a real client would (registers + logs in as ephemeral users,
performs a single ELINS preview each). Use it locally against a
dev instance — do NOT point it at production.

Usage:

    # Boot the runtime in another shell:
    uvicorn app:app --host 0.0.0.0 --port 8080

    # Then drive the probe:
    python scripts/run_load_probe.py
    python scripts/run_load_probe.py --concurrency 25 --flows 100
    python scripts/run_load_probe.py --base-url http://localhost:8080 \\
        --timeout 30 --concurrency 50

stdlib-only (urllib.request + concurrent.futures + statistics).
No external dependencies — runs in the same Python 3.12 env the
runtime uses.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import statistics
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Tiny HTTP client over stdlib urllib
# ---------------------------------------------------------------------------
@dataclass
class HttpResponse:
    status: int
    body: Optional[dict]
    duration_s: float
    error: Optional[str] = None


def _http(
    method: str,
    url: str,
    *,
    headers: Optional[dict] = None,
    body: Optional[dict] = None,
    timeout_s: float = 30.0,
) -> HttpResponse:
    started = time.perf_counter()
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read()
            status = resp.status
    except urllib.error.HTTPError as e:
        return HttpResponse(
            status=e.code,
            body=None,
            duration_s=time.perf_counter() - started,
            error=f"HTTPError {e.code}: {e.reason}",
        )
    except Exception as e:
        return HttpResponse(
            status=0,
            body=None,
            duration_s=time.perf_counter() - started,
            error=f"{type(e).__name__}: {e}",
        )

    try:
        parsed = json.loads(raw.decode("utf-8")) if raw else None
    except json.JSONDecodeError as e:
        return HttpResponse(
            status=status,
            body=None,
            duration_s=time.perf_counter() - started,
            error=f"JSONDecodeError: {e}",
        )
    return HttpResponse(
        status=status,
        body=parsed,
        duration_s=time.perf_counter() - started,
    )


# ---------------------------------------------------------------------------
# Flow definition
# ---------------------------------------------------------------------------
@dataclass
class FlowResult:
    idx: int
    user: str
    ok: bool
    elapsed_s: float
    step_durations: dict[str, float] = field(default_factory=dict)
    step_statuses: dict[str, int] = field(default_factory=dict)
    error: Optional[str] = None
    last_model_used: Optional[str] = None


def _run_one_flow(
    base_url: str,
    idx: int,
    timeout_s: float,
) -> FlowResult:
    """One full vertical: register + login + /me + /elins/preview + /me.

    Uses a unique username per flow; passwords are throwaway. Each
    step's duration + status is recorded so the aggregator can build
    per-step percentiles if needed.
    """
    username = f"loadprobe_{int(time.time() * 1000)}_{idx:05d}_{secrets.token_hex(4)}"
    flow_started = time.perf_counter()
    result = FlowResult(idx=idx, user=username, ok=False, elapsed_s=0.0)

    # 1. Register (idempotent-ish — if /register is invite-only the
    # script can't proceed; document via the error field).
    r_reg = _http(
        "POST", f"{base_url}/register",
        body={"username": username, "password": "loadprobe"},
        timeout_s=timeout_s,
    )
    result.step_durations["register"] = r_reg.duration_s
    result.step_statuses["register"] = r_reg.status
    if r_reg.status >= 400 and r_reg.status != 409:
        result.error = f"register failed: {r_reg.error or r_reg.status}"
        result.elapsed_s = time.perf_counter() - flow_started
        return result

    # 2. Login.
    r_login = _http(
        "POST", f"{base_url}/login",
        body={"username": username, "password": "loadprobe"},
        timeout_s=timeout_s,
    )
    result.step_durations["login"] = r_login.duration_s
    result.step_statuses["login"] = r_login.status
    if r_login.status != 200 or not r_login.body or "session_id" not in r_login.body:
        result.error = f"login failed: {r_login.error or r_login.status}"
        result.elapsed_s = time.perf_counter() - flow_started
        return result
    sid = r_login.body["session_id"]
    hdrs = {"X-Session-ID": sid}

    # 3. /me.
    r_me1 = _http("GET", f"{base_url}/me", headers=hdrs, timeout_s=timeout_s)
    result.step_durations["me_1"] = r_me1.duration_s
    result.step_statuses["me_1"] = r_me1.status
    if r_me1.status != 200:
        result.error = f"me_1 failed: {r_me1.error or r_me1.status}"
        result.elapsed_s = time.perf_counter() - flow_started
        return result

    # 4. /elins/preview.
    r_prev = _http(
        "POST", f"{base_url}/elins/preview", headers=hdrs,
        body={"text": "trust between partners is eroding"},
        timeout_s=timeout_s,
    )
    result.step_durations["preview"] = r_prev.duration_s
    result.step_statuses["preview"] = r_prev.status
    if r_prev.status != 200:
        result.error = f"preview failed: {r_prev.error or r_prev.status}"
        result.elapsed_s = time.perf_counter() - flow_started
        return result

    # 5. /me again.
    r_me2 = _http("GET", f"{base_url}/me", headers=hdrs, timeout_s=timeout_s)
    result.step_durations["me_2"] = r_me2.duration_s
    result.step_statuses["me_2"] = r_me2.status
    if r_me2.status != 200:
        result.error = f"me_2 failed: {r_me2.error or r_me2.status}"
        result.elapsed_s = time.perf_counter() - flow_started
        return result

    # Capture last_model_used for the post-flow invariant.
    if r_me2.body and isinstance(r_me2.body.get("intelligence_kernel"), dict):
        result.last_model_used = r_me2.body["intelligence_kernel"].get("last_model_used")

    result.ok = True
    result.elapsed_s = time.perf_counter() - flow_started
    return result


# ---------------------------------------------------------------------------
# Percentile helper (stdlib statistics doesn't give quantiles
# directly until 3.8, but we have 3.12 — use statistics.quantiles).
# ---------------------------------------------------------------------------
def _percentile(values: list[float], p: float) -> float:
    """Approximate percentile via nearest-rank. Inputs are seconds."""
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    # Nearest-rank — matches what pytest's load-envelope test prints.
    idx = max(0, min(len(s) - 1, int(round(p * len(s))) - 1))
    return s[idx]


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------
def _print_summary(
    base_url: str,
    concurrency: int,
    flows: int,
    timeout_s: float,
    burst_s: float,
    results: list[FlowResult],
) -> None:
    total = len(results)
    ok = sum(1 for r in results if r.ok)
    fail = total - ok

    # Latency.
    all_elapsed = [r.elapsed_s for r in results]
    ok_elapsed = [r.elapsed_s for r in results if r.ok]
    p50_all = _percentile(all_elapsed, 0.50)
    p95_all = _percentile(all_elapsed, 0.95)
    p99_all = _percentile(all_elapsed, 0.99)
    p50_ok  = _percentile(ok_elapsed, 0.50)
    p95_ok  = _percentile(ok_elapsed, 0.95)

    # Per-step p95 for ok flows.
    step_p95: dict[str, float] = {}
    if ok_elapsed:
        for step in ("register", "login", "me_1", "preview", "me_2"):
            xs = [r.step_durations.get(step, 0.0) for r in results if r.ok]
            xs = [x for x in xs if x > 0]
            if xs:
                step_p95[step] = _percentile(xs, 0.95)

    # Error histogram.
    err_hist: dict[str, int] = {}
    for r in results:
        if not r.ok and r.error:
            # Bucket by error category (HTTPError, connection refused, etc.).
            cat = r.error.split(":", 1)[0]
            err_hist[cat] = err_hist.get(cat, 0) + 1

    # Status-code histogram across all steps.
    status_hist: dict[int, int] = {}
    for r in results:
        for code in r.step_statuses.values():
            status_hist[code] = status_hist.get(code, 0) + 1

    print()
    print("=" * 72)
    print(" ClarityOS load probe — summary")
    print("=" * 72)
    print(f" target            : {base_url}")
    print(f" concurrency       : {concurrency}")
    print(f" total flows       : {flows}")
    print(f" per-call timeout  : {timeout_s:.1f}s")
    print(f" burst wall-clock  : {burst_s:.2f}s")
    print("-" * 72)
    print(f" ok                : {ok}/{total}  ({100.0 * ok / max(total, 1):.1f}%)")
    print(f" failed            : {fail}")
    print("-" * 72)
    print(" latency (all flows, end-to-end)")
    print(f"   p50             : {p50_all * 1000:.0f} ms")
    print(f"   p95             : {p95_all * 1000:.0f} ms")
    print(f"   p99             : {p99_all * 1000:.0f} ms")
    if ok_elapsed:
        print(" latency (ok flows only)")
        print(f"   p50             : {p50_ok * 1000:.0f} ms")
        print(f"   p95             : {p95_ok * 1000:.0f} ms")
    if step_p95:
        print("-" * 72)
        print(" per-step p95 (ok flows)")
        for step, p in step_p95.items():
            print(f"   {step:<10}      : {p * 1000:.0f} ms")
    print("-" * 72)
    print(" HTTP status histogram (across every request issued)")
    for code in sorted(status_hist):
        print(f"   {code if code else '(transport)':<10}      : {status_hist[code]}")
    if err_hist:
        print("-" * 72)
        print(" error category histogram")
        for cat, n in sorted(err_hist.items(), key=lambda kv: -kv[1]):
            print(f"   {cat:<28}: {n}")
    if fail:
        print("-" * 72)
        print(" sample failures (up to 5)")
        for r in [x for x in results if not x.ok][:5]:
            print(f"   #{r.idx:04d} user={r.user!r}: {r.error}")
    print("=" * 72)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="ClarityOS PASS-7 load probe (observational)."
    )
    ap.add_argument(
        "--base-url",
        default=os.environ.get("CLARITYOS_LOAD_PROBE_URL", "http://localhost:8080"),
        help="HTTP base URL of the dev/staging runtime (default: http://localhost:8080)",
    )
    ap.add_argument(
        "--concurrency", type=int, default=20,
        help="Max parallel workers (default: 20)",
    )
    ap.add_argument(
        "--flows", type=int, default=50,
        help="Total flows to drive (default: 50)",
    )
    ap.add_argument(
        "--timeout", type=float, default=30.0,
        help="Per-call timeout in seconds (default: 30.0)",
    )
    ap.add_argument(
        "--quiet", action="store_true",
        help="Suppress per-flow progress lines",
    )
    args = ap.parse_args(argv)

    if args.concurrency < 1:
        print("--concurrency must be >= 1", file=sys.stderr)
        return 2
    if args.flows < 1:
        print("--flows must be >= 1", file=sys.stderr)
        return 2

    print(
        f"driving {args.flows} flows at concurrency={args.concurrency} "
        f"against {args.base_url} ...",
        file=sys.stderr,
    )

    results: list[FlowResult] = []
    burst_started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = [
            ex.submit(_run_one_flow, args.base_url, i, args.timeout)
            for i in range(args.flows)
        ]
        for f in as_completed(futs):
            r = f.result()
            results.append(r)
            if not args.quiet:
                mark = "ok" if r.ok else "FAIL"
                print(
                    f"  flow #{r.idx:04d} {mark} "
                    f"({r.elapsed_s * 1000:.0f}ms) "
                    f"{(r.error or '').splitlines()[0] if r.error else ''}",
                    file=sys.stderr,
                )
    burst_s = time.perf_counter() - burst_started

    _print_summary(
        base_url=args.base_url,
        concurrency=args.concurrency,
        flows=args.flows,
        timeout_s=args.timeout,
        burst_s=burst_s,
        results=results,
    )

    # Exit non-zero if any flow failed — makes the script useful as a
    # smoke-check in a deploy pipeline.
    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
