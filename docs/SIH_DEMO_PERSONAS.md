# SkillSetu SIH Demo Persona & Quick-Access Guide (Phase 37.2)

This document is the official operational guide for presenters and demonstrators during the Smart India Hackathon (SIH) live evaluation. It specifies the verified accounts, role-specific login flows, exact screen routes, talking points, non-clickable traps, and failure recovery protocols across all 6 platform roles.

---

## 1. Quick Reference: Demo Execution At-a-Glance

### Before Entering the Presentation Room (T - 3 Minutes)
1. **Wake up the cloud services**:
   ```bash
   python scripts/warmup.py
   ```
   *Verify that all 13 checks return `[PASS]` and the final banner displays `OVERALL DEMO READINESS: DEMO READY`.*
2. **Open a clean browser session**:
   - Launch an **Incognito / Private Window**.
   - Navigate to: `https://skill-setu-rust.vercel.app/login`
   - Hard refresh (`Ctrl + Shift + R` or `Cmd + Shift + R`) to bust any stale service workers or browser cache.
   - Set zoom to **100%** (or **90%** if presenting on a standard 1080p hall projector).

### Optimal 5–7 Minute Presentation Sequence
| Time | Role / View | Route | Key Demo Action | Core Narrative |
|---|---|---|---|---|
| **0:00 - 1:30** | **Government** | `/government` | Maharashtra Interactive Map &rarr; Click Pune &rarr; District Plan &rarr; Policy Simulator | *Macro Problem*: State identifies regional skill deficits before they trigger unemployment. |
| **1:30 - 3:00** | **Employer** | `/employer` | Submit EV / AI Hiring Demand &rarr; GSTIN Validation &rarr; Match Pool | *Market Pull*: Industry defines real demand signals instead of static syllabus committees. |
| **3:00 - 5:00** | **Student** | `/student` | Skill Passport Radar &rarr; Diagnostic Assessment Quiz &rarr; Readiness Report &rarr; Learning Roadmap | *Citizen Impact*: Students receive an objective, NSQF-aligned passport and actionable roadmaps. |
| **5:00 - 6:00** | **Institute** | `/curriculum` | Curriculum Modernization Audit &rarr; Outdated vs Emerging Skill Gap | *Systemic Solution*: Universities & ITIs modernize curricula based on live industry feedback. |
| **6:00 - 7:00** | **Admin / Copilot** | `/admin` & `/copilot` | Data Governance & Grounded AI Copilot Response | *Trust & Verification*: Complete data provenance, RBAC enforcement, and grounded guidance. |

---

## 2. Global Authentication Architecture & Credential Matrix

SkillSetu features a dual-layer authentication architecture designed for zero-trust production security while enabling frictionless demonstrator speed.

### Credentials Table

| Role | Persona Name | Demo Email | Demo Password | Primary Route | Role Access Scope |
|---|---|---|---|---|---|
| **Student** | Aarav Sharma / Priya Deshmukh | `student@skillsetu.gov.in` | `Password@123` | `/student` | `/student`, `/student/profile`, `/copilot` |
| **Employee** | Vikram Shinde | `employee@skillsetu.gov.in` | `Password@123` | `/employee/profile` | `/employee/profile`, `/employer`, `/copilot` |
| **Employer** | Tata Motors Skill Lead | `employer@skillsetu.gov.in` | `Password@123` | `/employer` | `/employer`, `/employee/profile`, `/copilot` |
| **Institute** | VJTI Principal / COEP Director | `institute@skillsetu.gov.in` | `Password@123` | `/institute` | `/institute`, `/curriculum`, `/copilot` |
| **Government** | Maharashtra Skill Officer | `government@skillsetu.gov.in` | `Password@123` | `/government` | `/government`, `/government/district/:name`, `/curriculum`, `/copilot` |
| **Admin** | SkillSetu System Administrator | `admin@skillsetu.gov.in` | `AdminPass@2026` | `/admin` | **Omni-Role Access** (All routes and dashboards) |

> [!IMPORTANT]
> **Production vs Local Instance Login Notes:**
> - **On Local / Development Instances (`localhost:5173`)**: The `/login` page includes 1-click **Quick Demo Role Sign-In buttons** that automatically sign into any of the 6 roles instantly.
> - **On Live Production (`skill-setu-rust.vercel.app`)**:
>   - **Admin Account**: `admin@skillsetu.gov.in` / `AdminPass@2026` is pre-provisioned in Supabase GoTrue Auth and has omni-role access to every single protected route (`/admin`, `/government`, `/employer`, `/institute`, `/student`, `/employee/profile`).
>   - **Instant Persona Self-Registration**: In production, the demonstrator can also click **"Create an Account"** on `/login` (`/register`) to register a fresh candidate in any role in under 10 seconds. Registration issues an instant JWT bearer token and redirects straight to that role's dashboard.

