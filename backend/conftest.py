"""Pytest configuration and Supabase test doubles for SkillSetu backend test suites."""
from __future__ import annotations

import os
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-dedicated-for-pytest-conftest-environment")
os.environ.setdefault("DEMO_AUTH_ENABLED", "true")

import json
from copy import deepcopy
from pathlib import Path
from typing import Any
import pytest

from app.config import settings
if not settings.jwt_secret_key:
    settings.jwt_secret_key = "test-secret-key-dedicated-for-pytest-conftest-environment"
settings.demo_auth_enabled = True

from app.repositories.supabase_repository import set_supabase_client, reset_supabase_client


class MockSupabaseQuery:
    def __init__(self, table: MockSupabaseTable):
        self.table = table
        self.filters: list[tuple[str, Any]] = []
        self._in_filters: list[tuple[str, list[Any]]] = []
        self._ilike_filters: list[tuple[str, str]] = []
        self._action = "select"
        self._mutation_data: Any | None = None

    def select(self, columns="*"):
        self._action = "select"
        return self

    def update(self, updates: dict):
        self._action = "update"
        self._mutation_data = updates
        return self

    def insert(self, data: Any, *args: Any, **kwargs: Any):
        self._action = "insert"
        self._mutation_data = data
        return self

    def upsert(self, data: Any, *args: Any, **kwargs: Any):
        self._action = "upsert"
        self._mutation_data = data
        self._on_conflict = kwargs.get("on_conflict")
        return self

    def delete(self):
        self._action = "delete"
        return self

    def eq(self, column: str, value: Any):
        self.filters.append((column, value))
        return self

    def in_(self, column: str, values: list[Any]):
        self._in_filters.append((column, list(values)))
        return self

    def ilike(self, column: str, pattern: str):
        self._ilike_filters.append((column, pattern))
        return self

    def range(self, start: int, end: int):
        self._range = (start, end)
        return self

    def limit(self, count: int):
        self._limit = count
        return self

    def order(self, column: str, desc: bool = False):
        self._order_by = (column, desc)
        return self

    def execute(self):
        import re

        if (
            self.table.should_fail
            or (self._action == "update" and self.table.should_fail_update)
            or (self._action == "select" and self.table.should_fail_select)
            or (self._action in ("insert", "upsert") and self.table.should_fail_insert)
            or (self._action == "delete" and self.table.should_fail_delete)
        ):
            raise RuntimeError("Simulated Supabase PostgreSQL database connection error")

        def matches_filters(row: dict) -> bool:
            for col, val in self.filters:
                if str(row.get(col, "")).lower() != str(val).lower():
                    return False
            for col, vals in getattr(self, "_in_filters", []):
                if row.get(col) not in vals:
                    return False
            for col, pattern in getattr(self, "_ilike_filters", []):
                val = str(row.get(col, "")).lower()
                raw_pat = pattern.lower().replace(r"\%", "\x00").replace(r"\_", "\x01")
                escaped = re.escape(raw_pat)
                pat = "^" + escaped.replace("%", ".*").replace("_", ".").replace("\x00", "%").replace("\x01", "_") + "$"
                if not re.search(pat, val):
                    return False
            return True

        if self._action in ("insert", "upsert"):
            items = [self._mutation_data] if isinstance(self._mutation_data, dict) else list(self._mutation_data)
            result_rows = []
            on_conflict_cols = [c.strip() for c in (getattr(self, "_on_conflict", None) or "").split(",") if c.strip()]
            for item in items:
                idx = None
                if on_conflict_cols:
                    idx = next(
                        (
                            i
                            for i, r in enumerate(self.table.rows)
                            if all(
                                item.get(c) is not None
                                and r.get(c) is not None
                                and r.get(c) == item.get(c)
                                for c in on_conflict_cols
                            )
                        ),
                        None,
                    )
                if idx is None and not on_conflict_cols:
                    item_id = item.get("id")
                    idx = next((i for i, r in enumerate(self.table.rows) if item_id and r.get("id") == item_id), None)
                if idx is None and not on_conflict_cols:
                    uid = item.get("user_id")
                    idx = next((i for i, r in enumerate(self.table.rows) if uid and r.get("user_id") == uid), None)
                if idx is not None:
                    self.table.rows[idx].update(deepcopy(item))
                    result_rows.append(deepcopy(self.table.rows[idx]))
                else:
                    new_row = deepcopy(item)
                    self.table.rows.append(new_row)
                    result_rows.append(new_row)
            return type("APIResponse", (), {"data": result_rows, "count": len(result_rows)})()

        if self._action == "delete":
            deleted_rows = []
            surviving_rows = []
            for row in self.table.rows:
                if matches_filters(row):
                    deleted_rows.append(row)
                else:
                    surviving_rows.append(row)
            self.table.rows = surviving_rows
            return type("APIResponse", (), {"data": deepcopy(deleted_rows), "count": len(deleted_rows)})()

        # Filter matching rows for select & update
        matching_rows = []
        matching_indices = []
        for idx, row in enumerate(self.table.rows):
            if matches_filters(row):
                matching_rows.append(row)
                matching_indices.append(idx)

        if self._action == "select":
            selected_rows = deepcopy(matching_rows)
            if hasattr(self, "_order_by") and self._order_by:
                col, desc = self._order_by
                selected_rows.sort(key=lambda r: str(r.get(col, "")), reverse=desc)
            if hasattr(self, "_range") and self._range is not None:
                start, end = self._range
                selected_rows = selected_rows[start : end + 1]
            elif hasattr(self, "_limit") and self._limit is not None:
                selected_rows = selected_rows[: self._limit]
            return type("APIResponse", (), {"data": selected_rows, "count": len(selected_rows)})()
        elif self._action == "update":
            updated_rows = []
            for idx in matching_indices:
                row = self.table.rows[idx]
                row.update(deepcopy(self._mutation_data))
                updated_rows.append(deepcopy(row))
            return type("APIResponse", (), {"data": updated_rows, "count": len(updated_rows)})()

        return type("APIResponse", (), {"data": [], "count": 0})()


