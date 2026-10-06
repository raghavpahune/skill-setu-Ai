# SkillSetuAI — Frontend Design System & UI Architecture

This document specifies the actual frontend design system, component guidelines, theme tokens, and user experience patterns implemented in the SkillSetuAI web application.

---

## 1. Design Philosophy & Aesthetic Foundation

SkillSetuAI utilizes a modern, institutional-grade visual interface tailored for government officials, educational institutions, industrial employers, and students.
- **Visual Identity:** Clean, high-density government dashboard aesthetic with modern tech-forward accents.
- **Theme Foundation:** Dual light/dark theme system implemented via Tailwind CSS v4 custom theme tokens and CSS custom properties (`src/index.css`).
- **Typography:** Modern clean sans-serif typography using Inter (`'Inter', system-ui, -apple-system, sans-serif`).

---

## 2. Color Palette & Theme Tokens

The design tokens are defined in `@theme` inside `frontend/src/index.css`:

### Navy Palette (Primary Brand & Structure)
- `navy-50`: `#f0f4ff` (Ultra light tint)
- `navy-100`: `#dbe4ff` (Light accent border)
- `navy-200`: `#bac8ff`
- `navy-300`: `#91a7ff`
- `navy-400`: `#748ffc`
- `navy-500`: `#5c7cfa`
- `navy-600`: `#4c6ef5`
- `navy-700`: `#3b5bdb`
- `navy-800`: `#1e3a5f` (Deep institutional navy)
- `navy-900`: `#0f172a` (Primary dark background)
- `navy-950`: `#0a0f1e` (Deepest canvas)

### Teal Palette (Accent, Action & Highlights)
- `teal-50`: `#e6fcf5`
- `teal-100`: `#c3fae8`
- `teal-200`: `#96f2d7`
- `teal-300`: `#63e6be`
- `teal-400`: `#38d9a9`
- `teal-500`: `#0d9488` (Primary brand accent & focus ring)
- `teal-600`: `#0c8577` (Hover state)
- `teal-700`: `#0b7566`
- `teal-800`: `#095c51`
- `teal-900`: `#064e3b`

### Surface & Border Tokens
- Light Surfaces: `--color-surface: #ffffff`, `--color-surface-alt: #f8fafc`, `--color-border: #e2e8f0`
- Dark Surfaces: `--color-surface-dark: #0f172a`, `--color-surface-dark-alt: #1e293b`, `--color-border-dark: #334155`
- Text Colors: `--color-text: #1e293b`, `--color-text-dark: #f8fafc`, `--color-text-muted: #64748b`, `--color-text-muted-dark: #94a3b8`

### Semantic Feedback Tokens
- Success: `--color-success: #16a34a` (Green)
- Warning: `--color-warning: #d97706` (Amber)
- Danger: `--color-danger: #dc2626` (Red)

---

## 3. Typography & Hierarchy

Font: `Inter` loaded via system font stack:
- **Display / Hero:** `text-3xl` to `text-5xl font-black tracking-tight` (Landing hero, key metrics).
- **Page Titles (H1):** `text-2xl font-bold text-slate-900 dark:text-white` (Dashboard headers).
- **Section Headers (H2):** `text-lg font-semibold text-slate-800 dark:text-slate-100`.
- **Card Titles (H3):** `text-base font-semibold text-slate-700 dark:text-slate-200`.
- **Body Text:** `text-sm text-slate-600 dark:text-slate-300 leading-relaxed`.
- **Captions & Metadata:** `text-xs text-slate-500 dark:text-slate-400 font-medium`.
- **Badges & Tags:** `text-xs font-semibold px-2.5 py-0.5 rounded-full`.

---

## 4. Layout Architecture & Navigation

### Global Shell (`src/components/Layout.jsx`)
- **Sticky Header Navbar:**
  - SkillSetuAI emblem and government branding.
  - Dynamic role navigation links tailored to the authenticated user.
  - Live system connectivity badge (`Connected`, `Demo Mode`, `Offline`).
  - Dark/Light mode toggle button.
  - Interactive "Take Tour" button (`TourContext`).
  - Mobile hamburger toggle with animated slide-down sheet.
- **Global Shortcut:**
  - `Cmd+K` / `Ctrl+K` opens the AI Copilot console directly from anywhere in the application.
- **Footer:**
  - Institutional identity (Government of Maharashtra — Department of Skills, Employment, Entrepreneurship & Innovation).
  - Role-specific link directory and portal access points.
  - Live API status indicator.

---

## 5. Role-Specific Dashboards & Workspaces

