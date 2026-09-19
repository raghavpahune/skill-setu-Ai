# Phase 17 Capability Audit & Implementation Plan

**Repository:** SkillSetu (`raghavpahune/skill-setu-`)  
**Proposed Direction:** State Institutional Accreditation & District Training-to-Employment ROI Analytics Engine  
**Audit Date:** September 19, 2026  
**Status:** Audit & Architecture Proposal Only (No Code Modifications)

---

## 1. Current Repository State

- **Active Branch:** `main`
- **Current HEAD Commit SHA:** `04d1e80a9f27eb9e00602c33c881a68562af3e35`
- **Remote `origin/main` SHA:** `04d1e80a9f27eb9e00602c33c881a68562af3e35`
- **Working Tree Status:** Clean (`nothing to commit, working tree clean`)
- **Phase 16 Merge Commit:** `04d1e80` ("Merge pull request #19 from raghavpahune/feature/phase-16-placement-outcomes-feedback-loop")
- **Latest Commit Log (Top 5):**
  1. `04d1e80` - Merge pull request #19 from raghavpahune/feature/phase-16-placement-outcomes-feedback-loop
  2. `7140521` - fix(phase-16): production audit hardening and CodeRabbit review resolutions
  3. `17548d7` - feat(placements): implement Phase 16 placement outcomes and workforce feedback intelligence loop
  4. `9140101` - Merge pull request #18 from raghavpahune/feature/phase-15-curriculum-modernization
  5. `8d64452` - fix(phase-15): production audit hardening and CodeRabbit review resolutions

---

## 2. Capability Matrix

Every proposed Phase 17 capability has been evaluated against the active codebase across database schemas, SQL migrations, repository layer, backend services, FastAPI routers, frontend dashboards, and automated test suites.

