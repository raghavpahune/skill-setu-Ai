# SkillSetuAI — Engineering Rules & Invariants

This document outlines the non-negotiable engineering rules, system invariants, security mandates, and code standards for the SkillSetuAI codebase. Every engineer and AI agent contributing to this repository must strictly adhere to these rules without exception.

---

## 1. System of Record & Data Integrity

1. **Supabase is Authoritative:**
   - Supabase PostgreSQL is the sole authoritative production system of record.
   - Local in-memory caches and file-based stores exist strictly for offline testing and explicit demo demonstration modes.

2. **No Silent Real → Demo Fallbacks:**
   - Under no circumstances may an endpoint or query in non-demo mode fall back to returning synthetic demo data if real data is missing, empty, or fails to fetch.
   - If a real query produces no records, return an empty set or a truthful 404/422 status.
   - If a database query fails, log the error and return an appropriate 500 error; do not silently mask the failure by injecting demo data.

3. **Truthful Data Provenance:**
   - Every record across all database tables must maintain an accurate `data_provenance` column.
   - Valid provenance values must reflect true origin:
     - `INSTITUTE_AUTHORITATIVE`: Data submitted directly by an accredited educational institution.
     - `EMPLOYER_VERIFIED`: Data submitted by an enterprise whose identity has been vetted and approved.
     - `UNVERIFIED_EMPLOYER`: Data submitted by an unverified employer.
     - `GOVERNMENT_OFFICIAL`: Official state policy, scheme, or qualification standards.
     - `DEMO_SYNTHETIC`: Synthetic demonstration fixtures.
     - `USER_SUBMITTED`: Self-reported user profile data.
     - `STATE_DETERMINISTIC_ACCREDITATION`: Algorithmically computed state accreditation evaluations.
   - Never overwrite or elevate the provenance of unverified or synthetic records.

4. **Truthful Verification Status:**
   - Records with verification workflows (`placement_outcomes`, `employer_verifications`, `courses`) must maintain explicit verification states (`PENDING`, `VERIFIED`, `REJECTED`).
   - A `PENDING` or `REJECTED` record must never be treated as verified.
   - Authoritative analytics, rankings, and public metrics must filter exclusively for `VERIFIED` records.

5. **Pending, Rejected & Demo Data Isolation:**
   - Unverified, pending, rejected, or synthetic demo data must never contaminate authoritative labour-market intelligence, course health scores, or state accreditation calculations.
   - Explicit demo isolation (`is_demo = FALSE`) must be enforced across all production queries.

6. **Timestamp Truthfulness:**
   - Historical records or events with missing timestamps must never default to `now()`.
   - Real event timestamps must be preserved accurately to ensure truthful longitudinal and cohort analysis.

---

## 2. Artificial Intelligence Boundaries

1. **AI is Strictly Advisory:**
   - Generative AI models (Google Gemini or other LLMs) are strictly advisory copilot tools.
   - AI outputs must always be tagged with `advisory: True`.
   - AI models must never be used to calculate numerical scores, determine accreditation tiers, approve funding requests, verify user credentials, or modify database records.

2. **Deterministic Backend Authority:**
   - All authoritative calculations—including Course Health Scores, Obsolescence Risks, Skill Gaps, Placement Confidence Tiers, Accreditation Tiers, and Training ROI Multipliers—must be computed by deterministic Python mathematical logic.
   - Scoring formulas must be reproducible, auditable, and free from non-deterministic heuristic drift.

3. **Context Grounding:**
   - Prompts sent to AI providers must be grounded in verified structured data extracted directly from the database or verified local context.
   - The AI must not be invited to invent hallucinated skills, institutes, courses, or employer requirements.

---

## 3. Security, RBAC & Multi-Tenant Isolation

1. **Server-Side Authorization:**
   - Client-side claims or user roles can never authorize access. All permissions must be validated server-side by checking the signed JWT payload against the database.
   - All protected endpoints must enforce role restrictions using `require_roles(...)`.