---

## 3. Role-by-Role Demonstration Scripts

---

### ROLE 1: STUDENT (P0 — MUST SHOW)

- **Persona**: Aarav Sharma (3rd Year Engineering / Technical Student)
- **Starting URL**: `https://skill-setu-rust.vercel.app/student`
- **Purpose in SIH Story**: Demonstrates how SkillSetu replaces paper resumes with an objective, NSQF-aligned competency radar, diagnoses skill gaps with an interactive quiz, and delivers personalized roadmaps.

#### Navigation Path & Screen Actions:
1. **Skill Passport View** (`/student?tab=passport`):
   - **Show**: The **PassportRadar** chart displaying 6 competency axes (AI, Programming, Systems, Diagnostics, Cloud, Data).
   - **Show**: The **Career Pathway Sequence** banner displaying verified NSQF competency level and the active district (Pune).
   - **Action**: Click on any skill chip (e.g., `Python` or `Machine Learning`) to trigger the **Skill Explainability Modal**, demonstrating transparent curriculum provenance.
2. **Diagnostic Assessment Quiz** (`/student?tab=assessment`):
   - **Show**: Step 1 (Demographics) &rarr; Click **"Next: Career Goal & Interests"**.
   - **Show**: Step 2 (Target Role: AI Engineer / EV Diagnostics) &rarr; Click **"Next: Current Skills"**.
   - **Show**: Step 3 (Skills Inventory) &rarr; Click **"Next: Diagnostic Quiz"**.
   - **Action**: In Step 4 (Diagnostic Aptitude Quiz), select answer options (e.g., option A for questions) and click **"Submit & Calculate Readiness Report"**.
   - **Result**: Step 5 loads instantly with the candidate's readiness score (e.g., 78%), target role fit, and prioritized bridging needs.
3. **Career Recommendations & Job Matching** (`/student?tab=recommendations`):
   - **Show**: Filtered list of verified employer openings matched directly to the candidate's assessed skill scores.
4. **Learning Roadmap** (`/student?tab=roadmap`):
   - **Show**: Adaptive step-by-step milestones bridging identified gaps with accredited Maharashtra courses (COEP, VJTI, Government Polytechnic).
5. **Government Opportunities & Schemes** (`/student?tab=signals`):
   - **Show**: Live feed of state apprenticeships, PMKVY, and Mahaswayam vocational drives.
6. **Career Copilot** (`/student/copilot`):
   - **Action**: Ask: *"What skills do I need to reach NSQF Level 7 in Pune's EV sector?"*
   - **Result**: Grounded response drawing from the student's passport and current district demands.

#### Talking Points:
- *"Notice that this passport is dynamically calculated, not a self-reported bulleted list."*
- *"Every skill gap links directly to an accredited state institute course, closing the loop between assessment and employment."*

#### What NOT to Click:
- Do NOT click "Retake Quiz" repeatedly during evaluation; let the Step 5 readiness animation complete smoothly.

#### Failure Recovery:
- If passport data shows empty: Click the candidate dropdown and select `My Profile (Live Profile)` or hard refresh. Fallback cache is automatically loaded.

---

### ROLE 2: EMPLOYEE (P1 — SHOW IF TIME)

- **Persona**: Vikram Shinde (Mid-Career Professional, 3+ Years Experience in Legacy IT)
- **Starting URL**: `https://skill-setu-rust.vercel.app/employee/profile`
- **Purpose in SIH Story**: Solves industry workforce disruption by helping working professionals transition into high-growth AI and EV roles without restarting their careers.

#### Navigation Path & Screen Actions:
1. **Employee Profile Overview**:
   - **Show**: Current Role: *Software Developer*, Experience: *3.5 Years*, Target Role: *AI / Data Engineer*.
   - **Show**: Verified Certifications & NSQF Skill Badges.
2. **Transition Intelligence Matrix**:
   - **Show**: Skill Adjacency Delta Score (e.g., 68% transferable skills from Python/SQL to Machine Learning).
   - **Show**: Time-to-competence estimate (e.g., *8–12 weeks part-time reskilling*).
3. **Industry Signals & Emerging Demands**:
   - **Show**: Emerging demand surges in Chhatrapati Sambhajinagar and Pune industrial clusters.
4. **Reskilling Course Recommendations**:
   - **Show**: Evening/weekend executive certification modules at VJTI Mumbai and COEP Pune.