| # | Capability Area | Capability Item | Status | Repository Evidence & Analysis |
|---|---|---|---|---|
| **A. Institutional Performance Intelligence** |
| 1 | Institutional Performance | Institute Placement Rate | **PARTIALLY IMPLEMENTED** | Course-level placement rate is implemented in `courses.placement_rate` and computed from `placement_outcomes` in `backend/app/services/placement_service.py` (`compute_course_placement_performance`). However, an authoritative, multi-course aggregated **institute-level** placement rate rollup (`compute_institute_performance(institute_id)`) is missing. |
| 2 | Institutional Performance | Employment Rate / Conversion | **PARTIALLY IMPLEMENTED** | Course-level employment conversion (`employed_count / placed_count`) is implemented in `placement_service.py:70`. Aggregation across all courses of an institute or across districts is missing. |
| 3 | Institutional Performance | Retention Rate | **MISSING** | Neither `placement_outcomes` nor `placement_employer_feedback` tracks employment duration or tenure milestones (e.g., 6-month or 12-month post-placement retention status). |
| 4 | Institutional Performance | Employer Readiness Feedback | **IMPLEMENTED** | Phase 16 added `placement_employer_feedback` table tracking `skill_adequacy_score` (1-5), `practical_readiness` (`PRODUCTION_READY`, `NEEDS_SUPERVISION`, `UNPREPARED`), `missing_skills`, and `training_relevance`. Summarized in `placement_service.py:143-150`. |
| 5 | Institutional Performance | Curriculum Freshness | **IMPLEMENTED** | Phase 15 added `modernity_score` and `health_score` in `backend/app/services/curriculum_engine.py`, tracking syllabus alignment against multi-horizon skill forecasts. `courses.curriculum_version` and `last_curriculum_modernization_at` track active updates. |
| 6 | Institutional Performance | Verified Employer Evidence | **IMPLEMENTED** | Phase 14 (`employer_verifications`) and Phase 16 enforce `is_verified_employer` checks and set `data_provenance = 'EMPLOYER_VERIFIED'` when employer feedback or hiring demand is processed. |
| 7 | Institutional Performance | Outcome Confidence | **IMPLEMENTED** | `placement_service.py:34-41` implements deterministic `get_confidence_tier(candidate_count)` (`INSUFFICIENT_EVIDENCE`, `LOW`, `MODERATE`, `HIGH`) requiring >=15 verified outcomes for high confidence. |
| 8 | Institutional Performance | Historical Institutional Performance | **PARTIALLY IMPLEMENTED** | Legacy `placements` table contains historical cohort counts (`year, student_count, placed_count`), but longitudinal multi-year trend analytics, Year-over-Year (YoY) placement progression, and historical cohort comparisons are not exposed in services or dashboards. |
| **B. Accreditation / Institutional Rating** |
| 9 | Accreditation / Rating | Deterministic Scoring Engine | **MISSING** | No composite institutional accreditation scoring engine exists. While course health score exists (`(placement * 0.55) + (modernity * 0.45)`), there is no multi-dimensional institute-level accreditation score. |
| 10 | Accreditation / Rating | Rating / Tier Calculation | **MISSING** | No institutional accreditation tier or grade assignment (e.g. State Star / Tier 1 / Tier 2 / Provisional / Under Review) exists in schemas, services, or APIs. |
| 11 | Accreditation / Rating | Configurable Criteria | **MISSING** | No weighting rubric model or configuration exists for state accreditation dimensions (e.g., placement outcomes, wage premium, curriculum modernity, employer satisfaction). |
| 12 | Accreditation / Rating | Evidence Thresholds | **PARTIALLY IMPLEMENTED** | Threshold logic exists for placement confidence tiers and course obsolescence flags, but no minimum sample quorum or evidence threshold is enforced for institutional accreditation eligibility. |
| 13 | Accreditation / Rating | Government/Admin Visibility | **MISSING** | Neither `GovernmentDashboard.jsx` nor `AdminDashboard.jsx` contains an Institutional Accreditation or Institute Rating console. The term "Accreditation" only appears in UI labels and proposal reviews in `CurriculumHub.jsx`. |
| 14 | Accreditation / Rating | Audit Trail | **PARTIALLY IMPLEMENTED** | Audit trails exist for curriculum proposals (`reviewed_by`, `adopted_by`, `review_notes`) and employer verifications, but no audit trail exists for institutional accreditation actions or score recalculations. |
| 15 | Accreditation / Rating | Explainability | **PARTIALLY IMPLEMENTED** | Explainability models exist for skills (`SkillExplainabilityModal.jsx`) and course blueprints (`get_course_modernization_blueprint`), but no institutional accreditation scorecard breakdown explainability exists. |
| **C. District Training-to-Employment ROI** |
| 16 | Training-to-Employment ROI | Training Expenditure | **PARTIALLY IMPLEMENTED** | `curriculum_engine.py` maintains `EQUIPMENT_CATALOG` and `TRAINER_UPGRADE_CATALOG` with unit costs in INR. `district_service.py:293` estimates equipment and trainer budgets. However, operational per-student training cost, institutional operational expenditure, and state scheme allocations are not structured. |
| 17 | Training-to-Employment ROI | Number Trained | **IMPLEMENTED** | Tracked via `courses.enrolment_count`, `courses.enrolment_capacity`, and `placement_outcomes` lifecycle records in status `TRAINING_COMPLETED`. |
| 18 | Training-to-Employment ROI | Number Placed | **IMPLEMENTED** | Tracked via `courses.placed_count` and `placement_outcomes` in statuses `PLACED`, `EMPLOYED`, `EMPLOYER_FEEDBACK_PENDING`, `FEEDBACK_RECEIVED`. |
| 19 | Training-to-Employment ROI | Employment Outcomes | **IMPLEMENTED** | Tracked in `placement_outcomes` table with `role_title`, `industry`, `employer_name`, `status`, `placement_date`. |
| 20 | Training-to-Employment ROI | Salary Outcomes | **IMPLEMENTED** | Tracked in `placement_outcomes.salary_annual_inr`. `placement_service.py` calculates `average_salary_annual_inr` and `median_salary_annual_inr`. |
| 21 | Training-to-Employment ROI | Employer Retention | **MISSING** | No candidate tenure or post-placement retention tracking (e.g. 6-month retention rate) exists in data or calculation logic. |
| 22 | Training-to-Employment ROI | ROI Calculation | **MISSING** | No mathematical ROI formula exists comparing training investment against economic return (e.g., Net Economic Value = Total Wages Generated - Training Investment; ROI Ratio = Economic Value / Training Cost). |
| 23 | Training-to-Employment ROI | District Aggregation | **IMPLEMENTED** | `placement_service.py:208-290` (`compute_statewide_placement_analytics`) aggregates candidates, placed counts, placement rates, and average salaries by district. (ROI aggregation itself is missing). |
| 24 | Training-to-Employment ROI | Statewide Aggregation | **IMPLEMENTED** | Statewide aggregations implemented in `placement_service.py:208` and Section 33 platform KPI scorecard in `district_service.py:320-434`. |
| 25 | Training-to-Employment ROI | Real/Demo Isolation | **IMPLEMENTED** | All tables include `is_demo BOOLEAN NOT NULL DEFAULT FALSE`. `app.core.data_mode.is_explicit_demo_mode(is_demo)` and repository filtering ensure strict isolation across queries. |
| **D. Government Decision Intelligence** |
| 26 | Decision Intelligence | Institute Comparison | **PARTIALLY IMPLEMENTED** | `compute_statewide_placement_analytics` ranks `top_performing_courses` and `underperforming_courses` with institute names, but there is no multi-dimensional institutional comparison leaderboard. |
| 27 | Decision Intelligence | District Comparison | **IMPLEMENTED** | `compute_statewide_placement_analytics` and `MaharashtraMap.jsx` provide district-to-district comparisons across placement rate, candidate volume, and skill demand. |
| 28 | Decision Intelligence | Underperformance Detection | **IMPLEMENTED** | Implemented at course level: courses with placement rate < 60% are flagged as underperforming in `placement_service.py:288`, and health score < 42 is flagged as `CRITICAL_OBSOLETE` in `curriculum_engine.py:410`. |
| 29 | Decision Intelligence | Intervention Recommendations | **PARTIALLY IMPLEMENTED** | Course-level interventions exist (modernization blueprints, equipment procurement, trainer upskilling). Formal institutional intervention directives (e.g. performance audit warnings, funding reallocation recommendations) do not exist. |
| 30 | Decision Intelligence | Audit Notices | **MISSING** | No system exists for the government or directorate to issue formal audit notices, compliance warnings, or improvement timelines to underperforming institutions. |
| 31 | Decision Intelligence | Evidence-Backed Policy Signals | **IMPLEMENTED** | Macro industry signals (`industry_signals`), skill placement signals (`compute_skill_placement_signals`), and verified employer demands are cross-referenced in evidence summaries. |
| **E. Governance & Security** |
| 32 | Governance & Security | Government/Admin RBAC | **IMPLEMENTED** | Enforced via `require_roles(["GOVERNMENT", "ADMIN"])` on sensitive endpoints and `verify_admin_access` in `app.core.security`. |
| 33 | Governance & Security | Institute Tenant Isolation | **IMPLEMENTED** | Enforced in `placements.py`, `institute.py`, and `curriculum.py` via IDOR checks (`outcome["institute_id"].lower() == user_org.lower()`). |
| 34 | Governance & Security | Employer Isolation | **IMPLEMENTED** | Enforced in `placements.py:315` and `employer.py`; employers can only inspect and provide feedback for candidates hired by their own organization. |
| 35 | Governance & Security | Student Privacy | **IMPLEMENTED** | Direct student outcome inspection restricted to owning student or admin (`placements.py:231`). Public endpoints expose only aggregated, anonymized metrics. |
| 36 | Governance & Security | Aggregate-Only Public Data | **IMPLEMENTED** | Endpoints `/placements/course/{id}/performance`, `/placements/analytics/skills`, `/curriculum/audit`, and `/districts` return only statistical rollups, concealing individual identities. |
| 37 | Governance & Security | Provenance | **IMPLEMENTED** | `data_provenance` column maintained across all operational tables (`INSTITUTE_AUTHORITATIVE`, `EMPLOYER_VERIFIED`, `UNVERIFIED_EMPLOYER`, `GOVERNMENT_OFFICIAL`, `DEMO_SYNTHETIC`). |
| 38 | Governance & Security | Deterministic Calculations | **IMPLEMENTED** | All scoring algorithms (`health_score`, `gap_pct`, `placement_rate`, `employment_conversion_rate`) are computed via deterministic Python math without non-deterministic heuristics. |
| 39 | Governance & Security | No AI-Controlled Authoritative Scoring | **IMPLEMENTED** | AI (Gemini provider) is strictly restricted to natural-language copilot advisory and drafting; all authoritative scoring, metrics, and risk classifications are pure Python arithmetic. |
| 40 | Governance & Security | Auditability | **IMPLEMENTED** | All records retain immutable audit columns: `created_at`, `updated_at`, `user_id`, `user_email`, `source`, `data_provenance`, `verification_status`. |

