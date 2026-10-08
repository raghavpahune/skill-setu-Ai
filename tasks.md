# SkillSetuAI — Project Task Board & Roadmap

## Current Status Overview
- **Active Phase:** PHASE 18 COMPLETE — Vocational Faculty Competency & State Trainer Development Pipeline (Platform Readiness Audit Remediated; Awaiting Phase 19 Scope Definition)
- **Current Milestone:** Platform Readiness Audit Remediation Complete & Validated:
  - Finding 1: Backend employer feedback endpoint returns HTTP 404 for non-existent feedback records instead of HTTP 200.
  - Finding 2: EmployerDashboard signal feedback rollback on failure with truthful error toasts; batch confirms utilize `Promise.allSettled` without swallowing errors.
  - Finding 3: Candidate feedback modal explicitly validates response payload, prevents UI freeze on unexpected 2xx/network errors, and preserves retryable state.
  - Finding 4: Aligned certification validator requiring both `name` and `issuer`; integrated standardized `"test": "node --test test_*.test.js"` script in `frontend/package.json`.
  - Validation Results:
    - Employer Backend Tests (`backend/test_employer_phase8.py`, `backend/test_employer_phase14.py`): 10/10 PASSED
    - Phase 17 & 18 Regression / E2E Tests (`backend/test_phase17_accreditation_roi.py`, `backend/test_phase18_trainer_capacity.py`, `backend/test_e2e_phase18.py`): 55/55 PASSED
    - Student & Employee Integration Tests (`backend/test_student_journey_integration.py`, `backend/test_employee_journey_integration.py`, `backend/test_student_portal_persistence.py`): 29/29 PASSED
    - Security & Hardening Tests (`backend/test_copilot_grounding.py`, `backend/test_phase6_security_hardening.py`, `backend/test_real_data_hardening.py`, `backend/test_migration_integrity_phase11.py`): 28/28 PASSED
    - Frontend Automated Suites (`npm test`): 44/44 PASSED (0 failures)
    - Backend Linter (`ruff check backend`): CLEAN (All checks passed)
    - Frontend Linter (`oxlint` via `npm run lint`): CLEAN (0 errors, 78 warnings)
    - Production Bundle (`npm run build`): CLEAN (Vite build succeeded)
  - CodeRabbit Nitpick: 1 cosmetic test-helper extraction nitpick intentionally tolerated.
- **Next Step:** Define Phase 19 scope (no Phase 19 specifications currently exist in repository roadmap).

---

## 1. Task Board

### COMPLETED / VERIFIED (Platform Readiness Audit Remediation)
- [x] **Finding 1 — Backend Employer Feedback Status Code (`backend/app/routers/employer.py`):**
  - Raised `HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=f"Employer feedback record '{submission.feedback_id}' not found.")` when feedback ID does not match an existing record instead of returning HTTP 200 with an error object.
  - Preserved role verification (`EMPLOYER`, `ADMIN`), cross-tenant authorization checks, and success payload.
  - Regression tested in `backend/test_employer_phase8.py` verifying missing ID returns 404, valid submissions succeed with 200, and unauthorized roles return 403.
- [x] **Finding 2 — Employer Signal Feedback Failure & Batch Handling (`frontend/src/pages/EmployerDashboard.jsx`):**
  - In `handleAction`, reverted optimistic state on API/network failure and surfaced truthful error toast (`Failed to calibrate signal: ...`), eliminating false-success / offline messages.
  - In `handleBatchConfirmFiltered`, replaced swallowed `catch(() => null)` background dispatch with `Promise.allSettled`, updated state only for confirmed signals, and displayed truthful toasts (full success, partial success with error count, or complete failure error).
  - Preserved legitimate explicit demo-mode isolation.
- [x] **Finding 3 — Candidate Feedback Modal Response Handling (`frontend/src/pages/EmployerDashboard.jsx`):**
  - Added explicit validation for expected response shape (`if (res?.feedback)`).
  - Handled unexpected 2xx responses missing feedback and network errors with explicit error toasts and reset `submittingFeedback` loading state so the modal does not become stuck.
  - Retained candidate selection state for retry.
  - Added comprehensive frontend test coverage in `frontend/test_employer_feedback_handling.test.js` (8 tests: single failure rollback, single success, batch full success, batch partial failure, batch complete failure, candidate feedback success, candidate feedback unexpected payload, candidate feedback network exception).
