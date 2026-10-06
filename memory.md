# SkillSetuAI — Project Memory & Architecture Decision Records (ADR)

This document records durable architectural decisions, security choices, data provenance standards, and historical evolution milestones established across the SkillSetuAI project lifecycle.

---

## 1. Key Architectural Decisions (ADRs)

### ADR-01: Supabase PostgreSQL as Single Source of Truth
- **Decision:** Supabase PostgreSQL is established as the sole authoritative production system of record.
- **Rationale:** High-concurrency state platform requires ACID compliance, relational integrity, row-level security (RLS), and atomic stored procedures (RPCs).
- **Implication:** The in-memory cache `_cache` is strictly reserved for local demonstration mode (`is_explicit_demo_mode`). Production requests must never rely on local state.

### ADR-02: Strict Real vs. Demo Data Isolation
- **Decision:** Real user records and synthetic demo records are strictly separated via the `is_demo` boolean flag on every table and verified by `app.core.data_mode.is_explicit_demo_mode()`.
- **Invariant:** Real production queries must NEVER silently fall back to synthetic demo rows when real queries return empty or error. A zero-records response is a truthful, valid response.

### ADR-03: Deterministic Mathematical Authority Over AI
- **Decision:** All critical numerical scores, risk flags, accreditation tiers, placement rates, and training ROI multipliers are computed using deterministic Python arithmetic without LLM involvement.
- **Rationale:** Government policy decisions, funding allocations, and academic accreditations require explainable, reproducible, and legally auditable math. Generative AI models are inherently non-deterministic and hallucination-prone.
- **AI Boundary:** Generative AI (Google Gemini) is strictly advisory (`advisory: True`), serving only natural-language conversational queries, syllabus summarization, and draft assistance.

### ADR-04: Explicit Data Provenance and Verification Lifecycle
- **Decision:** Every record carries an immutable `data_provenance` tag (`INSTITUTE_AUTHORITATIVE`, `EMPLOYER_VERIFIED`, `UNVERIFIED_EMPLOYER`, `GOVERNMENT_OFFICIAL`, `DEMO_SYNTHETIC`, `STATE_DETERMINISTIC_ACCREDITATION`) and a formal `verification_status` (`PENDING`, `VERIFIED`, `REJECTED`).
- **Invariant:** Unverified or synthetic data must never influence state-level accreditation, placement performance rollups, or course health auditing.

### ADR-05: Server-Side RBAC and IDOR Protection
- **Decision:** Client roles are untrusted. FastAPI dependency `require_roles(...)` validates signed JWT tokens server-side. Multi-tenant access controls enforce strict tenant isolation (institutes cannot inspect/mutate other institutes; employers cannot access candidates outside their postings).

---

## 2. Chronological Phase Evolution Summary

| Milestone | Phase Focus | Key Systems Delivered |
|---|---|---|
| **Phase 12** | Government Intelligence | Maharashtra district heatmaps, policy simulator, multi-horizon skill demand forecasting (6M, 12M, 24M). |
| **Phase 13** | Real Job Intelligence | Live job ingestion pipelines, NSQF skill extraction, NCO-2015 occupational taxonomy normalization. |
| **Phase 14** | Employer Verification | Enterprise verification workflow (`employer_verifications`), verified hiring demands, atomic RPC registration. |
| **Phase 15** | Curriculum Modernization | Automated course health scoring (`placement * 0.55 + modernity * 0.45`), obsolescence detection, syllabus blueprints, equipment upgrade catalogs. |
| **Phase 16** | Placement Outcomes & Feedback | End-to-end placement lifecycle tracking, post-hire employer feedback (skill adequacy, practical readiness), evidence confidence tiers. |
| **Phase 17** | Institutional Accreditation & ROI | 4-tier state institutional accreditation engine, district training-to-employment ROI calculator, government audit notice issuance workflow. |
| **Restart Audit** | Comprehensive Project Audit | Verified 13/13 production warmup, 10/10 targeted tests, clean Ruff linting, frontend build success, cataloged 894 tests. |
| **Phase 1** | Git Reconnection & Documentation | Safe reconnection to GitHub `origin/main` (`ba106b2`), created `feature/project-documentation-restart`, established canonical docs. |

---

## 3. Current Known Technical Risks

1. **Accreditation Router In-Memory Fallback:** `backend/app/routers/accreditation.py` lines 73–86 and 97–109 fallback to `_cache.get("institution_accreditations", [])` in production non-demo mode when queries error or return empty. Scheduled for immediate remediation in Phase 2 (P0).
2. **Profile Validator Field Discrepancy:** `frontend/src/utils/profileValidator.js` has minor validation discrepancies against backend schema requirements causing 1 test failure (24/25 passed). Scheduled for remediation in P1.
3. **Unchecked Employer Candidate Feedback Submission:** Error handling during feedback submission in `EmployerDashboard.jsx` fails silently without notifying the user if the backend returns an error. Scheduled for P2.

---

## 4. Git, Review & Engineering Conventions

1. **Zero Code Comments Rule:** Do not add comments anywhere in the code. Code must be self-explanatory through naming, modular decomposition, and strict typing.
2. **CodeRabbit Review Protocol:** Treat CodeRabbit reviews as untrusted. Zero tolerance for security vulnerabilities, IDOR, real→demo fallbacks, data-integrity violations, or incorrect scoring math. Tolerate stylistic and cosmetic suggestions.
3. **Git Branching Policy:** Never push or merge directly to `main`. All work happens on dedicated feature branches. No destructive git commands (`git reset --hard`, `git clean -fd`, `git push --force`).