### Capability Summary Counts
- **IMPLEMENTED:** 23
- **PARTIALLY IMPLEMENTED:** 9
- **MISSING:** 8
- **NOT APPLICABLE:** 0
- **Total Capabilities Audited:** 40

---

## 3. Existing Functionality Reused (Anti-Duplication)

Phase 17 must build strictly on top of existing foundations from Phases 12–16. Under no circumstances should the following existing systems be rebuilt:

1. **Placement Outcomes & Feedback Data Layer (Phase 16):**
   - *Existing Files:* `backend/app/routers/placements.py`, `backend/app/services/placement_service.py`, `backend/app/repositories/supabase_repository.py` (lines 2760–2945).
   - *Tables:* `placement_outcomes`, `placement_employer_feedback`.
   - *Reuse:* Phase 17 must read existing verified placement outcomes and post-hire employer feedback directly. It must NOT create a parallel placement tracking schema.
   - *Genuinely New:* Institute-level rollup, multi-course aggregation, and composite accreditation scoring.

2. **Curriculum Health & Modernity Engine (Phase 15):**
   - *Existing Files:* `backend/app/services/curriculum_engine.py`, `backend/app/routers/curriculum.py`.
   - *Tables:* `courses`, `curriculum_proposals`.
   - *Reuse:* `audit_all_courses()` already calculates `modernity_score` (0–100), `health_score`, `obsolescence_risk`, and cataloged equipment/trainer costs. Phase 17 will ingest these existing scores directly as the "Curriculum Quality" dimension in the institutional accreditation formula.
   - *Genuinely New:* Aggregating course modernity across an entire institute's catalog into a single institutional curriculum freshness index.