- [x] **Finding 4 — Profile Certification Validation Alignment & Test Command (`frontend/src/utils/profileValidator.js`, `frontend/package.json`):**
  - Updated `formatStudentProfilePayload` and `formatEmployeeProfilePayload` to require `c.name && c.issuer` when filtering certifications, resolving the mismatch where empty issuers previously defaulted to synthetic self-certification and failed `frontend/test_profile_validation.test.js`.
  - Added standardized `"test": "node --test test_*.test.js"` script to `frontend/package.json`.
  - Verified 44/44 frontend test assertions pass with 0 failures via `npm test`.

### COMPLETED / VERIFIED (Phase 18 Milestones)
- [x] **Faculty Competency Scorecard Engine (`backend/app/services/trainer_service.py`):** Deterministic NSQF student-to-trainer ratio, competency matching, and capacity ratio calculation.
- [x] **State FDP Nomination Lifecycle (`backend/app/routers/trainers.py`):** State-sanctioned faculty development nominations with RBAC and immutable provenance.
- [x] **Statewide District Capacity Analytics:** District-level trainer supply, NSQF compliance tracking, and trade distribution analytics.
- [x] **Phase 18 CodeRabbit Finding Remediation — Cycle 1 (`051446c`):**
  - Finding 1 (`backend/app/db.py`): Authoritative database updates remain authoritative, update cache, and do not evaluate stale cache status. Genuine stale-status and database rejection errors surface as HTTP 409 Conflict rather than swallowed into cache fallback.
  - Finding 2 (`backend/app/services/trainer_service.py`, `backend/app/repositories/supabase_repository.py`): `list_institution_trainers` accepts optional status; status is normalized (`strip().upper()`) and applied before range pagination; post-pagination status filter removed; cache fallback retains consistent pagination semantics.
- [x] **Phase 18 CodeRabbit Finding Remediation — Cycle 2 (`cf35b04`, `8f4135e`):**
  - Finding 1 (`frontend/src/pages/GovernmentDashboard.jsx`): Replaced total trainer count with `active_trainers` for statewide active faculty KPI, and replaced `trainer_count` with `active_faculty` in district table cell.
  - Finding 2 (`memory.md`): Harmonized ADR-01 and ADR-06 to explicitly define production outage policy: production requests when Supabase is configured never silently fall back to `_cache` on database errors/outages (surfacing HTTP 503/409); `_cache` fallback is strictly restricted to unconfigured offline dev (`SupabaseConnectionError`) and explicit demo mode.
  - Finding 3 (`data/schema.sql`, `data/migrations/20260923_phase18_trainer_capacity.sql`, `backend/test_phase18_trainer_capacity.py`): Harmonized schema and migration definitions with repository allowlists (`VALID_INSTITUTION_TRAINER_COLUMNS`, `VALID_FACULTY_NOMINATION_COLUMNS`) and router write payloads; added mock client regression test confirming unallowlisted keys are stripped before reaching Supabase.
- [x] **Phase 18 CodeRabbit Finding Remediation — Cycle 3 (`a01f3a4`, `c8e384b`):**
  - Finding 1 (`backend/app/db.py`, `backend/app/repositories/supabase_repository.py`): Re-raise `SupabaseRepositoryError` in trainer/nomination db helpers, raise `ValueError` for missing trainer updates, and ensure `_enrich_trainer_record` normalizes `certifications` as a list.
  - Finding 2 (`backend/app/routers/trainers.py`): Role-restricted `/api/trainers/analytics/statewide` to `GOVERNMENT` and `ADMIN` personas.
  - Finding 3 (`backend/app/services/trainer_service.py`): Set `limit=None` in statewide analytics loaders for full aggregation.
  - Finding 4 (`backend/app/services/trainer_service.py`): Propagate configured DB failures from analytics loaders.
  - Finding 5 (`memory.md`): Documented trainer-service cache invariants in ADR-06.
  - Finding 6 (`frontend/src/pages/InstituteDashboard.jsx`): Normalized catalog category-to-program mapping in `InstituteDashboard.jsx` to flat array with required modal fields.
  - Regression Tests (`backend/test_phase18_trainer_capacity.py`): Added focused tests for analytics role enforcement and configured DB error propagation.
- [x] **Phase 18 CodeRabbit Finding Remediation — Cycle 4 (`4681d4a`):**
  - Finding 1 (`backend/app/services/trainer_service.py`): Re-raise `SupabaseRepositoryError` in `list_institution_trainers_service` and `list_faculty_nominations_service`, allowing cache fallback only for `ImportError` and `SupabaseConnectionError`.
  - Finding 2 (`frontend/src/pages/GovernmentDashboard.jsx`): Prefer authoritative `statewideTrainers.nomination_summary` counts for Pending and Sanctioned Grants KPIs with fallback to list-derived counts when analytics is unavailable.
  - Regression Tests (`backend/test_phase18_trainer_capacity.py`): Added 3 focused tests for list service DB error propagation, SupabaseConnectionError fallback, and ImportError fallback.
