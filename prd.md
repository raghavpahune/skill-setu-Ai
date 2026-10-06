# SkillSetuAI — Product Requirements Document (PRD)

## 1. Executive Summary & Purpose

SkillSetuAI is an AI-powered labour-market intelligence and curriculum-alignment platform built for the **Government of Maharashtra (Department of Skills, Employment, Entrepreneurship & Innovation / Maharashtra State Innovation Society)**.

The platform bridges the gap between fast-evolving industrial demand and state-level vocational training programs. It continuously converts live labour-market signals, employer job postings, and economic forecasts into actionable decisions for policy officers, vocational training institutes (ITIs and Polytechnics), employers, and students.

---

## 2. SIH Problem Context & Core Objectives

### The Problem
Traditional vocational and technical education frequently suffers from structural disconnects:
- **Curriculum Lag:** Institutional syllabi, lab equipment, and faculty training lag 3–5 years behind emerging industrial standards (AI/ML, Electric Vehicles, Industry 4.0 automation, Green Hydrogen).
- **Skill Mismatch:** High enrolment in obsolete or oversupplied courses leads to low placement rates and graduate underemployment.
- **Data Asymmetry:** District planners lack real-time visibility into local industry hiring needs, causing state training subsidies to be allocated inefficiently.
- **Unverified Feedback:** Informal placement metrics without verified employer feedback prevent data-driven curriculum modernization.

### The Objective
SkillSetuAI creates a continuous, evidence-grounded feedback loop across four pillars:
```
LABOUR MARKET DEMAND (Live Jobs & Signals)
        ↓
SKILL GAP ENGINE (NSQF-Aligned Gap Quantification)
        ↓
CURRICULUM MODERNIZATION & ACCREDITATION (Health Scores & Upgrades)
        ↓
PLACEMENT & WORKFORCE FEEDBACK LOOP (Employer Verification & ROI)
```

---

## 3. Target User Personas & Roles

The platform enforces strict Role-Based Access Control (RBAC) across six user personas:

| Role | Target Persona | Primary Responsibilities & Key Workflows |
|---|---|---|
| **GOVERNMENT** | State Skills Directorate & District Skill Development Officers (DSDO) | Statewide intelligence monitoring, district training plan approval, policy simulation, institutional performance oversight, training-to-employment ROI evaluation. |
| **INSTITUTE** | Principals & HODs of ITIs, Polytechnics, and Vocational Colleges | Course health auditing, curriculum modernization blueprints, lab equipment and trainer upskilling planning, placement outcome tracking. |
| **EMPLOYER** | Industrial HR Leaders & Plant Hiring Managers | Posting hiring demands, verifying candidates, submitting post-hire practical readiness feedback, validating emerging skill signals. |
| **STUDENT** | ITI/Polytechnic students & Vocational Job Seekers | Dynamic skill assessment, personalised Skill Passport, radar profile visualization, step-by-step NSQF roadmaps, government opportunity matching. |
| **EMPLOYEE** | Mid-career workers seeking upskilling/reskilling | Career transition passport, skill gap evaluation against target industry roles, lifelong learning pathways. |
| **ADMIN** | Platform Superusers & State System Administrators | Verification moderation, user management, audit logging, ingestion pipeline oversight, system health diagnostics. |

---

## 4. Core Product Loop

1. **Market Signal Capture:** The system captures live job postings, industry signals (investments, plant expansions, policy incentives), and employer hiring demands.
2. **Skill Demand Extraction:** Job descriptions and signals are mapped to standardized NSQF skills and NCO-2015 occupational codes.
3. **Institutional Curriculum Auditing:** The curriculum engine evaluates existing courses against market demand, computing Course Health Scores, Obsolescence Risk, and syllabus modernization blueprints.
4. **Student Assessment & Guidance:** Students complete adaptive diagnostic assessments; the system computes personal skill gaps and generates tailored career roadmaps.
5. **Verified Employment & Outcome Ingestion:** Post-graduation hiring outcomes are recorded, verified by employers, and enriched with employer readiness feedback.
6. **Accreditation & Economic ROI:** Aggregated institutional performance feeds a deterministic accreditation tiering engine and district-level training ROI analytics.

---

## 5. Major Product Capabilities Actually Present in Codebase

### A. State & District Labour-Market Intelligence
- **Interactive Maharashtra Map:** SVG and Leaflet-based district drilldown across Maharashtra (Pune, Mumbai, Nagpur, Nashik, Chhatrapati Sambhaji Nagar, etc.).
- **Multi-Horizon Skill Forecasting:** 6-month, 12-month, and 24-month horizon forecasting models with confidence scores, growth drivers, and risk factors (`forecast_engine.py`).
- **Policy Simulator:** Interactive scenario modeling estimating the economic impact of training subsidies, seat reallocations, and employer tax credits (`simulator.py`).
- **District Workforce Action Plans:** Automated generation of district training recommendations, equipment procurement budgets, and trainer capacity requirements (`district_service.py`).

### B. Curriculum Modernization & Course Health Engine
- **Deterministic Course Health Score:** Algorithmic calculation evaluating placement efficiency (55%) and curriculum modernity (45%) (`curriculum_engine.py`).
- **Automated Obsolescence Detection:** Automatic flagging of courses as `HEALTHY`, `NEEDS_REVIEW`, or `CRITICAL_OBSOLETE`.
- **Syllabus Modernization Blueprints:** Detailed module-level recommendations for modules to add, modules to prune, and hours reallocated.
- **Cataloged Resource Budgets:** Prescriptive lab equipment catalogs and faculty upskilling programs with standard INR unit cost benchmarks.