3. **Employer Trust & Verification Pipeline (Phase 14):**
   - *Existing Files:* `backend/app/services/employer_verification.py`, `backend/app/repositories/supabase_repository.py` (lines 2380–2570).
   - *Tables:* `employers`, `employer_verifications`.
   - *Reuse:* Verification status (`is_verified_employer`) is already enforced. Phase 17 must weight employer feedback from verified partners higher in accreditation scoring without altering verification tables.

4. **District Plans & Macro Metrics (PROJECT_SPEC §13, §33):**
   - *Existing Files:* `backend/app/services/district_service.py`, `backend/app/routers/districts.py`.
   - *Reuse:* District boundaries, course counts, and Section 33 platform KPIs are already calculated. Phase 17 must extend `district_service.py` to add ROI metrics rather than creating a disjoint district system.

5. **Security, Auth & RBAC (Phase 23, 14, 16):**
   - *Existing Files:* `backend/app/core/security.py`, `backend/app/core/data_mode.py`.
   - *Reuse:* Existing role guards (`require_roles(["GOVERNMENT", "ADMIN"])`, `require_roles(["INSTITUTE", "ADMIN"])`) and `is_demo` isolation routines.

---

## 4. Missing Functionality (Genuinely New Phase 17 Capabilities)

The audit reveals four genuinely missing capability pillars that define Phase 17:

### Pillar 1: Institutional Accreditation & Rating Engine
- **Composite Scoring Formula:** A deterministic, weighted index across 4 core dimensions:
  1. *Verified Placement & Employment Rate (35% weight):* Aggregated across all institute course cohorts.
  2. *Curriculum Modernity & Industry Alignment (25% weight):* Average course modernity score and active modernization proposal adoption.
  3. *Employer Satisfaction & Graduate Readiness (20% weight):* Weighted average of `skill_adequacy_score` (converted to 0–100) and `practical_readiness` from verified employers.
  4. *Salary Performance & Wage Premium (20% weight):* Institute median/average salary benchmarked against district/industry baseline.
- **Accreditation Tier Grading:**
  - `TIER_1_EXCELLENCE`: Composite Score >= 85, Placement Rate >= 75%, Sample Quorum >= 15 outcomes.
  - `TIER_2_ACCREDITED`: Composite Score 70–84, Placement Rate >= 60%, Sample Quorum >= 10 outcomes.
  - `TIER_3_PROVISIONAL`: Composite Score 55–69 or Sample Quorum < 10 (flagged "Evidence Pending").
  - `TIER_4_PERFORMANCE_WATCH`: Composite Score < 55 or Placement Rate < 45%.
- **Evidence Quorum Enforcement:** Strict rule that an institute cannot be awarded Tier 1 or Tier 2 status without statistically significant verified outcomes (`HIGH` or `MODERATE` confidence tier).

### Pillar 2: District Training-to-Employment ROI Analytics Engine
- **Deterministic ROI Model:**
  - *Annual Economic Output (AEO):* `Placed Graduates × Average Annual Salary (INR)`.
  - *Public Training Investment (PTI):* `(Enrolled Students × Baseline Cost Per Seat) + Lab Equipment Grants + Trainer Upskilling Grants`.
  - *Net Economic Benefit (NEB):* `AEO - PTI`.
  - *ROI Ratio / Multiplier:* `round(AEO / max(1, PTI), 2)` (e.g. 3.4x return on public training capital).
  - *Payback Period (Months):* Estimated time in months for graduate tax/economic contribution to offset training investment.