- [x] **Phase 18 CodeRabbit Finding Remediation — Cycle 5 (`c78f57c`):**
  - Finding 1 (`frontend/src/pages/GovernmentDashboard.jsx`): Display active loading state (`loading && !statewideTrainers`) on initial load for statewide trainer KPI cards, display `Unavailable` on error, and retain previously loaded values during background refresh.
  - Regression Tests (`frontend/test_government_trainer_kpis.test.js`): Added 4 focused node tests verifying initial load, error state, refresh retention, and zero-count validity.
  - Validation: 55 backend tests passed; 4 focused frontend tests passed; Ruff clean; Oxlint 0 errors; Vite build succeeded.
- [x] **Phase 18 CodeRabbit Finding Remediation — Cycle 6 (`ba05116`):**
  - Finding 1 (`frontend/src/pages/GovernmentDashboard.jsx`): Immediately synchronize `statewideTrainers.nomination_summary` upon confirmed backend sanction/rejection response and refresh authoritative statewide analytics, ensuring immediate KPI consistency without full dashboard reload.
  - Finding 2 (`frontend/src/pages/GovernmentDashboard.jsx`): Relabeled `certified_trainers_count` KPI card and `certified_count` district leaderboard column to emerging-trade faculty without claiming verified certification.
  - Finding 3 (`frontend/src/pages/InstituteDashboard.jsx`): Rendered 5-column empty state table row prompting instructor registration when the trainer roster is empty.
  - Nitpick (`frontend/test_government_trainer_kpis.test.js`): Preserved focused test suite without unnecessary production abstraction; added 7 focused tests covering sanction/rejection transitions, zero count bounds, terminology labels, and empty/populated roster states.
  - Validation: 29 Phase 18 backend tests passed; 19 Phase 17 regression tests passed; 11 focused frontend tests passed; Ruff clean; Oxlint 0 errors; Vite build succeeded.

---

### P1 — High Priority / Review & Verification
- [x] **Platform Readiness Audit Remediation:** All 4 verified audit findings resolved and verified.
- [x] **Phase 18 CodeRabbit Re-Review & Validation:** Completed across Cycles 1–6. All actionable findings resolved and verified; 1 cosmetic test-helper extraction nitpick intentionally tolerated.
- [x] **Phase 18 Final Validation & Closure:** Validated full test suite (29 backend + 7 E2E + 19 regression + 11 frontend tests passed, Ruff clean, Oxlint 0 errors, Vite build clean). Phase 18 cleanly closed.
- [ ] **Phase 19 Scope Definition & Planning:** Define formal Phase 19 requirements and acceptance criteria (currently undefined in repository roadmap).

---

### P2 — Medium Priority / Backlog
- [x] **EmployerDashboard Silent Feedback Failure Handling (`frontend/src/pages/EmployerDashboard.jsx`):**
  - *Completed:* Added error toasts, optimistic rollback, `Promise.allSettled` batch tracking, and modal error handling for unexpected or failing responses.
- [x] **Frontend Test Command & CI Integration:**
  - *Completed:* Standardized `"test": "node --test test_*.test.js"` in `frontend/package.json`. All 44 tests pass.

---

### P3 — Low Priority / Code Health
- [ ] **React Compiler Warnings Review:**
  - *Issue:* Review and resolve React 19 compiler warnings and hook dependency lint messages across dashboards.
- [ ] **Material Quality & Performance Hardening:**
  - *Issue:* Audit frontend bundle sizes and optimize Recharts / Leaflet rendering cycles.

---

### P4 — Backlog & Cosmetic Polish
- [ ] **Cosmetic Cleanup:** Minor spacing, dark mode contrast enhancements, and typography refinements.

---

## 2. Blocked Tasks
- *None currently.*

---

## 3. Verification & Testing Requirements

Every task completed must pass the following verification gates before PR submission:

1. **Targeted Backend Tests:**
   ```powershell
   pytest backend/test_<relevant_feature>.py -v
   ```
2. **Backend Static Analysis:**
   ```powershell
   ruff check backend/
   ```
3. **Frontend Automated Tests:**
   ```powershell
   node --test frontend/test_*.test.js
   ```
4. **Frontend Linter & Build:**
   ```powershell
   cd frontend
   npm run lint
   npm run build
   ```
5. **Git Review:**
   ```powershell
   git status
   git diff
   ```