class MockSupabaseTable:
    def __init__(self, initial_rows=None):
        self.rows: list[dict[str, Any]] = deepcopy(initial_rows) if initial_rows else []
        self.should_fail = False
        self.should_fail_update = False
        self.should_fail_select = False
        self.should_fail_insert = False
        self.should_fail_delete = False

    def select(self, columns="*"):
        return MockSupabaseQuery(self).select(columns)

    def update(self, updates: dict):
        return MockSupabaseQuery(self).update(updates)

    def insert(self, data: Any, *args: Any, **kwargs: Any):
        return MockSupabaseQuery(self).insert(data, *args, **kwargs)

    def upsert(self, data: Any, *args: Any, **kwargs: Any):
        return MockSupabaseQuery(self).upsert(data, *args, **kwargs)

    def delete(self):
        return MockSupabaseQuery(self).delete()


class MockSupabaseClient:
    def __init__(
        self,
        feedback_rows=None,
        demands_rows=None,
        profiles_rows=None,
        employee_profiles_rows=None,
        student_roadmaps_rows=None,
        assessments_rows=None,
        courses_rows=None,
        industry_signals_rows=None,
        skill_forecasts_rows=None,
        schemes_rows=None,
        gov_opportunities_rows=None,
        skills_rows=None,
        job_skills_rows=None,
        course_skills_rows=None,
        placements_rows=None,
        jobs_rows=None,
        sync_logs_rows=None,
        employers_rows=None,
        users_rows=None,
        difficult_skills_rows=None,
    ):
        self.tables = {
            "employer_feedback": MockSupabaseTable(feedback_rows),
            "employer_demands": MockSupabaseTable(demands_rows),
            "student_profiles": MockSupabaseTable(profiles_rows),
            "employee_profiles": MockSupabaseTable(employee_profiles_rows),
            "student_roadmaps": MockSupabaseTable(student_roadmaps_rows),
            "student_assessments": MockSupabaseTable(assessments_rows),
            "courses": MockSupabaseTable(courses_rows),
            "industry_signals": MockSupabaseTable(industry_signals_rows),
            "skill_forecasts": MockSupabaseTable(skill_forecasts_rows),
            "schemes": MockSupabaseTable(schemes_rows),
            "gov_opportunities": MockSupabaseTable(gov_opportunities_rows),
            "skills": MockSupabaseTable(skills_rows),
            "job_skills": MockSupabaseTable(job_skills_rows),
            "course_skills": MockSupabaseTable(course_skills_rows),
            "placements": MockSupabaseTable(placements_rows),
            "jobs": MockSupabaseTable(jobs_rows),
            "sync_logs": MockSupabaseTable(sync_logs_rows),
            "employers": MockSupabaseTable(employers_rows),
            "users": MockSupabaseTable(users_rows),
            "difficult_skills": MockSupabaseTable(difficult_skills_rows),
        }

    def table(self, table_name: str) -> MockSupabaseTable:
        if table_name not in self.tables:
            self.tables[table_name] = MockSupabaseTable([])
        return self.tables[table_name]

    def rpc(self, fn_name: str, params: dict | None = None) -> MockSupabaseRpc:
        return MockSupabaseRpc(self, fn_name, params)