- **Aggregations:** Program-level ROI, Institute-level ROI, District-level ROI, and Statewide Macro ROI.

### Pillar 3: Government Institutional Benchmarking & Audit Notices Console
- Multi-dimensional ranking leaderboard comparing technical institutes across Maharashtra on accreditation score, placement rate, average wage, and ROI.
- Underperformance detection and formal issuance of **State Performance Audit Notices** (with regulatory reason, remediation deadline, and mandated actions).

### Pillar 4: Lightweight Retention Tracking
- Introduction of an optional `retention_status` field (`6_MONTH_RETAINED`, `12_MONTH_RETAINED`, `ATTRITED`, `UNKNOWN`) to track graduate career sustainability.

---

## 5. Data Gap Analysis

| Data Field / Entity | Status | Existing Location / Source | Gap & Remediation Strategy |
|---|---|---|---|
| **Placement Outcomes** | **EXISTS** | `placement_outcomes` table (Phase 16) | Fully available; contains course, institute, salary, status, candidate ID. |
| **Employer Feedback** | **EXISTS** | `placement_employer_feedback` table (Phase 16) | Fully available; contains adequacy score, readiness, missing skills. |
| **Course & Syllabus Alignment** | **EXISTS** | `courses`, `curriculum_proposals` tables | Fully available; contains curriculum version, modernization date, capacity. |
| **District Geography** | **EXISTS** | `courses.district`, `jobs.district`, `placement_outcomes.district` | Fully available across all 36 Maharashtra districts. |
| **Graduate Salary** | **EXISTS** | `placement_outcomes.salary_annual_inr` | Fully available for wage premium calculations. |
| **Equipment & Trainer Costs** | **EXISTS** | `EQUIPMENT_CATALOG`, `TRAINER_UPGRADE_CATALOG` in `curriculum_engine.py` | Hardware packages and instructor training costs are cataloged in INR. |
| **Candidate Count / Cohort Size** | **EXISTS** | `courses.enrolment_capacity`, `courses.enrolment_count`, `placements.student_count` | Available for cohort sizing. |
| **Institutional Master Registry** | **PARTIAL** | Inferred from `courses.institute_id` and `courses.institute` | No separate `institutes` table exists. Institutes are registered via `courses` and authenticated via `users.organization_id`. **Strategy:** Maintain current architecture by aggregating over `institute_id` from existing `courses` and `placement_outcomes`, avoiding unnecessary new master tables. |
| **Operational Training Cost Per Seat** | **PARTIAL** | Fixed equipment budgets exist; operational tuition/seat cost is not on `courses` | **Strategy:** Introduce an explicit default benchmark in `accreditation_service.py` (e.g. ₹35,000 per student/year based on Maharashtra DTE/DVET standard norms) with optional course-level override. |
| **Graduate Retention (6m/12m)** | **MISSING** | Neither table currently stores retention tenure | **Strategy:** Add nullable `retention_status` column to `placement_outcomes` via migration. |
| **Accreditation Rating History** | **MISSING** | No accreditation table exists | **Strategy:** Create minimal `institution_accreditations` and `institution_audit_notices` tables. |
| **Accreditation Rubric Configuration** | **MISSING** | No configurable criteria weights stored | **Strategy:** Store authoritative default weights in `accreditation_service.py` with optional state configuration override. |

---

## 6. Security & Governance Gap Analysis

1. **RBAC Rules for Accreditation:**
   - Public / Students: Can view aggregate institutional accreditation tiers and district ROI leaderboards.
   - Institutes: Can view their own detailed scorecard, breakdown, and received audit notices; cannot evaluate or grade themselves.
   - Government / Admin: Can trigger accreditation re-evaluations, modify criteria weights, issue formal audit notices, and view unmasked statewide audit trails.
2. **IDOR Prevention:**
   - Institute deans cannot view non-public candidate records or internal audit directives issued to competitor institutes.
3. **Student Privacy:**
   - Accreditation and ROI analytics must be strictly aggregate-only. Candidate names and IDs must never appear in accreditation scorecards or ROI summaries.
4. **Deterministic Calculation Boundary:**
   - Composite scores, accreditation tiers, and ROI numbers must be computed 100% deterministically in Python arithmetic. AI Copilot must only explain results, never calculate or alter authoritative ratings.

---

## 7. Proposed Minimal Architecture

