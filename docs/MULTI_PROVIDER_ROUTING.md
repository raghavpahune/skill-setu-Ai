# AI Workload Routing & External Ingestion Architecture (Phase 37.3)

SkillSetu implements workload-based AI routing with deterministic fallback and robust external connector telemetry. Rather than treating external dependencies as an opaque monolithic stack, AI tasks and external datasets are decoupled into distinct workloads, credential boundaries, and explicit provenance states.

---

## 1. Provenance & Operational State Taxonomy

SkillSetu strictly enforces provenance boundaries across all services:

| Classification | Meaning | When Permitted |
|---|---|---|
| **REAL PROVIDER** | Active generative AI model (Google Gemini `gemini-3.6-flash`) | Valid API key configured and upstream online |
| **DETERMINISTIC FALLBACK** | Local rule-based advisory synthesis (`deterministic_fallback`) | Triggered on primary quota (429), timeout, auth failure, or unconfigured key |
| **LIVE_API** | Real-time external stream directly from an upstream API feed (Adzuna, Data.gov.in) | Valid credentials configured and API call succeeds |
| **VERIFIED_SNAPSHOT** | Authenticated historical snapshot with explicit timestamp and checksum | Permitted only when explicitly labeled as snapshot |
| **DEMO_SYNTHETIC** | Seed demonstration records (`data/demo/`) | Allowed ONLY when explicit demo mode is active (`is_demo=True` or `SKILLSETU_DATA_MODE=demo`) |

> [!IMPORTANT]
> External live-data failure in production NEVER silently falls back to local seed data or demo files.
> For migrated authoritative domains, Supabase PostgreSQL is the sole authoritative persistence layer. If Supabase is unavailable, the application raises a database/service error—never a silent local SQLite, cache, or synthetic fallback.

---

## 2. Environment Variable Matrix

| Service | Environment Variable(s) | Role | Production Fallback Policy |
|---|---|---|---|
| **Primary AI Inference** | `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) | Primary generative AI inference across workloads | `deterministic_fallback` (advisory output) |
| **Workload-Specific AI Keys** | `GEMINI_API_KEY_<WORKLOAD>` (e.g. `GEMINI_API_KEY_CAREER_COPILOT`) | Dedicated quota/key isolation per workload | Falls back to primary `GEMINI_API_KEY` |
| **Workload Provider Mapping** | `AI_PROVIDER_<WORKLOAD>` | Configured AI provider for workload (defaults to `gemini`) | Primary `gemini` &rarr; `deterministic_fallback` |
| **Adzuna India Jobs** | `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | Real-time vacancy ingestion across Maharashtra | Fail-closed: reports connector unavailable (no synthetic substitution) |
| **data.gov.in (OGD)** | `DATA_GOV_API_KEY` | Official OGD training programs and schemes | Fail-closed: reports connector unavailable (no synthetic substitution) |
| **Supabase PostgreSQL** | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (or `SUPABASE_KEY`) | Authoritative persistence for migrated domains | Fail-closed: raises database connection error |
| **Admin Authorization** | `ADMIN_API_KEY` (or Bearer JWT) | RBAC-protected endpoints and telemetry | Fail-closed: strict 401 Unauthorized in production |
| **JWT Session Secret** | `JWT_SECRET_KEY` | Cryptographic session signing | Mandatory: fails on startup if absent in production |

---

## 3. Supported AI Workload Categories

SkillSetu routes AI requests to 8 distinct workload categories via `ai.router.AIRouter`:

1. `career_copilot`: Conversational career advisory grounded in student skills and target goals.
2. `skill_gap_analysis`: Differential analysis between candidate competencies and industry demand vectors.
3. `learning_roadmap`: NSQF-aligned milestone generation linking bridging courses to identified gaps.
4. `employee_transition`: Mid-career skill adjacency and transferability delta evaluation.
5. `employer_candidate_analysis`: Demand-driven talent pool matching and suitability scoring.
6. `institute_curriculum_analysis`: Syllabus extraction and gap identification against active market signals.
7. `government_policy_analysis`: Regional training subsidy and incentive shift projections.
8. `data_insight_generation`: District-level labor telemetry and high-growth domain summaries.

> [!NOTE]
> AI is strictly advisory. AI does NOT control authentication, authorization, scoring, ranking, matching, recommendation eligibility, provenance, or data integrity. Authoritative calculations remain deterministic.

---

## 4. Failover & Routing Architecture

### AI Workload Routing Flow
```text
Task Request (workload_category)
  │
  ▼
Resolve Workload Credential
  ├── Specific Key: GEMINI_API_KEY_<WORKLOAD> (if set)
  └── Default Key:  GEMINI_API_KEY
        │
        ▼
Is Gemini Configured?
  ├── Yes ──► Execute Google Gemini (gemini-3.6-flash)
  │             ├── HTTP 200 ──► Return Output (provider: "gemini", fallback_used: False, advisory: True)
  │             └── Error (429/Timeout/Quota/Network) ──┐
  │                                                     │
  └── No ───────────────────────────────────────────────┴──► Execute Deterministic Fallback
                                                              (provider: "deterministic_fallback",
                                                               fallback_used: True,
                                                               advisory: True)
```

### External Connector Routing Flow
```text
Connector Request (Adzuna / Data.gov.in)
  │
  ├── Is Explicit Demo Mode Active?
  │     └── Yes ──► Return Demo Records (stamped: source="DEMO_SYNTHETIC", is_demo=True)
  │
  └── Production Mode (is_demo=False)
        ├── Are Credentials Configured?
        │     ├── No  ──► Report NOT_CONFIGURED (return empty, status: "NOT_CONFIGURED")
        │     └── Yes ──► Execute Live API Fetch
        │                   ├── Success ──► Return Live Records (source="LIVE_API", is_demo=False)
        │                   └── Failure ──► Report UNAVAILABLE (return empty, status: "UNAVAILABLE")
        │                                   (NEVER silently substitute local seed files as live data)
```

---

## 5. Diagnostics & Observability

Live integration telemetry is exposed via:
- **API Endpoint**: `GET /api/admin/integrations/health` (Protected by `verify_admin_key`)
- **Dashboard UI**: Admin Dashboard &rarr; Overview Tab &rarr; *AI Engine & External Ingestion Routing* card.

The diagnostics payload never returns raw API keys, bearer tokens, service-role keys, or secrets.
