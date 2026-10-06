# SkillSetuAI — System Architecture

## 1. High-Level Architectural Topology

SkillSetuAI is architected as a modern, decoupled web application with strict separation between user interfaces, API routing, deterministic intelligence services, persistent storage, and advisory AI components.

```
┌────────────────────────────────────────────────────────────────────────┐
│                      FRONTEND LAYER (Vercel)                          │
│  React 19 + Vite 8 + Tailwind CSS v4 + Recharts + React-Leaflet        │
│  Context Providers: AuthContext, ThemeContext, TourContext             │
│  Pages: 13 Role Dashboards & Workspaces | 15 Interactive Components    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTPS / REST (JSON) + JWT Bearer
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      BACKEND LAYER (Render)                            │
│  FastAPI (Python 3.11) + Uvicorn ASGI Server                           │
│  Lifespan Management, CORS Middleware, Background Scheduler            │
├────────────────────────────────────────────────────────────────────────┤
│                      SECURITY & RBAC GATEWAY                           │
│  HTTP Bearer Authentication, JWT Verification (HS256)                  │
│  Bcrypt Password Hashing, Role Dependencies (require_roles)            │
│  Strict Cross-Tenant IDOR Protection & Admin Access Verification       │
├────────────────────────────────────────────────────────────────────────┤
│                      BUSINESS & INTELLIGENCE SERVICES                  │
│  Deterministic Mathematical Engines (Pure Python, Zero AI Bias):       │
│  - Accreditation & ROI Engine (accreditation_service.py)               │
│  - Curriculum Modernization & Obsolescence (curriculum_engine.py)      │
│  - Placement Outcomes & Workforce Feedback (placement_service.py)      │
│  - Career Recommendation & Matching (career_recommendation_engine.py)  │
│  - Multi-Horizon Skill Forecasting (forecast_engine.py)                │
│  - District Workforce Planning (district_service.py)                   │
│  - Student Skill Passport & Diagnostics (student_service.py)           │
├───────────────────────────────────┬────────────────────────────────────┤
│                                   │                                    │
│   ADVISORY AI LAYER               │   DATA ACCESS LAYER                │
│   (ai/router.py)                  │   (repositories/supabase_repository.py│
│   - Primary: Google Gemini        │   - Supabase PostgreSQL Client     │
│   - Fallback: DemoProvider        │   - Atomic Transactions & RPCs     │
│   - 8 Task Workloads              │   - Row-Level Security (RLS)       │
│   - Strictly Advisory Output      │   - In-Memory Cache (Demo Mode)    │
└─────────────────┬─────────────────┴───────────────────┬────────────────┘
                  │                                     │
                  ▼                                     ▼
┌───────────────────────────────────┐ ┌──────────────────────────────────┐
│        EXTERNAL SERVICES          │ │       SYSTEM OF RECORD           │
│  - Google Gemini API              │ │  Supabase PostgreSQL Database    │
│  - Public NSDC / NCO Data         │ │  22 Structured Domain Tables     │
│  - Industry Telemetry Signals     │ │  Immutable Audit Log Trails      │
└───────────────────────────────────┘ └──────────────────────────────────┘
```

---

## 2. Frontend Structure

### Stack & Build Setup
- **Framework:** React 19.2, Vite 8.2, React Router DOM 7.18.
- **Styling:** Tailwind CSS v4.3 with custom theme tokens defined in `src/index.css`.
- **Visualizations:** Recharts 3.10 (Bar, Line, Area, Radar charts), React-Leaflet 5.0 (interactive Maharashtra district geographic visualization).
- **Hosting:** Vercel (`https://skill-setu-rust.vercel.app`).

### Component Hierarchy & Routing
- **Entry Points:** `main.jsx` → `App.jsx` with lazy-loaded route chunking and `RouteLoadingFallback`.
- **Global Contexts:**
  - `AuthContext.jsx`: User session state, JWT storage, role state, login/logout actions.
  - `ThemeContext.jsx`: Dark/light mode theme toggling with smooth CSS transitions.
  - `TourContext.jsx`: Guided product walkthrough overlay across key personas.
- **Pages (13 Total):**
  - Public / Entry: `Landing.jsx`, `Login.jsx`, `Register.jsx`, `CopilotPage.jsx`.
  - Government / Policy: `GovernmentDashboard.jsx`, `DistrictPlan.jsx`.
  - Institute: `InstituteDashboard.jsx`, `CurriculumHub.jsx`.
  - Employer: `EmployerDashboard.jsx`.
  - Student & Professional: `StudentDashboard.jsx`, `StudentProfile.jsx`, `EmployeeProfile.jsx`.
  - Administrative: `AdminDashboard.jsx` (wrapped in `AdminErrorBoundary.jsx`).