Following the *"Ponytail: lazy senior dev mode"* guideline, the architecture introduces the fewest files and smallest diffs possible:

```
┌────────────────────────────────────────────────────────────────────────┐
│                          FASTAPI APPLICATION                           │
├──────────────────────────────────┬─────────────────────────────────────┤
│ Existing Routers (Phase 12-16)   │ New Router:                         │
│ - placements.py (REUSED)         │ - accreditation.py                  │
│ - curriculum.py (REUSED)         │   * GET  /accreditation/institutes  │
│ - districts.py (REUSED)          │   * GET  /accreditation/institutes/{id}
│ - institute.py (REUSED)          │   * POST /accreditation/evaluate    │
│ - gov_opportunities.py (REUSED)  │   * POST /accreditation/notices     │
│                                  │   * GET  /analytics/roi/districts   │
│                                  │   * GET  /analytics/roi/statewide   │
├──────────────────────────────────┼─────────────────────────────────────┤
│ Core Services Layer              │ Core Services Layer (Extended)      │
│ - placement_service.py (REUSED)  │ - accreditation_service.py (NEW)    │
│ - curriculum_engine.py (REUSED)  │   * compute_institute_scorecard()   │
│ - district_service.py (EXTENDED) │   * compute_training_roi()          │
│   * add get_district_roi_plan()  │   * evaluate_accreditation_tier()   │
├──────────────────────────────────┼─────────────────────────────────────┤
│ Database Tables (Supabase / PG)  │ Database Tables (New Minimal)       │
│ - courses (REUSED)               │ - institution_accreditations (NEW)  │
│ - placement_outcomes (EXTENDED:  │ - institution_audit_notices (NEW)   │
│     retention_status)            │                                     │
│ - placement_employer_feedback    │                                     │
│ - employer_verifications         │                                     │
└──────────────────────────────────┴─────────────────────────────────────┘
```

### New Database Schema (Minimal SQL Migration)
```sql
-- Migration: 20260922_phase17_institutional_accreditation_roi.sql

-- 1. Extend placement_outcomes with optional retention tracking
ALTER TABLE placement_outcomes 
ADD COLUMN IF NOT EXISTS retention_status TEXT 
CHECK (retention_status IN ('6_MONTH_RETAINED', '12_MONTH_RETAINED', 'ATTRITED', 'UNKNOWN'));

-- 2. Institutional Accreditations
CREATE TABLE IF NOT EXISTS institution_accreditations (
    id TEXT PRIMARY KEY,
    institute_id TEXT NOT NULL,
    institute_name TEXT NOT NULL,
    district TEXT NOT NULL,
    composite_score NUMERIC(5, 2) NOT NULL,
    accreditation_tier TEXT NOT NULL CHECK (accreditation_tier IN ('TIER_1_EXCELLENCE', 'TIER_2_ACCREDITED', 'TIER_3_PROVISIONAL', 'TIER_4_PERFORMANCE_WATCH')),
    placement_score NUMERIC(5, 2) NOT NULL,
    curriculum_score NUMERIC(5, 2) NOT NULL,
    employer_satisfaction_score NUMERIC(5, 2) NOT NULL,
    wage_premium_score NUMERIC(5, 2) NOT NULL,
    evidence_confidence TEXT NOT NULL CHECK (evidence_confidence IN ('HIGH', 'MODERATE', 'LOW', 'INSUFFICIENT_EVIDENCE')),
    total_candidates_evaluated INT NOT NULL DEFAULT 0,
    placed_candidates INT NOT NULL DEFAULT 0,
    average_salary_inr INT NOT NULL DEFAULT 0,
    roi_multiplier NUMERIC(6, 2) NOT NULL DEFAULT 1.0,
    valid_until DATE,
    evaluator_user_id TEXT,
    is_demo BOOLEAN NOT NULL DEFAULT FALSE,
    data_provenance TEXT NOT NULL DEFAULT 'STATE_DETERMINISTIC_ACCREDITATION',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 3. Institutional Audit Notices
CREATE TABLE IF NOT EXISTS institution_audit_notices (
    id TEXT PRIMARY KEY,
    institute_id TEXT NOT NULL,
    institute_name TEXT NOT NULL,
    district TEXT NOT NULL,
    notice_type TEXT NOT NULL CHECK (notice_type IN ('PERFORMANCE_WARNING', 'CURRICULUM_DEFICIT', 'COMPLIANCE_REVIEW', 'EXCELLENCE_COMMENDATION')),
    severity TEXT NOT NULL CHECK (severity IN ('CRITICAL', 'HIGH', 'MEDIUM', 'INFO')),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    mandated_action TEXT,
    deadline_date DATE,
    status TEXT NOT NULL DEFAULT 'ISSUED' CHECK (status IN ('ISSUED', 'IN_REMEDIATION', 'RESOLVED', 'ESCALATED')),
    issued_by TEXT NOT NULL,
    is_demo BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_accreditations_inst_id ON institution_accreditations(institute_id);
CREATE INDEX IF NOT EXISTS idx_accreditations_district ON institution_accreditations(district);
CREATE INDEX IF NOT EXISTS idx_accreditations_tier ON institution_accreditations(accreditation_tier);
CREATE INDEX IF NOT EXISTS idx_audit_notices_inst_id ON institution_audit_notices(institute_id);
```

