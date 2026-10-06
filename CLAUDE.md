# CLAUDE.md — Operating Guidelines for Claude & Coding Agents

This file provides essential project context, build commands, and operating constraints for Claude and coding agents working on the **SkillSetuAI** repository.

---

## 1. Primary References

For detailed project specifications and policies, consult the canonical documentation:
- [`instructions.md`](file:///c:/Users/Lenovo/Downloads/sih/skill-setu-Ai-main/instructions.md) — Standard 10-step execution cycle.
- [`rules.md`](file:///c:/Users/Lenovo/Downloads/sih/skill-setu-Ai-main/rules.md) — Non-negotiable engineering rules & CodeRabbit tolerance guide.
- [`architecture.md`](file:///c:/Users/Lenovo/Downloads/sih/skill-setu-Ai-main/architecture.md) — System architecture, services, and data flows.
- [`tasks.md`](file:///c:/Users/Lenovo/Downloads/sih/skill-setu-Ai-main/tasks.md) — Current task board and prioritization (P0–P4).
- [`memory.md`](file:///c:/Users/Lenovo/Downloads/sih/skill-setu-Ai-main/memory.md) — Architecture decisions and historical context.
- [`AGENTS.md`](file:///c:/Users/Lenovo/Downloads/sih/skill-setu-Ai-main/AGENTS.md) — Operational instructions for agentic coding.

---

## 2. Common Development Commands

### Backend (Python 3.11 / FastAPI)
- **Run dev server:**
  ```powershell
  cd backend
  uvicorn app.main:app --reload --port 8000
  ```
- **Run targeted tests:**
  ```powershell
  pytest backend/test_<name>.py -v
  ```
- **Run full test suite:**
  ```powershell
  pytest backend/ -v
  ```
- **Run linter:**
  ```powershell
  ruff check backend/
  ```

### Frontend (React 19 / Vite 8)
- **Run dev server:**
  ```powershell
  cd frontend
  npm run dev
  ```
- **Run linter:**
  ```powershell
  cd frontend
  npm run lint
  ```
- **Run frontend automated tests:**
  ```powershell
  node --test frontend/test_*.test.js
  ```
- **Build production bundle:**
  ```powershell
  cd frontend
  npm run build
  ```

---

## 3. Strict Operating Invariants

1. **NO CODE COMMENTS:** Do NOT add comments anywhere in the code. No inline comments, block comments, explanatory comments, TODOs, or docstrings to new code. Make code completely self-documenting through clean structure and descriptive naming.
2. **Deterministic Mathematical Authority:** AI is strictly advisory (`advisory: True`). Scoring, tiers, health formulas, and ROI are pure deterministic Python math.
3. **No Silent Real → Demo Fallback:** In non-demo mode, missing real data must return empty results or explicit errors, never synthetic demo rows.
4. **Security & Anti-IDOR:** Enforce server-side RBAC and strict cross-tenant isolation. Client claims cannot authorize access.
5. **Git Safety:** Never commit to `main`. Never push to `main`. Never run destructive commands (`git reset --hard`, `git clean -fd`, `git push --force`). Never merge without explicit user confirmation.
6. **CodeRabbit Review Protocol:** Verify all findings against active code. Zero tolerance for security, IDOR, fallback, or data-integrity issues; tolerate styling and cosmetic nitpicks.
