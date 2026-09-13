# SkillSetu Pre-Demo Warmup & Verification Procedure (Phase 37.1)

This guide details the exact operational preflight procedure to execute prior to live Smart India Hackathon (SIH) demonstrations.

---

## 1. Timing & Purpose

- **When to Run**: 2–3 minutes before entering the judging room or beginning the presentation.
- **Primary Goal**: Wake the cloud backend on Render from idle/cold sleep to guarantee instant (<500ms) response times for all evaluators.
- **Secondary Goal**: Verify end-to-end cloud infrastructure (Vercel, Render, Supabase, AI provider, critical endpoints) to prevent live demonstration failures.

---

## 2. Exact Execution Command

From the repository root, run:

```bash
python scripts/warmup.py
```

Optional flags:
- `--warmup-only`: Run only the Render wakeup ping without the full endpoint checklist.
- `--retries 5`: Adjust maximum cold-start retry attempts (default: 4).
- `--delay 4.0`: Adjust sleep delay between retries in seconds (default: 4.0).

---

## 3. Expected Output

```text
======================================================================
SKILLSETU SIH DEMO PRE-FLIGHT WARMUP
Target URL : https://skill-setu-backend-jklo.onrender.com/api/health
Max Retries: 4
======================================================================

[Attempt 1/4] Pinging backend health endpoint...
  --> HTTP 200 OK (425.1 ms) [WARM INSTANT]
----------------------------------------------------------------------
  Service Status     : OK
  Supabase Connected : True
  AI Available       : True
  Records In-Memory  : 2786
  Demo Mode Overlay  : False
  Active Districts   : 11
----------------------------------------------------------------------
SUCCESS: Production backend is warm and ready for presentation!
======================================================================

======================================================================
STARTING FULL PRE-DEMO READINESS CHECKLIST
======================================================================
[PASS]   Backend Health Endpoint                       HTTP 200 (420.2 ms)
[PASS]   Frontend Vercel Deployment                    HTTP 200 (185.0 ms)
[PASS]   Vercel /api/* Proxy Rewrite                   HTTP 200 (490.5 ms)
[PASS]   Supabase Production Database                  Connected & Healthy
[PASS]   Real Data Mode Active                         Authoritative (demo_mode=false)
[PASS]   Authoritative Data In-Memory                  2,786 records loaded
[PASS]   AI Gemini Provider Readiness                  Online & Ready
[PASS]   Jobs Public Feed                              HTTP 200 (480.1 ms)
[PASS]   Government Schemes Feed                       HTTP 200 (510.3 ms)
[PASS]   Government Opportunities                      HTTP 200 (620.4 ms)
[PASS]   Skill Taxonomy Directory                      HTTP 200 (780.2 ms)
[PASS]   Curriculum Modernization Audit                HTTP 200 (850.1 ms)
[PASS]   Student Alert Domains                         HTTP 200 (430.0 ms)
----------------------------------------------------------------------
Summary: 13 PASSED, 0 WARNINGS, 0 FAILED
======================================================================
OVERALL DEMO READINESS: DEMO READY
======================================================================
```

---

## 4. Status Interpretation & Recovery Runbook

| Status | Meaning | Action Required |
|---|---|---|
| **PASS** | Component is live, healthy, and responsive. | None. Proceed with demonstration. |
| **WARN** | Component is degraded or offline, but deterministic fallbacks are functioning. | **Gemini Offline**: The system automatically uses the deterministic recommendation engine and offline guidance. The demo remains functional. |
| **FAIL** | Critical component is unreachable (Backend down, Frontend down, Database severed, or Rewrite broken). | See recovery steps below. |

### Recovery Steps for FAIL Conditions:

1. **Backend Health Endpoint Fails**:
   - Cause: Render free-tier instance is still cold or service was redeployed.
   - Fix: Re-run `python scripts/warmup.py --retries 6 --delay 5.0` to allow up to 45 seconds for container initialization.
2. **Vercel /api/* Proxy Rewrite Fails**:
   - Cause: Local network blocking Vercel proxy or DNS resolution failure.
   - Fix: Confirm internet connectivity; check `https://skill-setu-rust.vercel.app/api/health` directly in browser.
3. **Supabase Production Database Disconnected**:
   - Cause: Database paused or connection pool limit reached.
   - Fix: The backend automatically utilizes in-memory verified cache while attempting background reconnection.
4. **Real Data Mode Unexpected Demo Overlay**:
   - Cause: `ENVIRONMENT` or `DEMO_MODE` flag was misconfigured in cloud settings.
   - Fix: Ensure production environment on Render has `ENVIRONMENT=production`.

---

## 5. Demonstrator Browser Preparation Steps

1. **Use Incognito / Private Window**: Always open a fresh private browser window to prevent stale cache or lingering session cookies from affecting live evaluation.
2. **Pre-load Tabs**:
   - Tab 1: `https://skill-setu-rust.vercel.app/` (Landing Page)
   - Tab 2: `https://skill-setu-rust.vercel.app/login` (Login screen ready for role switching)
3. **Hard Refresh**: Press `Ctrl + Shift + R` (Windows) or `Cmd + Shift + R` (Mac) to ensure the latest assets are cached in the browser.
4. **Check Zoom**: Set browser zoom to 100% (or 90% if presenting on standard 1080p projectors) for optimal layout visibility.