---

## 8. API Proposal

| Method | Endpoint | Access / Role | Description |
|---|---|---|---|
| `GET` | `/api/accreditation/institutes` | Public / All | List evaluated institutes with accreditation tier, score, and placement summary. Filterable by `district`, `tier`, `is_demo`. |
| `GET` | `/api/accreditation/institutes/{institute_id}` | Public / All | Detailed accreditation scorecard with 4-dimension breakdown, evidence confidence, and ROI ratio. |
| `POST` | `/api/accreditation/institutes/{institute_id}/evaluate` | `GOVERNMENT`, `ADMIN` | Trigger deterministic re-evaluation of an institute's accreditation rating based on latest placement & curriculum data. |
| `GET` | `/api/accreditation/institutes/{institute_id}/notices` | `INSTITUTE`, `GOVERNMENT`, `ADMIN` | Retrieve formal audit notices for an institute (scoped by institute tenant). |
| `POST` | `/api/accreditation/institutes/{institute_id}/notices` | `GOVERNMENT`, `ADMIN` | Issue a formal state audit notice or improvement directive. |
| `PATCH` | `/api/accreditation/notices/{notice_id}` | `INSTITUTE`, `GOVERNMENT`, `ADMIN` | Update notice status (e.g. institute marks `IN_REMEDIATION`, gov marks `RESOLVED`). |
| `GET` | `/api/analytics/roi/districts` | Public / All | Leaderboard of Maharashtra districts ranked by training-to-employment ROI multiplier and economic output. |
| `GET` | `/api/analytics/roi/districts/{district}` | Public / All | Deep-dive training expenditure vs graduate wage generation breakdown for a specific district. |
| `GET` | `/api/analytics/roi/statewide` | `GOVERNMENT`, `ADMIN` | Consolidated statewide macroeconomic training ROI scorecard for state executive planning. |

---

## 9. Frontend Proposal

1. **Government Dashboard (`frontend/src/pages/GovernmentDashboard.jsx`):**
   - Add new section/tab: **"State Institutional Accreditation & District ROI"**.
   - Displays:
     - Accreditation Tier Distribution Cards (Tier 1 Stars, Tier 2 Standard, Tier 3 Provisional, Tier 4 Watch).
     - District Training-to-Employment ROI Leaderboard (showing training expenditure vs economic return in ₹ Cr).
     - Institutional Performance & Accreditation Benchmarking Table with search and district filters.
     - Direct action button for government officers to "Issue Audit Notice" or "Re-evaluate Accreditation".
2. **Institute Dashboard (`frontend/src/pages/InstituteDashboard.jsx`):**
   - Add new tab: **"Accreditation & Quality Scorecard"**.
   - Displays:
     - Active Institute Accreditation Tier badge and overall score (out of 100).
     - Radar/Progress bars for the 4 dimensions: Placement Rate, Curriculum Modernity, Employer Readiness, Wage Premium.
     - Active State Audit Notices / Improvement Directives (with remediation deadlines).
     - Guidance notes on exact metrics needed to advance to the next accreditation tier.
3. **API Client (`frontend/src/services/api.js`):**
   - Add client helper functions: `getInstituteAccreditations`, `getInstituteScorecard`, `evaluateInstituteAccreditation`, `getDistrictRoiAnalytics`, `getStatewideRoiAnalytics`, `issueInstituteAuditNotice`.

---

## 10. Test Plan

A dedicated test suite `backend/test_phase17_accreditation_roi.py` must validate all Phase 17 logic:

1. **RBAC & Security Authorization:**
   - Institute user CANNOT evaluate accreditation or issue audit notices to itself or others (`403 Forbidden`).
   - Government user CAN evaluate accreditation and issue audit notices (`200/201`).
   - Anonymous user CAN view aggregate public institute ratings but CANNOT trigger evaluations (`401 Unauthorized`).