- **Core Components (15 Total):**
  - `Layout.jsx`: Responsive shell with role-aware header navigation, health indicators, keyboard shortcuts (`Cmd+K`).
  - Specialized widgets: `MaharashtraMap.jsx`, `PassportRadar.jsx`, `StudentAssessmentForm.jsx`, `CareerRecommendationsView.jsx`, `SkillExplainabilityModal.jsx`, `SkillGapBar.jsx`, `StudentAlertsFeed.jsx`, `CopilotChat.jsx`.

---

## 3. Backend Structure

### Stack & Runtime
- **Framework:** Python 3.11, FastAPI 0.110+, Uvicorn ASGI.
- **Hosting:** Render (`https://skill-setu-backend-jklo.onrender.com`).
- **Application Lifespan:** Managed via `asynccontextmanager` in `main.py`:
  - Startup: Verifies environment constraints (e.g. fatal exit if demo auth is enabled in production), initializes database layer (`init_db()`), starts background ingestion scheduler (`scheduler.start()`).
  - Shutdown: Graceful cancellation of background scheduler (`scheduler.stop()`).

### Modular Routers (23 Routers under `backend/app/routers/`)
1. `auth.py`: User registration, JWT login, profile self-lookup.
2. `profile.py`: Student and employee career passport lifecycle management.
3. `skills.py`: Skill master taxonomy queries and search.
4. `jobs.py`: Job posting ingestion, district filtering, and skill demands.
5. `gaps.py`: Aggregated labour-market skill gap queries.
6. `courses.py`: Course listings, capacity, and enrolment data.
7. `curriculum.py`: Curriculum health auditing and syllabus modernization proposals.
8. `placements.py`: Verified placement outcomes and employer post-hire feedback.
9. `accreditation.py`: Institutional accreditation scoring, tiers, and audit notices.
10. `institute.py`: Institute tenant profile and course management.
11. `signals.py`: Real-time industrial investment and market telemetry signals.
12. `forecast.py`: Multi-horizon (6M, 12M, 24M) skill demand projections.
13. `districts.py`: District-level training demand rollups.
14. `student.py`: Personalized skill assessment, diagnostic submission, and roadmap generation.
15. `copilot.py`: Context-grounded AI copilot conversational endpoints.
16. `employer.py`: Employer hiring demands and applicant review.
17. `schemes.py`: Government vocational schemes and financial subsidies.
18. `opportunities.py`: Apprenticeship, internship, and hiring opportunities.
19. `gov_opportunities.py`: Government opportunity aggregation and matching.
20. `sync.py`: Manual and automated data synchronization endpoints.
21. `simulator.py`: Policy simulation scenarios and budget impact forecasting.
22. `admin.py`: Superuser moderation, verification approvals, and audit log inspection.
23. `health` (in `main.py`): Comprehensive diagnostic endpoints (`/`, `/health`, `/api/health`, `/api/health/ai`).

---

## 4. Business & Intelligence Services

The intelligence engine lives in `backend/app/services/` and operates on strict mathematical, deterministic logic:

| Service Module | Purpose & Core Logic | Key Calculations & Outputs |
|---|---|---|
| `accreditation_service.py` | Institutional evaluation & state training ROI | Composite accreditation score (outcomes 40%, curriculum 30%, feedback 20%, stability 10%), Tier classification (Tiers 1–4), Net Economic Benefit, ROI Multiplier, Payback Period. |
| `curriculum_engine.py` | Course health & obsolescence detection | Course Health Score (`placement_rate * 0.55 + modernity_score * 0.45`), Obsolescence risk categorization (`HEALTHY`, `NEEDS_REVIEW`, `CRITICAL_OBSOLETE`), modernization syllabus blueprints. |
| `placement_service.py` | Placement lifecycle & workforce feedback | Placement rate calculation, employment conversion rate, average/median salary rollups, evidence confidence tiering (`INSUFFICIENT_EVIDENCE` to `HIGH`). |
| `career_recommendation_engine.py` | Personalized candidate matching | Career role fit scoring against standard benchmarks, skill-gap identification, explainable justification strings. |
| `forecast_engine.py` | Predictive labour demand | Multi-horizon regression and trend analysis across 6, 12, and 24-month windows, growth driver attribution. |
| `district_service.py` | Localized district workforce planning | District seat allocation recommendations, required equipment budgets, trainer upskilling targets. |
| `student_service.py` | Assessment scoring & profile persistence | Assessment grading, mastery level calculation, atomic profile persistence. |
| `roadmap_service.py` | Milestones & learning progression | Step-by-step NSQF milestone pathways, government scheme linkage. |
| `employer_verification.py` | Enterprise legitimacy checks | Verification state machine (`PENDING` → `VERIFIED` / `REJECTED`), registration vetting. |