The frontend implements 6 distinct role views:

1. **Government Command (`GovernmentDashboard.jsx` & `DistrictPlan.jsx`):**
   - High-density state overview: Total jobs, active courses, verified placements, skill gap index.
   - Interactive district selection via Maharashtra SVG map and Leaflet map view.
   - Multi-horizon forecast visualization (6M/12M/24M).
   - Policy simulation sandbox for subsidy reallocation.
   - District-specific workforce action plans.

2. **Institute Portal (`InstituteDashboard.jsx` & `CurriculumHub.jsx`):**
   - Course health metrics cards with health score dials (0–100).
   - Obsolescence risk tags (`HEALTHY`, `NEEDS_REVIEW`, `CRITICAL_OBSOLETE`).
   - Detailed curriculum modernization blueprints with added/pruned modules.
   - Equipment and faculty upskilling budget planning tables.

3. **Employer Hub (`EmployerDashboard.jsx`):**
   - Verified demand creation form.
   - Applicant review pipeline with NSQF match percentages.
   - Candidate post-hire feedback submission form with 1–5 skill adequacy rating and readiness tiers.

4. **Student Passport (`StudentDashboard.jsx` & `StudentProfile.jsx`):**
   - Multi-axis Skill Passport Radar (`PassportRadar.jsx`).
   - Dynamic diagnostic assessment form (`StudentAssessmentForm.jsx`).
   - Grounded career recommendations with transparent "Why recommended" reasoning (`CareerRecommendationsView.jsx`).
   - Milestone-based learning roadmaps and government apprenticeship matching.

5. **Employee Profile (`EmployeeProfile.jsx`):**
   - Career passport for working professionals.
   - Experience tracking, current industry skills, and transition target roles.

6. **Admin Board (`AdminDashboard.jsx`):**
   - Verification queue for employer registrations.
   - Verification queue for course modernization proposals.
   - Audit trail explorer.
   - Wrapped in dedicated `AdminErrorBoundary.jsx` to prevent dashboard crash propagation.

---

## 6. Component Library & Visual Patterns

### Key Shared Components
- `StatCard.jsx`: Standard KPI widget with icon, large numerical value, contextual trend badge, and tooltip.
- `MaharashtraMap.jsx`: Interactive Maharashtra district choropleth map supporting zoom, hover tooltips, and click-to-filter.
- `SkillGapBar.jsx`: Horizontal visual comparison bar contrasting demand percentage against institutional training capacity.
- `SkillExplainabilityModal.jsx`: Modal popup providing grounded citations, industry drivers, and growth horizon breakdowns for any skill.
- `RecommendationCard.jsx`: Actionable card for career or course suggestions with fit scores and eligibility badges.
- `CopilotChat.jsx`: Grounded AI conversational drawer with suggested queries, message history, streaming feedback, and role badges.

---

## 7. Data Visualizations & Charts

- **Recharts Library:**
  - `RadarChart`: Visualizes student competency profiles across 6 skill dimensions.
  - `BarChart`: Displays skill gap discrepancies (demand vs supply) and district placement volumes.
  - `LineChart` / `AreaChart`: Visualizes multi-horizon skill growth trajectories and historical cohort trends.
- **Leaflet Maps:**
  - Interactive geographic display of Maharashtra districts with pinned training centers, active vacancies, and district performance colors.

---

## 8. Micro-Animations & Motion Design

Tailwind utility animations defined in `index.css`:
- `animate-fadeIn`: Subtle 0.2s opacity and 4px upward translation on component mount.
- `animate-slide-up`: 0.25s translation for modals and dropdown menus.
- `animate-pulse-subtle`: Gentle breathing animation for live system status indicators.
- **Interactive Button Micro-Transitions:**
  - Hover: `transform: translateY(-1px)` with elevation shadow.
  - Active: `transform: scale(0.98)` for tactile feedback.
- **Accessibility & Reduced Motion:**
  - `@media (prefers-reduced-motion: reduce)` resets all animation durations to `0.01ms` and removes transform translations.

---

## 9. States: Loading, Empty, and Errors

- **Route Loading:** `RouteLoadingFallback` renders a centered teal glowing spinner on lazy route transitions.
- **Component Loading:** Skeleton card loaders with animated pulse shimmer.
- **Empty States:** Clear descriptive empty states with icon, explanatory message, and an action button to initiate data creation.
- **Error Boundaries:** `AdminErrorBoundary.jsx` traps catastrophic dashboard render crashes, offering a reload button without terminating the user session.
