# SkillSetuAI — Project Task Board & Roadmap

## Current Status Overview
- **Active Phase:** PHASE 1 — Safe Git Reconnection & Documentation Restart Layer
- **Current Milestone:** Phase 1 Complete (Reconnected to `origin/main` on `feature/project-documentation-restart`; documentation layer established).
- **Next Task:** P0 — Remove non-demo accreditation in-memory fallback in `backend/app/routers/accreditation.py`.

---

## 1. Task Board

### COMPLETED / VERIFIED (Audit & Phase 1 Baseline)
- [x] **Two-Week Restart Project Audit:** Full inventory of architecture, schemas, and endpoints.
- [x] **Production Warmup Validation:** 13/13 production warmup checks passed on Render/Vercel/Supabase.
- [x] **Targeted Backend Verification Tests:** 10/10 critical path tests passed (`test_student_phase12.py`, etc.).
- [x] **Frontend Build Verification:** `npm run build` completed successfully with 0 build errors.
- [x] **Frontend Linter Verification:** `oxlint` passed cleanly.
- [x] **Current Architecture Audit:** Verified live integration across Frontend (Vercel) → Backend (Render) → Supabase PostgreSQL.
- [x] **Safe Git Reconnection (Phase 1A):** Safely initialized Git, connected remote `origin` (`https://github.com/raghavpahune/skill-setu-Ai.git`), fetched history, synchronized with commit `ba106b2` on `origin/main`, created branch `feature/project-documentation-restart`.
- [x] **Documentation Layer Establishment (Phase 1B):** Established canonical documentation files (`prd.md`, `architecture.md`, `rules.md`, `instructions.md`, `design.md`, `tasks.md`, `memory.md`, `AGENTS.md`, `CLAUDE.md`).

---

### P0 — Critical Correctness & Data Integrity (Upcoming)
- [ ] **Remove Non-Demo Accreditation In-Memory Fallback (`backend/app/routers/accreditation.py`):**
  - *Issue:* Lines 73–86, 97–109 in `accreditation.py` query `_cache.get("institution_accreditations", [])` in production non-demo mode when Supabase queries return empty or throw exceptions.
  - *Requirement:* Ensure non-demo requests return truthful empty results or propagate explicit HTTP errors. Never fall back to in-memory demo cache in non-demo mode.

---

### P1 — High Priority / Contract Alignment
- [ ] **Fix Profile Validation Discrepancy (`frontend/src/utils/profileValidator.js`):**
  - *Issue:* Field validation rules in `profileValidator.js` diverge slightly from backend model requirements, causing 1 frontend test failure (24/25 passed).
  - *Requirement:* Align frontend validation rules with backend schemas and resolve the failing test in `frontend/test_profile_validation.test.js`.
- [ ] **Ruff Exclusion Configuration Correction (`ruff.toml`):**
  - *Issue:* `ruff.toml` excludes directories that should be linted or monitored in standard CI.
  - *Requirement:* Clean up `ruff.toml` configuration to ensure consistent static analysis coverage.

---

### P2 — Medium Priority / Reliability & Tooling
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
- *None currently.* All prerequisites for Phase 2 P0 are satisfied.

---

## 3. Future Features (Out of Current Phase Scope)
- [ ] **pgvector Semantic RAG Search:** Activate vector embeddings for course syllabus PDFs and job descriptions.
- [ ] **DigiLocker / APAAR ID Integration:** Automated verification of academic diplomas via India Stack APIs.
- [ ] **Full 36-District Statewide Expansion:** Scale ingestion pipelines from pilot districts to all 36 Maharashtra districts.
- [ ] **Marathi UI Localization:** Full bilingual support for regional users.

---

## 4. Verification & Testing Requirements

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
