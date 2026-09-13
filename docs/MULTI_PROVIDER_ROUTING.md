# Multi-Provider AI & External API Key Routing (Phase 37.3)

SkillSetu employs a centralized, multi-provider routing and resilient fallback architecture. Rather than treating third-party services as monolithic external dependencies, AI tasks and external datasets are decoupled into independent provider connectors with automated failover policies.

---

## 1. Environment Variable Matrix

| Service | Purpose | Environment Variable(s) | Type | Fallback Policy |
|---|---|---|---|---|
| **Google Gemini AI** | Primary generative AI inference for Career Copilot and personalized contextual explainability | `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) | Optional in Dev / Recommended in Prod | `DemoProvider` (Rule-based grounded intelligence) |
| **Adzuna India** | Live vacancy telemetry across Maharashtra 36 districts | `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | Optional | Verified Local Snapshot (`data/real/jobs.json`) &rarr; Immutable Baseline |
| **data.gov.in (OGD)** | Open Government Data portal feeds (PMKVY, NAPS, ITI apprenticeships) | `DATA_GOV_API_KEY` | Optional | Verified Local Snapshot (`data/real/`) &rarr; Immutable Baseline |
| **Supabase Managed Postgres** | Authoritative cloud database with RLS policies | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (or `SUPABASE_ANON_KEY`) | Required in Prod | In-Memory Verified Cache (`data/real/` disk store) |
| **Admin Authorization** | Administration and integration health diagnostics access | `ADMIN_API_KEY` | Optional (Bearer JWT supported) | Strict 401/403 RBAC rejection |
| **JWT Session Secret** | Cryptographic token signing for user authentication | `JWT_SECRET_KEY` | Required | Platform startup default (Dev only) |
| **Environment Mode** | Production vs Development deployment flag | `ENVIRONMENT` (or `RENDER`) | Required in Prod | `development` |

---

## 2. Supported AI Task Categories

SkillSetu routes AI requests to 8 distinct task categories managed by `ai.router.AIRouter`:

1. `career_copilot`: Natural language conversational career advisory grounded in student skills and target goals.
2. `skill_gap_analysis`: Differential analysis between candidate competencies and industry demand vectors.
3. `learning_roadmap`: NSQF-aligned milestone generation linking bridging courses to identified gaps.
4. `employee_transition`: Mid-career skill adjacency and transferability delta evaluation.
5. `employer_candidate_analysis`: Demand-driven talent pool matching and suitability scoring.
6. `institute_curriculum_analysis`: Syllabus extraction and gap identification against active market signals.
7. `government_policy_analysis`: Regional training subsidy and incentive shift projections.
8. `data_insight_generation`: District-level labor telemetry and high-growth domain summaries.

---

## 3. Failover & Fallback Architecture

### AI Routing Fallback Chain
```text
Task Request
  │
  ▼
GeminiProvider (Configured & Available?)
  ├── Yes ──► Call Google Gemini API (gemini-3.6-flash)
  │             ├── Success ──► Return Grounded AI Output (fallback_used: False)
  │             └── Error (429/Timeout/Quota) ──┐
  │                                             │
  └── No ───────────────────────────────────────┴──► DemoProvider Fallback
                                                       (Rule-based deterministic engine,
                                                        fallback_used: True)
```

### External Data Ingestion Fallback Chain
```text
Connector Fetch
  │
  ▼
Live External API (Adzuna / data.gov.in)
  ├── Configured & Success ──► Transform, Dedupe (SHA-256), Persist (source: LIVE_API)
  │
  └── Unconfigured / Network Error
        │
        ▼
      Authoritative Database (Supabase Cached Records)
        │
        └── Empty / Disconnected
              │
              ▼
            Verified Local Snapshot (data/real/ store)
              │
              └── Demo Mode Explicitly Enabled
                    │
                    ▼
                  Baseline Immutable Dataset (data/demo/)
```

---

## 4. Diagnostics & Observability

Administrators can inspect live provider health via:
- **API Endpoint**: `GET /api/admin/integrations/health` (Protected by `verify_admin_key`)
- **Dashboard UI**: Admin Dashboard &rarr; Overview Tab &rarr; *Multi-Provider AI & External Data Routing* card.

The diagnostics payload never returns raw API keys, bearer tokens, or sensitive authorization headers.
