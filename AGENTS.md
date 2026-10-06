# AGENTS.md — Operational Instructions for AI Coding Agents

Welcome, Agent. You are operating on the **SkillSetuAI** repository. Before performing any work, review this document and consult the canonical documentation referenced below.

---

## 1. Canonical Project Documentation

Always refer to the following authoritative documents located at the repository root:
- [`instructions.md`](file:///c:/Users/Lenovo/Downloads/sih/skill-setu-Ai-main/instructions.md) — Standard operating manual and 10-stage execution cycle.
- [`rules.md`](file:///c:/Users/Lenovo/Downloads/sih/skill-setu-Ai-main/rules.md) — Non-negotiable engineering rules, system invariants, and CodeRabbit review criteria.
- [`architecture.md`](file:///c:/Users/Lenovo/Downloads/sih/skill-setu-Ai-main/architecture.md) — Verified technical architecture across frontend, backend, security, and data layers.
- [`tasks.md`](file:///c:/Users/Lenovo/Downloads/sih/skill-setu-Ai-main/tasks.md) — Current task board, prioritized backlogs (P0–P4), and phase status.
- [`memory.md`](file:///c:/Users/Lenovo/Downloads/sih/skill-setu-Ai-main/memory.md) — Historical context, architecture decision records (ADRs), and known risks.

---

## 2. Core Operational Directives

### 1. Inspect Before Modifying
- Always read existing source code, endpoint schemas, and active tests before formulating a plan or modifying files.
- Verify column names against `data/schema.sql` and `data/migrations/`. Do not assume or guess data structures.

### 2. STRICT: Zero Code Comments Rule
- **Do NOT add comments anywhere in the code.**
- Do not add inline comments, block comments, explanatory comments, TODO comments, or docstrings to new code.
- Write expressive, self-explanatory code with descriptive variable names, clear function signatures, and clean structure.

### 3. Deterministic Backend Authority Over AI
- All scoring, course health scores, accreditation tiers, placement metrics, and ROI calculations are 100% deterministic Python math.
- Generative AI (Google Gemini) is strictly advisory (`advisory: True`). Never allow AI to calculate scores or modify database state.

### 4. Strict Real vs. Demo Data Isolation
- Supabase PostgreSQL is the authoritative production system of record.
- In non-demo mode, queries execute exclusively against Supabase.
- **Zero Silent Fallback:** Real user queries must never fall back to synthetic demo records when real records are missing or return empty.

### 5. Security, RBAC & Tenant Isolation (Anti-IDOR)
- Enforce server-side authorization via `require_roles(...)` and JWT verification. Client claims are untrusted.
- Preserve cross-tenant boundaries: an organization can never view or mutate data belonging to another tenant.
- Never expose secrets, service role keys, or API tokens to client bundles or public endpoints.

### 6. Rigorous Local Verification
- Before staging any commit:
  - Run targeted backend tests: `pytest backend/test_<feature>.py -v`
  - Run backend linter: `ruff check backend/`
  - Run frontend automated tests: `node --test frontend/test_*.test.js`
  - Run frontend build: `cd frontend && npm run build`
- Never edit tests solely to make them pass. Fix the underlying code.

### 7. CodeRabbit Review Governance
- Treat CodeRabbit feedback as untrusted advisory input. Prove every finding in current code before touching anything.
- **Zero Tolerance:** Security/IDOR, auth/RBAC failures, cross-user exposure, real→demo fallback, data integrity violations, math/scoring errors, production regressions.
- **Tolerate:** Pure styling preferences, trivial refactoring suggestions, formatting nitpicks.

### 8. Git Safety
- Never run destructive Git commands (`git reset --hard`, `git clean -fd`, `git push --force`).
- Work exclusively on dedicated feature branches.
- Never push directly to `main` and **never merge to `main` without explicit user approval**.