class MockSupabaseRpc:
    def __init__(self, client: MockSupabaseClient, fn_name: str, params: dict | None = None):
        self.client = client
        self.fn_name = fn_name
        self.params = params or {}

    def execute(self):
        if self.fn_name == "sync_student_profile_atomic":
            p_profile = self.params.get("p_profile") or {}
            uid = p_profile.get("user_id")
            if not uid:
                raise RuntimeError("user_id is required in profile payload")

            if "skill_match_pct" in p_profile:
                smp = p_profile["skill_match_pct"]
                if smp is None or not isinstance(smp, (int, float, str)):
                    raise RuntimeError(f"Invalid skill_match_pct: {smp}")
                try:
                    smp_int = int(smp)
                    if smp_int < 0 or smp_int > 100 or str(smp_int) != str(smp).strip():
                        raise ValueError()
                except Exception:
                    raise RuntimeError(f"Invalid skill_match_pct: {smp}")

            prof_table = self.client.table("student_profiles")
            skills_table = self.client.table("student_skills")

            prof_snapshot = deepcopy(prof_table.rows)
            skills_snapshot = deepcopy(skills_table.rows)

            try:
                existing_prof = next((r for r in prof_table.rows if r.get("user_id") == uid), None)
                payload_to_upsert = deepcopy(p_profile)
                if existing_prof is None and "skill_match_pct" not in payload_to_upsert:
                    payload_to_upsert["skill_match_pct"] = 0
                elif "skill_match_pct" in payload_to_upsert:
                    payload_to_upsert["skill_match_pct"] = int(payload_to_upsert["skill_match_pct"])

                prof_res = prof_table.upsert(payload_to_upsert, on_conflict="user_id").execute()
                saved_prof = prof_res.data[0] if getattr(prof_res, "data", None) else payload_to_upsert

                if "skills" in p_profile and isinstance(p_profile["skills"], list):
                    req_skills = p_profile["skills"]
                    for sk in req_skills:
                        if isinstance(sk, dict) and "proficiency" in sk:
                            p_val = str(sk["proficiency"]).strip().lower()
                            if p_val not in ("beginner", "intermediate", "advanced", "expert"):
                                raise RuntimeError(f"Invalid skill proficiency: {sk}")
                    new_skill_ids = set()
                    for sk in req_skills:
                        if isinstance(sk, dict):
                            sid = str(sk.get("skill_id") or sk.get("id") or "").strip()
                            if not sid:
                                s_name = str(sk.get("skill_name") or sk.get("name") or "").strip().lower()
                                if s_name:
                                    for srow in self.client.table("skills").rows:
                                        r_name = str(srow.get("name") or "").strip().lower()
                                        syns = [str(x).strip().lower() for x in (srow.get("synonyms") or [])]
                                        if r_name == s_name or s_name in syns:
                                            sid = str(srow.get("id") or "").strip()
                                            break
                            raw_prof = str(sk.get("proficiency") or "intermediate").strip().lower()
                            prof = raw_prof if raw_prof in ("beginner", "intermediate", "advanced", "expert") else "intermediate"
                            if sid:
                                new_skill_ids.add(sid)
                                skills_table.upsert({
                                    "user_id": uid,
                                    "skill_id": sid,
                                    "proficiency": prof,
                                }, on_conflict="user_id,skill_id").execute()

                    surviving = []
                    for row in skills_table.rows:
                        if row.get("user_id") == uid:
                            row_sid = str(row.get("skill_id") or "").strip()
                            if row_sid and row_sid in new_skill_ids:
                                surviving.append(row)
                        else:
                            surviving.append(row)
                    skills_table.rows = surviving

                return type("APIResponse", (), {"data": deepcopy(saved_prof), "count": 1})()
            except Exception:
                prof_table.rows = prof_snapshot
                skills_table.rows = skills_snapshot
                raise

        return type("APIResponse", (), {"data": None, "count": 0})()


