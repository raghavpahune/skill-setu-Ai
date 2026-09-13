#!/usr/bin/env python3
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

DEFAULT_BACKEND_URL = "https://skill-setu-backend-jklo.onrender.com"
DEFAULT_FRONTEND_URL = "https://skill-setu-rust.vercel.app"
DEFAULT_HEALTH_URL = f"{DEFAULT_BACKEND_URL}/api/health"


def fetch_url(url: str, timeout: float = 20.0, headers: dict | None = None) -> tuple[int, str, float, dict]:
    req_headers = {"User-Agent": "SkillSetu-Preflight-Probe/1.0", "Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            elapsed_ms = (time.time() - t0) * 1000
            status = response.status
            body = response.read().decode("utf-8", errors="ignore")
            resp_headers = dict(response.headers)
            return status, body, elapsed_ms, resp_headers
    except urllib.error.HTTPError as e:
        elapsed_ms = (time.time() - t0) * 1000
        body = e.read().decode("utf-8", errors="ignore") if hasattr(e, "read") else ""
        return e.code, body, elapsed_ms, dict(e.headers) if hasattr(e, "headers") else {}
    except Exception as e:
        elapsed_ms = (time.time() - t0) * 1000
        return 0, str(e), elapsed_ms, {}


def probe_backend(url: str = DEFAULT_HEALTH_URL, max_retries: int = 5, retry_delay: float = 4.0):
    print("=" * 70)
    print("SKILLSETU SIH DEMO PRE-FLIGHT WARMUP")
    print(f"Target URL : {url}")
    print(f"Max Retries: {max_retries}")
    print("=" * 70)

    for attempt in range(1, max_retries + 1):
        print(f"\n[Attempt {attempt}/{max_retries}] Pinging backend health endpoint...")
        status, body, elapsed_ms, _ = fetch_url(url, timeout=25.0)

        if status == 200:
            try:
                data = json.loads(body)
            except Exception:
                data = {}
            is_cold = elapsed_ms > 4000.0
            resp_type = "COLD START RECOVERY" if is_cold else "WARM INSTANT"
            print(f"  --> HTTP {status} OK ({elapsed_ms:.1f} ms) [{resp_type}]")
            print("-" * 70)
            print(f"  Service Status     : {str(data.get('status', 'unknown')).upper()}")
            print(f"  Supabase Connected : {data.get('supabase_connected', False)}")
            print(f"  AI Available       : {data.get('ai_available', False)}")
            print(f"  Records In-Memory  : {data.get('records_loaded', 0)}")
            print(f"  Demo Mode Overlay  : {data.get('demo_mode', False)}")
            print(f"  Active Districts   : {data.get('districts_count', 0)}")
            print("-" * 70)
            print("SUCCESS: Production backend is warm and ready for presentation!")
            print("=" * 70)
            return True, data, elapsed_ms
        else:
            print(f"  --> HTTP {status} ({elapsed_ms:.1f} ms). Retrying in {retry_delay}s...")

        if attempt < max_retries:
            time.sleep(retry_delay)

    print("\nFAILED: Backend could not be reached or confirmed within specified retries.")
    return False, {}, 0.0


def run_preflight_suite(backend_url: str = DEFAULT_BACKEND_URL, frontend_url: str = DEFAULT_FRONTEND_URL) -> bool:
    print("\n" + "=" * 70)
    print("STARTING FULL PRE-DEMO READINESS CHECKLIST")
    print("=" * 70)

    checks_passed = 0
    checks_warn = 0
    checks_failed = 0

    def record_result(status: str, title: str, details: str = ""):
        nonlocal checks_passed, checks_warn, checks_failed
        tag = f"[{status}]"
        if status == "PASS":
            checks_passed += 1
            print(f"{tag:<8} {title:<45} {details}")
        elif status == "WARN":
            checks_warn += 1
            print(f"{tag:<8} {title:<45} {details}")
        else:
            checks_failed += 1
            print(f"{tag:<8} {title:<45} {details}")

    health_url = f"{backend_url.rstrip('/')}/api/health"
    status, body, elapsed, _ = fetch_url(health_url, timeout=15.0)
    backend_data = {}
    if status == 200:
        try:
            backend_data = json.loads(body)
            record_result("PASS", "Backend Health Endpoint", f"HTTP 200 ({elapsed:.1f} ms)")
        except Exception:
            record_result("FAIL", "Backend Health Endpoint", "Invalid JSON payload")
    else:
        record_result("FAIL", "Backend Health Endpoint", f"HTTP {status} ({elapsed:.1f} ms)")

    frontend_clean = frontend_url.rstrip("/")
    status_fe, body_fe, elapsed_fe, _ = fetch_url(f"{frontend_clean}/", timeout=15.0)
    if status_fe == 200 and ("<!doctype html>" in body_fe.lower() or "<html" in body_fe.lower()):
        record_result("PASS", "Frontend Vercel Deployment", f"HTTP 200 ({elapsed_fe:.1f} ms)")
    else:
        record_result("FAIL", "Frontend Vercel Deployment", f"HTTP {status_fe} ({elapsed_fe:.1f} ms)")

    rewrite_url = f"{frontend_clean}/api/health"
    status_rw, body_rw, elapsed_rw, _ = fetch_url(rewrite_url, timeout=15.0)
    if status_rw == 200 and "status" in body_rw:
        record_result("PASS", "Vercel /api/* Proxy Rewrite", f"HTTP 200 ({elapsed_rw:.1f} ms)")
    else:
        record_result("FAIL", "Vercel /api/* Proxy Rewrite", f"HTTP {status_rw} ({elapsed_rw:.1f} ms)")

    if backend_data.get("supabase_connected") is True:
        record_result("PASS", "Supabase Production Database", "Connected & Healthy")
    else:
        record_result("FAIL", "Supabase Production Database", "Disconnected")

    if backend_data.get("demo_mode") is False:
        record_result("PASS", "Real Data Mode Active", "Authoritative (demo_mode=false)")
    else:
        record_result("FAIL", "Real Data Mode Active", "Unexpected Demo Overlay")

    records_count = backend_data.get("records_loaded", 0)
    if records_count >= 1000:
        record_result("PASS", "Authoritative Data In-Memory", f"{records_count:,} records loaded")
    elif records_count > 0:
        record_result("WARN", "Authoritative Data In-Memory", f"Low count: {records_count} records")
    else:
        record_result("FAIL", "Authoritative Data In-Memory", "0 records loaded")

    ai_ready = backend_data.get("ai_available", False)
    if ai_ready:
        record_result("PASS", "AI Gemini Provider Readiness", "Online & Ready")
    else:
        record_result("WARN", "AI Gemini Provider Readiness", "Offline; Deterministic Fallback Active")

    critical_endpoints = [
        ("Jobs Public Feed", f"{backend_url.rstrip('/')}/api/jobs?limit=5"),
        ("Government Schemes Feed", f"{backend_url.rstrip('/')}/api/schemes?limit=5"),
        ("Government Opportunities", f"{backend_url.rstrip('/')}/api/gov/opportunities?limit=5"),
        ("Skill Taxonomy Directory", f"{backend_url.rstrip('/')}/api/skills?limit=5"),
        ("Curriculum Modernization Audit", f"{backend_url.rstrip('/')}/api/curriculum/audit"),
        ("Student Alert Domains", f"{backend_url.rstrip('/')}/api/student/alert-domains"),
    ]

    for label, ep_url in critical_endpoints:
        ep_status, ep_body, ep_elapsed, _ = fetch_url(ep_url, timeout=15.0)
        if ep_status == 200:
            record_result("PASS", label, f"HTTP 200 ({ep_elapsed:.1f} ms)")
        else:
            record_result("FAIL", label, f"HTTP {ep_status} ({ep_elapsed:.1f} ms)")

    print("-" * 70)
    print(f"Summary: {checks_passed} PASSED, {checks_warn} WARNINGS, {checks_failed} FAILED")
    print("=" * 70)

    if checks_failed == 0:
        print("OVERALL DEMO READINESS: DEMO READY")
        print("=" * 70)
        return True
    else:
        print("OVERALL DEMO READINESS: DEMO NOT READY")
        print(f"ATTENTION: {checks_failed} critical checks failed. Resolve blockers before presenting.")
        print("=" * 70)
        return False


def main():
    parser = argparse.ArgumentParser(description="SkillSetu Production Warmup & Pre-Flight Probe")
    parser.add_argument(
        "--backend-url",
        default=os.getenv("SKILLSETU_BACKEND_URL", DEFAULT_BACKEND_URL),
        help="Backend base URL",
    )
    parser.add_argument(
        "--frontend-url",
        default=os.getenv("SKILLSETU_FRONTEND_URL", DEFAULT_FRONTEND_URL),
        help="Frontend base URL",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="Custom health endpoint URL for probe_backend compatibility",
    )
    parser.add_argument("--retries", type=int, default=4, help="Maximum probe retries (default: 4)")
    parser.add_argument("--delay", type=float, default=4.0, help="Delay between retries in seconds (default: 4.0)")
    parser.add_argument("--warmup-only", action="store_true", help="Only run the warmup probe")
    args = parser.parse_args()

    health_target = args.url if args.url else f"{args.backend_url.rstrip('/')}/api/health"
    warmup_ok, _, _ = probe_backend(url=health_target, max_retries=args.retries, retry_delay=args.delay)

    if not warmup_ok:
        print("\nERROR: Warmup probe failed. Backend service is not reachable.")
        sys.exit(1)

    if args.warmup_only:
        sys.exit(0)

    preflight_ok = run_preflight_suite(backend_url=args.backend_url, frontend_url=args.frontend_url)
    sys.exit(0 if preflight_ok else 1)


if __name__ == "__main__":
    main()
