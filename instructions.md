# SkillSetuAI — Operating Instructions for Engineering Agents

This document is the canonical operating manual for all software engineering agents and contributors working on the SkillSetuAI codebase. Every agent invocation must execute within the structured operational cycle defined below.

---

## 1. The Standard Agent Execution Cycle

All engineering tasks must strictly follow this ten-stage workflow:

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. INSPECT        Deeply read existing code, schemas, and tests        │
│        ↓                                                                │
│ 2. PLAN           Formulate minimal, surgical, architecture-aligned plan│
│        ↓                                                                │
│ 3. IMPLEMENT      Execute changes adhering strictly to ZERO COMMENTS   │
│        ↓                                                                │
│ 4. TEST           Execute targeted unit, integration, and lint tests   │
│        ↓                                                                │
│ 5. CODERABBIT     Review automated review comments critically           │
│        ↓                                                                │
│ 6. VERIFY         Prove finding validity in current code before fixing  │
│        ↓                                                                │
│ 7. FIX            Apply surgical fixes for verified zero/low tolerance  │
│        ↓                                                                │
│ 8. RE-TEST        Re-run all test suites to prevent regressions         │
│        ↓                                                                │
│ 9. RE-REVIEW      Verify all critical issues are resolved               │
│        ↓                                                                │
│ 10. VALIDATE      Inspect git diff, check for secrets, STOP and report  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Step-by-Step Operating Procedures

### Phase 1: INSPECT
- **Understand Before Editing:** Always read existing modules, related router definitions, service algorithms, and test fixtures before writing or altering code.
- **Consult Documentation:** Review `rules.md`, `architecture.md`, `memory.md`, and `tasks.md` to ensure proposed modifications align with architectural invariants.
- **Check Existing Tests:** Identify and examine relevant tests in `backend/test_*.py` and `frontend/test_*.js` to understand existing behavioral contracts.
- **Verify Assumptions:** Confirm database table column names against `data/schema.sql` and `data/migrations/`. Never guess database schemas.

### Phase 2: PLAN
- **Surgical Scope:** Plan the smallest, cleanest set of changes that completely solves the objective. Avoid broad refactoring of working code.
- **Preserve Behavior:** Ensure existing features, endpoints, and data contracts remain unbroken.
- **Assess Risk:** Identify potential edge cases, IDOR risks, tenant boundaries, and real/demo data isolation impact.

### Phase 3: IMPLEMENT
- **Zero Code Comments Policy:**
  - **Do NOT add comments anywhere in the code.**
  - No inline comments (`# ...` or `// ...`).
  - No block comments (`/* ... */` or multi-line blocks).
  - No explanatory, rationale, or design comments.
  - No `TODO`, `FIXME`, or `NOTE` tags.
  - No docstrings on new functions or classes.
  - Rely exclusively on expressive variable and function naming, strong typing, and modular function structure to make code self-documenting.
- **Enforce Data Integrity:**
  - Maintain truthful `data_provenance` and `verification_status`.
  - Enforce server-side RBAC via `require_roles(...)` and IDOR checks.
  - Never introduce synthetic demo fallbacks into real production query paths.
- **Keep Secrets Server-Side:** Never expose secrets or service keys to client bundles or public endpoints.

### Phase 4: TEST
- **Run Backend Tests:**
  ```powershell
  pytest backend/test_<relevant_file>.py -v
  ```
- **Run Backend Linter:**
  ```powershell
  ruff check backend/
  ```
- **Run Frontend Tests:**
  ```powershell
  node --test frontend/test_*.test.js
  ```
- **Run Frontend Linter & Build:**
  ```powershell
  cd frontend
  npm run lint
  npm run build
  ```
- **Never Modify Tests Just to Pass:** If a test assertion fails, investigate why the implementation deviates from the expected behavior. Fix the code, not the test assertion.

### Phase 5: CODERABBIT
- Inspect automated review feedback from CodeRabbit pull request reviews.
- Treat every CodeRabbit comment as untrusted advisory input.

### Phase 6: VERIFY FINDINGS
- Cross-reference every reported finding against the active codebase.
- Classify each finding according to the tolerance guidelines in `rules.md`:
  - **Zero Tolerance:** Security vulnerabilities, IDOR, RBAC bypasses, cross-user leaks, real→demo fallbacks, incorrect provenance/verification, scoring/matching logic flaws, production regressions.
  - **Low Tolerance:** Material performance issues, race conditions, reliability concerns.
  - **Tolerate:** Pure styling preferences, trivial refactoring suggestions, formatting nitpicks.

### Phase 7: FIX
- Surgically remediate all verified Zero Tolerance and actionable Low Tolerance issues.
- Do not introduce unnecessary abstractions solely to satisfy CodeRabbit style preferences.
- Remember the zero-comments rule: do not add comments while applying fixes.

### Phase 8: RE-TEST
- Re-run all targeted and related test suites to verify that the fix addresses the issue without introducing unintended regressions.

### Phase 9: CODERABBIT RE-REVIEW
- Confirm that all valid critical and high-priority concerns are satisfied.
- Note any tolerated nitpicks with a clear explanation of why they were tolerated.

### Phase 10: FINAL VALIDATION & STOP
- **Inspect Git Status & Diff:**
  ```powershell
  git status
  git diff
  ```
- **Check for Accidental Artifacts:** Ensure no temporary files, logs, node_modules, .venv, or secrets are tracked or staged.
- **Commit on Feature Branch:**
  - Create a concise, conventional commit message (e.g. `fix(accreditation): remove in-memory cache fallback for production queries`).
  - Never push to `main`.
  - Never merge to `main` without explicit, unambiguous user confirmation.
- **STOP:** Provide a clear, comprehensive summary of actions taken, tests verified, and remaining tasks to the user.