#### Talking Points:
- *"SkillSetu prevents technological unemployment by mapping adjacent skills rather than requiring workers to start from zero."*

#### What NOT to Click:
- Do NOT click "Remove All Skills"; keep at least 2 existing skills populated so the transition delta matrix renders properly.

---

### ROLE 3: EMPLOYER (P0 — MUST SHOW)

- **Persona**: Tata Motors Skill Lead / Enterprise Hiring Partner
- **Starting URL**: `https://skill-setu-rust.vercel.app/employer`
- **Purpose in SIH Story**: Reverses the traditional hiring disconnect. Employers publish verified future skill demands into the platform, directly informing university curriculums and student assessments.

#### Navigation Path & Screen Actions:
1. **Hiring Demand Hub** (`activeTab='demand'`):
   - **Show**: Existing verified demands (e.g., *EV Powertrain Diagnostics*, *Battery Management Systems*).
   - **Action**: Click **"Submit Hiring Demand"**.
   - **Fill**: Company: *Mahindra EV Mobility*, Role: *Battery Systems Diagnostics Engineer*, District: *Pune*, Volume: *25*.
   - **Add Skill Chips**: Click preset chips like `EV Battery Technology` and `BMS`.
   - **Action**: Click **"Submit Demand"**.
   - **Result**: Immediate inclusion in the demand queue with state verification status.
2. **GSTIN Enterprise Validation**:
   - **Show**: Verified corporate badge linking employer demand to active corporate registrations.
3. **Candidate Readiness Pool** (`activeTab='validation'`):
   - **Show**: Live pool of assessed students who meet >=70% of the required skills in the selected district.
4. **Difficult-to-Hire Analysis** (`activeTab='difficult'`):
   - **Show**: Regional talent shortages (e.g., high-voltage safety specialists in Pune).

#### Talking Points:
- *"Instead of waiting for universities to update syllabi every four years, employers push live demand directly into the state training engine."*

#### What NOT to Click:
- Do NOT submit a demand with zero skills; always include at least one skill chip.

---

### ROLE 4: INSTITUTE (P1 — SHOW IF TIME)

- **Persona**: VJTI Principal / COEP Vocational Training Director
- **Starting URL**: `https://skill-setu-rust.vercel.app/institute` & `/curriculum`
- **Purpose in SIH Story**: Equips educational institutes and ITIs with syllabus modernization intelligence, ensuring course capacity matches market demand.

#### Navigation Path & Screen Actions:
1. **Institute Course Catalog** (`/institute`):
   - **Show**: Catalog of technical and vocational courses across districts.
   - **Show**: NSQF Level badges (Level 4 through 8) and capacity vs placement ratios (e.g., 60 enrolled / 48 placed).
2. **Curriculum Modernization Hub** (`/curriculum`):
   - **Show**: The Curriculum Audit Scorecard.
   - **Show**: Outdated syllabus modules highlighted in red (e.g., legacy manual testing) vs emerging industry requirements in green (e.g., CI/CD, Containerization).
   - **Action**: Click **"Modernization Audit"** to view AI-assisted syllabus enhancement recommendations.

#### Talking Points:
- *"Institutes can now audit syllabus relevance against real hiring signals before commencing new academic batches."*

---

### ROLE 5: GOVERNMENT (P0 — MUST SHOW)

- **Persona**: Maharashtra State Skill Development Officer
- **Starting URL**: `https://skill-setu-rust.vercel.app/government`
- **Purpose in SIH Story**: The macro policy cockpit. Enables administrators to track state-wide labor intelligence, inspect district-level skill plans, and simulate the economic impact of training policies.

#### Navigation Path & Screen Actions:
1. **Labour Market Intelligence Cockpit**:
   - **Show**: State-level KPIs (Total jobs indexed, active candidate assessments, average placement readiness).
2. **Interactive Maharashtra District Map**:
   - **Show**: SVG map of Maharashtra districts colored by demand intensity.
   - **Action**: Hover over and click **Pune** (or Mumbai / Nagpur).
3. **District Training Plan View** (`/government/district/Pune`):
   - **Show**: Pune district breakdown &rarr; EV Automotive vs IT Services demand.
   - **Show**: Sector seat distribution, training center capacity, and deficit areas.
4. **Policy What-If Simulator**:
   - **Show**: The Policy Simulation Slider (e.g., *Increase EV Stipend Subsidy by 15%*).
   - **Action**: Slide the incentive controller.
   - **Result**: Real-time projected uptick in student enrollment (+18%) and projected enterprise hiring uptake (+12%).