def _load_demo_feedback_rows() -> list[dict]:
    demo_file = Path(__file__).resolve().parent.parent / "data" / "demo" / "employer_feedback.json"
    if demo_file.is_file():
        try:
            return json.loads(demo_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return [
        {"id": "ef-001", "employer_id": "emp-001", "skill_id": "sk-005", "demand_level": "critical", "proficiency_required": "advanced", "status": "pending", "notes": None},
        {"id": "ef-002", "employer_id": "emp-001", "skill_id": "sk-004", "demand_level": "high", "proficiency_required": "intermediate", "status": "confirmed", "notes": "Gen AI skills"},
        {"id": "ef-004", "employer_id": "emp-002", "skill_id": "sk-002", "demand_level": "high", "proficiency_required": "advanced", "status": "confirmed", "notes": None},
    ]


def _load_initial_demands_rows() -> list[dict]:
    rows: list[dict] = []
    base_dir = Path(__file__).resolve().parent.parent / "data"
    demo_file = base_dir / "demo" / "employer_demands.json"
    real_file = base_dir / "real" / "employer_demands.json"

    seen_ids = set()
    for file_path in (real_file, demo_file):
        if file_path.is_file():
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                for d in data:
                    if d.get("id") and d["id"] not in seen_ids:
                        rows.append(d)
                        seen_ids.add(d["id"])
            except Exception:
                pass
    return rows


def _load_initial_student_profiles_rows() -> list[dict]:
    rows: list[dict] = []
    base_dir = Path(__file__).resolve().parent.parent / "data"
    demo_file = base_dir / "demo" / "student_profiles.json"
    real_file = base_dir / "real" / "student_profiles.json"

    seen_ids = set()
    for file_path in (real_file, demo_file):
        if file_path.is_file():
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                for p in data:
                    pid = p.get("user_id") or p.get("id")
                    if pid and pid not in seen_ids:
                        rows.append(p)
                        seen_ids.add(pid)
            except Exception:
                pass
    return rows


def _load_initial_student_assessments_rows() -> list[dict]:
    rows: list[dict] = []
    base_dir = Path(__file__).resolve().parent.parent / "data"
    demo_file = base_dir / "demo" / "student_assessments.json"
    real_file = base_dir / "real" / "student_assessments.json"

    seen_ids = set()
    for file_path in (real_file, demo_file):
        if file_path.is_file():
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                for a in data:
                    aid = a.get("id")
                    if aid and aid not in seen_ids:
                        rows.append(a)
                        seen_ids.add(aid)
            except Exception:
                pass
    return rows


def _load_initial_courses_rows() -> list[dict]:
    rows: list[dict] = []
    base_dir = Path(__file__).resolve().parent.parent / "data"
    demo_file = base_dir / "demo" / "courses.json"
    real_file = base_dir / "real" / "courses.json"

    seen_ids = set()
    for file_path in (real_file, demo_file):
        if file_path.is_file():
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                for c in data:
                    cid = c.get("id")
                    if cid and cid not in seen_ids:
                        rows.append(c)
                        seen_ids.add(cid)
            except Exception:
                pass
    return rows


def _load_initial_industry_signals_rows() -> list[dict]:
    rows: list[dict] = []
    base_dir = Path(__file__).resolve().parent.parent / "data"
    demo_file = base_dir / "demo" / "industry_signals.json"
    real_file = base_dir / "real" / "industry_signals.json"

    seen_ids = set()
    for file_path in (real_file, demo_file):
        if file_path.is_file():
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                for s in data:
                    sid = s.get("id")
                    if sid and sid not in seen_ids:
                        rows.append(s)
                        seen_ids.add(sid)
            except Exception:
                pass
    return rows


def _load_initial_skill_forecasts_rows() -> list[dict]:
    rows: list[dict] = []
    base_dir = Path(__file__).resolve().parent.parent / "data"
    demo_file = base_dir / "demo" / "skill_forecasts.json"
    real_file = base_dir / "real" / "skill_forecasts.json"

    seen_ids = set()
    for file_path in (real_file, demo_file):
        if file_path.is_file():
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                for s in data:
                    sid = s.get("id")
                    if sid and sid not in seen_ids:
                        rows.append(s)
                        seen_ids.add(sid)
            except Exception:
                pass
    return rows


def _load_initial_gov_opportunities_rows() -> list[dict]:
    rows: list[dict] = []
    base_dir = Path(__file__).resolve().parent.parent / "data"
    demo_file = base_dir / "demo" / "gov_opportunities.json"
    real_file = base_dir / "real" / "gov_opportunities.json"

    seen_ids = set()
    for file_path in (real_file, demo_file):
        if file_path.is_file():
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                for o in data:
                    oid = o.get("id")
                    if oid and oid not in seen_ids:
                        rows.append(o)
                        seen_ids.add(oid)
            except Exception:
                pass
    return rows


_PRISTINE_FEEDBACK = deepcopy(_load_demo_feedback_rows())
_PRISTINE_DEMANDS = deepcopy(_load_initial_demands_rows())
_PRISTINE_PROFILES = deepcopy(_load_initial_student_profiles_rows())
_PRISTINE_ASSESSMENTS = deepcopy(_load_initial_student_assessments_rows())
_PRISTINE_COURSES = deepcopy(_load_initial_courses_rows())
_PRISTINE_SIGNALS = deepcopy(_load_initial_industry_signals_rows())
_PRISTINE_FORECASTS = deepcopy(_load_initial_skill_forecasts_rows())
_PRISTINE_GOV_OPPORTUNITIES = deepcopy(_load_initial_gov_opportunities_rows())


_REAL_DISK_DIR = Path(__file__).resolve().parent.parent / "data" / "real"
_REAL_DISK_SNAPSHOT: dict[Path, bytes] = {}
if _REAL_DISK_DIR.is_dir():
    for _f in _REAL_DISK_DIR.glob("*.json"):
        try:
            _REAL_DISK_SNAPSHOT[_f] = _f.read_bytes()
        except Exception:
            pass


def _restore_real_disk_files():
    if _REAL_DISK_DIR.is_dir():
        for _f in _REAL_DISK_DIR.glob("*.json"):
            if _f not in _REAL_DISK_SNAPSHOT:
                try:
                    _f.unlink(missing_ok=True)
                except Exception:
                    pass
    for _f, _content in _REAL_DISK_SNAPSHOT.items():
        try:
            _f.write_bytes(_content)
        except Exception:
            pass


def _build_pristine_cache() -> dict[str, list[dict]]:
    from app.db import _cache, load_demo_data, load_real_data, init_demo_users
    _restore_real_disk_files()
    _cache.clear()
    load_demo_data()
    load_real_data()
    init_demo_users()
    _cache["employer_feedback"] = deepcopy(_PRISTINE_FEEDBACK)
    _cache["employer_demands"] = deepcopy(_PRISTINE_DEMANDS)
    _cache["student_profiles"] = deepcopy(_PRISTINE_PROFILES)
    _cache["student_assessments"] = deepcopy(_PRISTINE_ASSESSMENTS)
    _cache["courses"] = deepcopy(_PRISTINE_COURSES)
    _cache["industry_signals"] = deepcopy(_PRISTINE_SIGNALS)
    _cache["skill_forecasts"] = deepcopy(_PRISTINE_FORECASTS)
    _cache["gov_opportunities"] = deepcopy(_PRISTINE_GOV_OPPORTUNITIES)
    return deepcopy(_cache)


_PRISTINE_CACHE = _build_pristine_cache()


@pytest.fixture(scope="session", autouse=True)
def preserve_real_disk_files():
    _restore_real_disk_files()
    yield
    _restore_real_disk_files()


def ensure_cache_baseline():
    from app.db import _cache, load_demo_data, load_real_data, init_demo_users
    for tbl in ("skills", "jobs", "schemes", "gov_opportunities"):
        if tbl not in _cache or not _cache[tbl]:
            load_demo_data()
            break
    load_real_data()
    init_demo_users()


@pytest.fixture
def enable_demo_mode(monkeypatch):
    monkeypatch.setenv("SKILLSETU_DATA_MODE", "demo")


@pytest.fixture(autouse=True)
def mock_supabase_for_tests():
    ensure_cache_baseline()
    from app.db import _cache

    _cache["employer_feedback"] = deepcopy(_PRISTINE_FEEDBACK)
    _cache["employer_demands"] = deepcopy(_PRISTINE_DEMANDS)
    _cache["student_profiles"] = deepcopy(_PRISTINE_PROFILES)
    _cache["employee_profiles"] = deepcopy(_PRISTINE_CACHE.get("employee_profiles", []))
    _cache["student_roadmaps"] = deepcopy(_PRISTINE_CACHE.get("student_roadmaps", []))
    _cache["student_assessments"] = deepcopy(_PRISTINE_ASSESSMENTS)
    _cache["courses"] = deepcopy(_PRISTINE_COURSES)
    _cache["industry_signals"] = deepcopy(_PRISTINE_SIGNALS)
    _cache["skill_forecasts"] = deepcopy(_PRISTINE_FORECASTS)
    _cache["gov_opportunities"] = deepcopy(_PRISTINE_GOV_OPPORTUNITIES)
    _cache["job_skills"] = deepcopy(_PRISTINE_CACHE.get("job_skills", []))
    _cache["course_skills"] = deepcopy(_PRISTINE_CACHE.get("course_skills", []))

    mock_client = MockSupabaseClient(
        feedback_rows=deepcopy(_PRISTINE_FEEDBACK),
        demands_rows=deepcopy(_PRISTINE_DEMANDS),
        profiles_rows=deepcopy(_PRISTINE_PROFILES),
        employee_profiles_rows=deepcopy(_cache.get("employee_profiles", [])),
        student_roadmaps_rows=deepcopy(_cache.get("student_roadmaps", [])),
        assessments_rows=deepcopy(_PRISTINE_ASSESSMENTS),
        courses_rows=deepcopy(_PRISTINE_COURSES),
        industry_signals_rows=deepcopy(_PRISTINE_SIGNALS),
        skill_forecasts_rows=deepcopy(_PRISTINE_FORECASTS),
        schemes_rows=deepcopy(_cache.get("schemes", [])),
        gov_opportunities_rows=deepcopy(_PRISTINE_GOV_OPPORTUNITIES),
        skills_rows=deepcopy(_cache.get("skills", [])),
        job_skills_rows=deepcopy(_cache.get("job_skills", [])),
        course_skills_rows=deepcopy(_cache.get("course_skills", [])),
        placements_rows=deepcopy(_cache.get("placements", [])),
        jobs_rows=deepcopy(_cache.get("jobs", [])),
        sync_logs_rows=deepcopy(_cache.get("sync_logs", [])),
        employers_rows=deepcopy(_cache.get("employers", [])),
        users_rows=[deepcopy(u) for u in _cache.get("users", []) if not u.get("is_demo")],
        difficult_skills_rows=deepcopy(_cache.get("difficult_skills", [])),
    )
    set_supabase_client(mock_client)
    yield mock_client
    reset_supabase_client()