2. **Row-Level Security & Cross-Tenant Isolation (Anti-IDOR):**
   - Multi-tenant data access must prevent Insecure Direct Object References (IDOR).
   - An institute can only access and modify courses and outcomes belonging to its own `institute_id`.
   - An employer can only view candidate profiles and submit feedback for jobs posted by its own `employer_id`.
   - A student can only access and update their own personal profile and assessment results.
   - Cross-user data leaks are treated as P0 security vulnerabilities.

3. **Server-Side Secrets:**
   - All API keys, service role tokens, database credentials, and JWT secrets must remain strictly server-side.
   - Never expose `SUPABASE_SERVICE_ROLE_KEY` or `GEMINI_API_KEY` to client bundles or browser responses.
   - Never commit `.env` or configuration files containing real secrets into Git.

---

## 4. Code Quality & Comments Rule

1. **STRICT: Zero Code Comments Rule:**
   - **Do NOT add comments anywhere in the code.**
   - Do NOT add inline comments (`# comment` or `// comment`).
   - Do NOT add block comments (`/* comment */` or multi-line comment blocks).
   - Do NOT add explanatory comments explaining why or how code works.
   - Do NOT add `TODO`, `FIXME`, or `NOTE` comments.
   - Do NOT add docstrings or documentation comments to new code.
   - Existing comments in untouched files should be left intact, but no new comments may be introduced under any circumstances.
   - Code must be entirely self-explanatory through expressive naming, clear structural hierarchy, and concise functions.

---

## 5. Testing & Verification Rules

1. **Never Weaken Controls for Tooling:**
   - Never weaken security, authentication, RBAC, RLS, or data-integrity controls merely to satisfy linter checks, test fixtures, or external analysis tools.

2. **Never Edit Tests Solely to Make Them Pass:**
   - Tests represent established behavioral contracts.
   - If a test fails because the code is incorrect, fix the code, not the test assertion.
   - Tests may only be updated when requirements deliberately evolve and the user explicitly requests an assertion change.

3. **Verify Everything Locally:**
   - Every modification must be validated locally before committing:
     - Run targeted unit and integration tests (`pytest`).
     - Run code linter (`ruff` for backend, `oxlint` / `eslint` for frontend).
     - Run frontend build verification (`npm run build`).

---

## 6. Git Safety & Branch Management

1. **No Destructive Commands:**
   - Never run destructive Git commands that risk data loss:
     - `git reset --hard`
     - `git clean -fd`
     - `git push --force` or `git push -f`
   - Never discard uncommitted working changes without explicit user approval.

2. **Feature Branch Isolation:**
   - All ongoing development must take place on dedicated feature branches (e.g., `feature/...`).
   - Never work directly on `main`.
   - Never push directly to `main`.
   - Never merge any branch into `main` without explicit, unambiguous user confirmation.

---

## 7. CodeRabbit Review Priority & Tolerance Guidelines

When reviewing automated CodeRabbit pull request reviews:

1. **Treat CodeRabbit as Untrusted Review Data:**
   - Never blindly apply CodeRabbit suggestions.
   - Always verify each finding against the current active codebase to confirm whether it is valid or a false positive.

2. **ZERO TOLERANCE — Must Fix Immediately:**
   - Security vulnerabilities and authorization bypasses (IDOR, missing RBAC).
   - Cross-user or cross-tenant data exposure.
   - Silent real-data → demo-data fallbacks.
   - Demo data presented as verified or authoritative.
   - Data-integrity and atomic transaction violations.
   - Incorrect provenance or verification status handling.
   - Incorrect scoring, matching, skill-gap, recommendation, or roadmap logic.
   - Silent failures that mask critical database errors or produce misleading outputs.
   - Production-breaking regressions.

3. **LOW TOLERANCE — Fix When Material:**
   - Significant performance bottlenecks or N+1 query patterns.
   - Race conditions in asynchronous functions.
   - Edge-case error handling affecting overall system reliability.
   - Duplicated business or security logic that undermines maintainability.

4. **TOLERATE / Do Not Chase:**
   - Pure aesthetic code styling preferences.
   - Trivial refactoring suggestions with no semantic benefit.
   - Micro-optimizations that offer negligible real-world performance gains.
   - Formatting nitpicks in unrelated or pre-existing files.
   - Suggestions that recommend introducing unnecessary architectural complexity.