---

## 5. Advisory AI Routing Layer (`ai/`)

SkillSetuAI enforces a strict boundary between deterministic software logic and generative AI:
- **Zero Authoritative Scoring by AI:** AI models never assign course health scores, never determine accreditation tiers, never grade student certifications, and never approve funding.
- **Advisory Grounding:** AI output is flagged `advisory: True` and is restricted to natural-language summarization, personalized explanations, and draft assistance.
- **Provider Architecture:**
  - `LLMProvider` (`ai/provider.py`): Abstract base class defining `generate(prompt, context)`.
  - `GeminiProvider` (`ai/gemini_provider.py`): Primary provider utilizing Google Gemini models (`gemini-3.6-flash`).
  - `DemoProvider` (`ai/demo_provider.py`): Deterministic, offline rule-based fallback provider.
- **Workload Routing (`ai/router.py`):**
  - Manages 8 discrete workloads: `career_copilot`, `skill_gap_analysis`, `learning_roadmap`, `employee_transition`, `employer_candidate_analysis`, `institute_curriculum_analysis`, `government_policy_analysis`, `data_insight_generation`.
  - Enforces 12-second timeout protection.
  - Automatic failover to `DemoProvider` on timeout, quota exhaustion (429), authentication failure, or missing API key.

---

## 6. Security, Authentication & Authorization

### Authentication Pipeline
- **Password Security:** Passwords hashed with bcrypt (12 rounds) via `hash_password()` in `app.core.security`.
- **Token Generation:** Stateless JSON Web Tokens (JWT) signed with HS256 algorithm and configured expiration (`JWT_SECRET_KEY`).
- **Token Validation:** `get_current_user` FastAPI dependency extracts and validates Bearer token, checks user active status, and binds identity to the request.

### Authorization & RBAC
- **Role Enforcement:** `require_roles(["GOVERNMENT", "ADMIN"])` dependency factory enforces allowed roles per endpoint.
- **Admin Verification:** `verify_admin_access` validates either an active `ADMIN` JWT token or a secure admin key header (strictly forbidden in production if demo auth is enabled).
- **Tenant Isolation (Anti-IDOR):**
  - Institutes can only update courses and submit outcomes belonging to their `institute_id`.
  - Employers can only view candidates and submit feedback for positions matching their `employer_id`.
  - Students can only view or modify their own profile and assessment records.

---

## 7. Data Layer & System of Record

### Supabase PostgreSQL
- **System of Record:** Supabase is the single source of truth for production.
- **Schema:** 22 domain tables defined in `data/schema.sql` and versioned via sequential migrations in `data/migrations/`.
- **Atomic Operations & RPCs:** Sensitive multi-table mutations (such as profile synchronization and placement submission) utilize atomic database stored procedures to guarantee ACID compliance.
- **Row-Level Security (RLS):** Database policies in `data/schema_rls_policies.sql` enforce multi-tenant isolation directly in PostgreSQL.

### In-Memory Overlay & Dual-Mode Execution
- `app.db._cache`: Holds pre-loaded synthetic datasets for offline demo execution.
- `is_explicit_demo_mode()` (`app.core.data_mode`): Controls whether demo datasets are queried.
- **Strict Isolation Rule:** In non-demo mode, queries execute exclusively against Supabase. Real user workflows never silently degrade to synthetic records.

---

## 8. Deployment Topology

| Component | Target Environment | Key Configuration |
|---|---|---|
| **Frontend** | Vercel Edge / Serverless | Static SPA bundle, environment-injected API URL (`VITE_API_URL`). |
| **Backend** | Render Cloud Platform | Containerized Web Service, Python 3.11, Uvicorn worker, managed HTTPS. |
| **Database** | Supabase Cloud | Managed PostgreSQL 15+, Connection Pooling, RLS enabled, automated backups. |
| **AI Inference** | Google AI Studio | Gemini API key, server-side environment variable only (`GEMINI_API_KEY`). |