#### Talking Points:
- *"This simulator gives government policymakers predictive intelligence before allocating crores in public skill development budgets."*

#### What NOT to Click:
- Do NOT click outside the district boundaries on the SVG map; click directly on named district tiles.

---

### ROLE 6: ADMINISTRATOR (P2 — BACKUP & AUDIT PROOF)

- **Persona**: SkillSetu System Administrator
- **Starting URL**: `https://skill-setu-rust.vercel.app/admin`
- **Purpose in SIH Story**: Proves data governance, provenance integrity, and operational security to the judging panel.

#### Navigation Path & Screen Actions:
1. **Data Governance Overview** (`/admin?tab=overview`):
   - **Show**: 2,786 authoritative records loaded in-memory across 11 Maharashtra districts.
   - **Show**: Real Data Mode verification (`demo_mode: false`).
2. **Assessment Management & Provenance Audit** (`/admin?tab=students`):
   - **Show**: Provenance tags clearly separating `USER_SUBMITTED` first-party data from synthetic baselines.
   - **Action**: Click **"Inspect"** on any student record to view the raw assessment schema and verification timestamps.
3. **Employer Demand Governance** (`/admin?tab=employers`):
   - **Show**: State approval workflow for incoming enterprise hiring demands.

#### Talking Points:
- *"SkillSetu maintains strict provenance separation. Evaluators can see exactly which data points are authentic user submissions versus verified baselines."*

---

## 4. Priority Ranking & Timing Guide

### Priority Matrix
- **P0 (MUST SHOW — Core Winning Path)**:
  1. **Government**: Macro view, Maharashtra Map, Pune District Plan, Policy Simulator (1.5 mins)
  2. **Employer**: Hiring Demand Submission, GSTIN check, Talent Matching (1.5 mins)
  3. **Student**: Skill Passport Radar, Interactive Quiz, Adaptive Roadmap (2.5 mins)
- **P1 (SHOW IF TIME — High-Impact Differentiators)**:
  4. **Institute / Curriculum Hub**: Syllabus modernization audit (1 min)
  5. **Employee**: Career Transition Intelligence and adjacency matrix (1 min)
- **P2 (BACKUP / Q&A ASSURANCE)**:
  6. **Admin**: Data Governance, Provenance Audit, RBAC boundary inspection
  7. **Copilot**: Conversational grounded Q&A

---

## 5. Live Demonstration Failure Recovery Runbook

| Scenario | Symptom | Immediate Demonstrator Action | Fallback Behavior |
|---|---|---|---|
| **Render Cold Start** | Initial page load spinner spins >5 seconds. | Before demo starts, run `python scripts/warmup.py`. If cold during demo, casually explain: *"The cloud container is spinning up dedicated compute for our demonstration."* | Container initializes in 15–25s. All requests queue and resolve cleanly. |
| **Gemini AI Rate-Limited / Offline** | Copilot response takes >4s or Gemini API key quota exhausted. | The system automatically falls back to the **Deterministic Recommendation Engine**. | Instant, grounded rule-based career pathway response is served seamlessly. |
| **Browser Cache Stale** | UI looks like an old build or button does not fire. | Press `Ctrl + Shift + R` (Windows) or `Cmd + Shift + R` (Mac) to hard-reload. | Fresh static bundle fetched from Vercel edge CDN. |
| **Authentication Session Expired** | 401 Unauthorized or redirect to `/login`. | On `/login`, click the desired role quick-fill button or sign in as Admin (`admin@skillsetu.gov.in` / `AdminPass@2026`). | Instant new JWT token generated and stored in `localStorage`. |
| **Vercel API Rewrite Glitch** | Error alert: "Failed to connect to API backend". | Check internet connectivity. If proxy is temporarily blocked by conference WiFi, switch demonstrator hotspot. | Direct backend URL (`skill-setu-backend-jklo.onrender.com/api/health`) remains live. |
| **Accidental Bad Input in Quiz** | Form displays validation error. | Click "Previous Step" or click "Diagnostic Assessment" tab header to reset form fields to clean defaults. | Clean state restored without reloading the page. |

---

## 6. Security Assurance & Data Privacy Notice

To maintain strict compliance with cybersecurity and hackathon integrity guidelines:
1. **No Sensitive Production Secrets**: No real API keys, cloud master passwords, or private database connection strings are recorded in this guide or exposed in the client UI.
2. **Demo Password Hygiene**: All demo credentials listed (`Password@123`, `AdminPass@2026`) are designated for pre-seeded demonstration and sandboxed evaluation purposes.
3. **Data Provenance**: Real user records are isolated and protected by Supabase Row-Level Security (RLS) policies.