### C. Placement Outcomes & Workforce Feedback Intelligence
- **Placement Lifecycle Tracking:** End-to-end lifecycle state machine (`TRAINING_COMPLETED` → `PLACEMENT_PENDING` → `PLACED` → `EMPLOYED` → `EMPLOYER_FEEDBACK_PENDING` → `FEEDBACK_RECEIVED`).
- **Post-Hire Employer Feedback:** Standardized scoring for skill adequacy (1–5 scale), practical readiness (`PRODUCTION_READY`, `NEEDS_SUPERVISION`, `UNPREPARED`), and missing skills.
- **Evidence Confidence Tiers:** Deterministic quorum tiers (`INSUFFICIENT_EVIDENCE`, `LOW`, `MODERATE`, `HIGH`) requiring >=15 verified candidate outcomes for high confidence.

### D. Institutional Accreditation & Training-to-Employment ROI
- **Institutional Accreditation Scorecard:** 4-tier accreditation model (`TIER_1_EXCELLENCE`, `TIER_2_ACCREDITED`, `TIER_3_PROVISIONAL`, `TIER_4_PERFORMANCE_WATCH`).
- **Training-to-Employment Economic ROI:** Deterministic calculation of Net Economic Benefit, ROI Multiplier, and Payback Period in months (`accreditation_service.py`).
- **Audit Notices & Performance Improvement Plans:** Formal government notice issuance workflow for underperforming institutions with compliance deadlines.

### E. Student Skill Passport & Adaptive Guidance
- **Personalized Skill Passport:** Multi-dimensional skill profile with NSQF level tracking, verified skills, and radar chart visualization (`PassportRadar.jsx`).
- **Adaptive Diagnostic Assessment:** Interactive domain quiz capturing proficiency across theory, practical application, and tools (`StudentAssessmentForm.jsx`).
- **Explainable Career Matching:** Transparent matching against benchmark career roles with detailed "why recommended" explanations (`career_recommendation_engine.py`).
- **Step-by-Step Roadmaps:** Milestone-based learning roadmaps incorporating government schemes (PMKVY, MSSDS, Apprenticeship Promotion Scheme).

### F. Employer Demand & Verification Hub
- **Employer Verification Workflow:** Government admin review and approval of enterprise registrations (`employer_verification.py`).
- **Verified Demand Posting:** Structured hiring intake capturing required skills, NSQF levels, vacancies, and salary brackets.

### G. Advisory AI Copilot
- **Multi-Workload AI Router:** Unified routing layer supporting 8 distinct task workloads (`ai/router.py`).
- **Strictly Advisory Role:** AI generates conversational explanations and draft recommendations; all authoritative scoring, metrics, and gate checks remain 100% deterministic backend logic.
- **Resilient Fallback:** 100% offline-capable deterministic rule-based fallback provider when Gemini API is unconfigured or rate-limited.

---

## 6. Current Scope & Production Baseline

- **Verified Production URLs:**
  - Production Frontend: `https://skill-setu-rust.vercel.app` (Vercel)
  - Production Backend: `https://skill-setu-backend-jklo.onrender.com` (Render)
  - System of Record: Supabase PostgreSQL
- **Data Footprint:**
  - Full demo mode ships with realistic Maharashtra data across 5 pilot districts, 50+ skills, 500+ jobs, 25+ courses, 15+ employers.
  - Real public datasets incorporated: NSDC Qualification Packs, NCO-2015 occupational standards, Maharashtra government apprenticeship schemes.
- **Audit Baseline:**
  - Production warmup: 13/13 passed.
  - Backend targeted tests: 10/10 passed.
  - Ruff linting: 0 errors.
  - Frontend build: passed.
  - Frontend lint: passed.
  - Frontend tests: 24/25 passed.
  - Backend test suite: ~894 tests across 73 test files.

---

## 7. Known Limitations & Technical Debt

The following issues were established during the project restart audit and are tracked for subsequent phases:
1. **Accreditation Router In-Memory Fallback (P0):** In non-demo mode, `backend/app/routers/accreditation.py` falls back to querying the in-memory cache `_cache.get("institution_accreditations", [])` if repository queries return empty or error. This violates the zero-silent-fallback rule.
2. **Profile Validation Discrepancy (P1):** Field validation logic in `frontend/src/utils/profileValidator.js` has minor discrepancies with backend schema requirements, causing 1 frontend test failure (24/25 passed).
3. **Ruff Exclusion Configuration (P1):** `ruff.toml` excludes scripts/scratch directories that require tighter alignment with repository CI.
4. **EmployerDashboard Silent Feedback Failure (P2):** Error handling during employer candidate feedback submission in `EmployerDashboard.jsx` fails silently without notifying the user when an API error occurs.
5. **Frontend Test CI Integration (P2):** Frontend test execution script is not yet integrated into `package.json` scripts.

---

## 8. Future Scope (Not Yet Implemented)

The following capabilities are planned for future phases but are explicitly **not implemented** in the current codebase:
- **pgvector Semantic RAG:** Vector embeddings for semantic search over unstructured university syllabus PDFs (database schema has reserved column, but vector search pipeline is inactive).
- **DigiLocker / APAAR ID Integration:** Direct API integration with India Stack digital credentials for instant academic certificate verification.
- **Statewide 36-District Expansion:** Expansion of live scraping and telemetry across all 36 Maharashtra districts.
- **Bilingual Marathi UI:** Complete localization of all dashboards and copilot responses in Marathi.
