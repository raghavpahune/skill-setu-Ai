# SkillSetuAI — Project Task Board & Roadmap

## Current Status Overview
- **Active Phase:** PHASE 18 — Vocational Faculty Competency & State Trainer Development Pipeline
- **Current Milestone:** Phase 18 CodeRabbit Remediation Completed & Validated.
  - Cycle 1 (Commit `051446c`): DB nomination updates conflict surfacing, pre-pagination status filtering.
  - Cycle 2:
    - Finding 1: GovernmentDashboard.jsx bound to active faculty metrics (`active_trainers`, `active_faculty`).
    - Finding 2: ADR-01 & ADR-06 harmonized on production outage policy and `_cache` fallback boundaries.
    - Finding 3: Database schema, migration, and repository allowlists synchronized across all trainer/nomination fields; mock allowlist regression test added.
  - Validation: 23 Phase 18 tests, 7 Phase 18 E2E tests, 19 Phase 17 regression tests passed; Ruff clean; frontend build & lint clean.
- **Next Step:** CodeRabbit re-review & final validation workflow prior to PR merge and phase closure.

---

## 1. Task Board

### COMPLETED / VERIFIED (Phase 18 Milestones)
- [x] **Faculty Competency Scorecard Engine (`backend/app/services/trainer_service.py`):** Deterministic NSQF student-to-trainer ratio, competency matching, and capacity ratio calculation.
- [x] **State FDP Nomination Lifecycle (`backend/app/routers/trainers.py`):** State-sanctioned faculty development nominations with RBAC and immutable provenance.
- [x] **Statewide District Capacity Analytics:** District-level trainer supply, NSQF compliance tracking, and trade distribution analytics.
- [x] **Phase 18 CodeRabbit Finding Remediation — Cycle 1 (`051446c`):**
  - Finding 1 (`backend/app/db.py`): Authoritative database updates remain authoritative, update cache, and do not evaluate stale cache status. Genuine stale-status and database rejection errors surface as HTTP 409 Conflict rather than swallowed into cache fallback.
  - Finding 2 (`backend/app/services/trainer_service.py`, `backend/app/repositories/supabase_repository.py`): `list_institution_trainers` accepts optional status; status is normalized (`strip().upper()`) and applied before range pagination; post-pagination status filter removed; cache fallback retains consistent pagination semantics.
- [x] **Phase 18 CodeRabbit Finding Remediation — Cycle 2:**
  - Finding 1 (`frontend/src/pages/GovernmentDashboard.jsx`): Replaced total trainer count with `active_trainers` for statewide active faculty KPI, and replaced `trainer_count` with `active_faculty` in district table cell.
  - Finding 2 (`memory.md`): Harmonized ADR-01 and ADR-06 to explicitly define production outage policy: production requests when Supabase is configured never silently fall back to `_cache` on database errors/outages (surfacing HTTP 503/409); `_cache` fallback is strictly restricted to unconfigured offline dev (`SupabaseConnectionError`) and explicit demo mode.
  - Finding 3 (`data/schema.sql`, `data/migrations/20260923_phase18_trainer_capacity.sql`, `backend/test_phase18_trainer_capacity.py`): Harmonized schema and migration definitions with repository allowlists (`VALID_INSTITUTION_TRAINER_COLUMNS`, `VALID_FACULTY_NOMINATION_COLUMNS`) and router write payloads; added mock client regression test confirming unallowlisted keys are stripped before reaching Supabase.
  - Validation: 23 Phase 18 tests passed, 7 Phase 18 E2E tests passed, 19 Phase 17 regression tests passed, Ruff clean, frontend build/oxlint clean.

---

### P1 — High Priority / Review & Verification
- [ ] **Phase 18 CodeRabbit Re-Review & Validation:** Await standard CodeRabbit re-review workflow on branch `feature/phase-18-faculty-trainer-capacity` to verify zero valid actionable findings remaining.
- [ ] **Phase 18 PR Final Validation:** Confirm all automated checks pass on GitHub Actions / PR pipeline prior to merge.

---

### P2 — Medium Priority / Backlog
- [ ] **EmployerDashboard Silent Feedback Failure Handling (`frontend/src/pages/EmployerDashboard.jsx`):**
  - *Issue:* Submitting candidate feedback in `EmployerDashboard.jsx` swallows API errors silently without displaying user feedback.
  - *Requirement:* Add descriptive error notifications and retry states upon submission failure.
- [ ] **Frontend Test Command & CI Integration:**
  - *Issue:* `frontend/package.json` scripts lack a standardized `"test"` command for running node test suites (`test_*.test.js`).
  - *Requirement:* Add `"test": "node --test test_*.test.js"` script to `package.json` and ensure test automation runs seamlessly.

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