2. **IDOR & Scoped Multi-Tenant Isolation:**
   - Institute `usr-institute-001` CANNOT view confidential internal remediation drafts of `usr-institute-002`.
3. **Deterministic Accreditation Scoring Boundaries:**
   - Verify exact composite formula: `Score = (Placement * 0.35) + (Modernity * 0.25) + (Readiness * 0.20) + (Wage * 0.20)`.
   - Verify boundary conditions: Score 85.0 with 75% placement = `TIER_1_EXCELLENCE`; Score 84.9 = `TIER_2_ACCREDITED`.
4. **Evidence Quorum Enforcement:**
   - High score with < 10 candidates MUST be capped at `TIER_3_PROVISIONAL` with confidence `LOW` / `INSUFFICIENT_EVIDENCE`.
5. **Deterministic ROI Calculations:**
   - Verify `AEO = Placed * Average Salary`.
   - Verify `ROI = AEO / Total Training Cost`. Test zero-cost and zero-candidate boundary cases without division by zero.
6. **District & Statewide Aggregation:**
   - District totals must sum accurately without data leakage across districts.
7. **Real / Demo Data Isolation:**
   - Queries with `is_demo=False` must strictly exclude synthetic demo institutes and outcomes.
8. **Regressions against Phases 12–16:**
   - All tests in `test_phase16_placement_outcomes.py`, `test_phase15_curriculum_modernization.py`, `test_phase14_employer_verification.py`, and `test_phase13_job_intelligence.py` must continue to pass 100%.

---

## 11. Risks & Mitigations

| Risk | Impact | Mitigation Strategy |
|---|---|---|
| **Data Sparseness in Rural ITIs** | Small institutes with few graduates might be unfairly penalized with Tier 4 rating. | Implement explicit `TIER_3_PROVISIONAL` ("Evidence Pending") status for cohorts under 10 candidates rather than failing them. |
| **Operational Cost Variations** | Actual training cost varies significantly by trade (e.g. Welder vs Software Developer). | Allow trade-specific cost categories from `EQUIPMENT_CATALOG` combined with standardized per-seat baseline. |
| **Institutional Resistance to Public Ratings** | Institutes may dispute automated ratings. | Transparent explainability breakdown detailing exact calculation inputs; formal dispute/remediation workflow via audit notices. |
| **Database Bloat from Intermediate Metrics** | Storing too many fine-grained daily calculations. | Cache calculated rollups with periodic re-evaluation on placement or curriculum events. |

---

## 12. Recommended Phase 17 Scope

We recommend scoping Phase 17 strictly to:
1. **Migration & Retention Field:** Add `retention_status` to `placement_outcomes`, plus `institution_accreditations` and `institution_audit_notices` tables.
2. **Accreditation & ROI Engine:** Implement `backend/app/services/accreditation_service.py` with deterministic composite scoring and training-to-employment ROI calculations.
3. **Accreditation Router:** Implement `backend/app/routers/accreditation.py` with full RBAC, tenant isolation, and audit notice workflows.
4. **Government & Institute Dashboards:** Add Accreditation & ROI leaderboards to `GovernmentDashboard.jsx` and the Quality Scorecard to `InstituteDashboard.jsx`.
5. **Comprehensive Automated Tests:** Implement `backend/test_phase17_accreditation_roi.py` covering RBAC, IDOR, score boundaries, ROI formulas, and regression.

---

## 13. Explicit List of Things NOT to Rebuild

To maintain maximum development velocity and respect the Ponytail lazy senior dev principles, DO NOT rebuild:
- ❌ **DO NOT rebuild placement recording or outcome tracking** — reuse Phase 16 `placement_outcomes`.
- ❌ **DO NOT rebuild employer post-hire feedback forms** — reuse Phase 16 `placement_employer_feedback`.
- ❌ **DO NOT rebuild course health or curriculum modernization scoring** — reuse Phase 15 `curriculum_engine.py`.
- ❌ **DO NOT rebuild employer verification or trust scoring** — reuse Phase 14 `employer_verifications`.
- ❌ **DO NOT create an independent `institutes` master table** — aggregate over existing `institute_id` and `courses` records.
- ❌ **DO NOT rebuild job intelligence or skill gap formulas** — reuse Phase 13 and `gap_engine.py`.
- ❌ **DO NOT use LLM generative models for authoritative scores** — keep all ratings and ROI math 100% deterministic in Python.
