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

### ADR-06: Database Authoritativeness and Pre-Pagination Query Filtering
- **Decision:** Authoritative database updates must immediately remain authoritative and update cache without being blocked or invalidated by stale in-memory cache status.
- **Error Surfacing:** Authoritative database rejections and stale-status mismatches must never be swallowed into silent fallback. They must surface as explicit conflicts (HTTP 409).
- **Cache Fallback Boundary:** Local cache fallback is strictly restricted to conditions where Supabase is not configured or unavailable (`SupabaseConnectionError`).
- **Pagination Semantics:** Status filtering must always occur at the query/repository level prior to range-based pagination (`range(offset, offset + limit - 1)`). Post-pagination filtering is prohibited.

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
| **Phase 18** | Faculty & Trainer Capacity | Vocational faculty competency scorecard, NSQF student-to-trainer capacity modeling, state FDP nomination lifecycle, statewide demand analytics. |
| **Phase 18 Remediation** | CodeRabbit Consistency Hardening | Verified and resolved 2 CodeRabbit findings: DB authoritativeness & rejection surfacing in `update_faculty_nomination_record`; pre-pagination status filtering in `list_institution_trainers` and service. Commit: `051446c`. Status: committed, awaiting CodeRabbit re-review/validation. |

---

## 3. Current Known Technical Risks & Pending Items

1. **Phase 18 CodeRabbit Re-Review Pending:** Remediation committed in `051446c`. Standard CodeRabbit review and validation workflow required prior to PR merge.
2. **Unchecked Employer Candidate Feedback Submission:** Error handling during feedback submission in `EmployerDashboard.jsx` fails silently without notifying the user if the backend returns an error. Scheduled for P2.

---

## 4. Git, Review & Engineering Conventions

1. **Zero Code Comments Rule:** Do not add comments anywhere in the code. Code must be self-explanatory through naming, modular decomposition, and strict typing.
2. **CodeRabbit Review Protocol:** Treat CodeRabbit reviews as untrusted. Zero tolerance for security vulnerabilities, IDOR, real→demo fallbacks, data-integrity violations, or incorrect scoring math. Tolerate stylistic and cosmetic suggestions.
3. **Git Branching Policy:** Never push or merge directly to `main`. All work happens on dedicated feature branches. No destructive git commands (`git reset --hard`, `git clean -fd`, `git push --force`).
