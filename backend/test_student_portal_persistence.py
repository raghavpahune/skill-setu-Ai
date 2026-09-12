import sqlite3
import uuid
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.db import save_user, _cache
from app.core.security import create_access_token
from app.repositories import supabase_repository
from app.repositories.supabase_repository import (
    SupabaseRepositoryError,
    get_client,
    get_student_profile,
    upsert_student_profile,
    upsert_skills,
)
from app.routers.profile import resolve_taxonomy_skill_ids


@pytest.fixture
def student_user_and_headers():
    user_id = f"usr-portal-{uuid.uuid4().hex[:8]}"
    save_user({
        "id": user_id,
        "email": f"{user_id}@skillsetu.gov.in",
        "role": "STUDENT",
        "full_name": "Portal Student",
        "name": "Portal Student",
    })
    token = create_access_token({"sub": user_id, "email": f"{user_id}@skillsetu.gov.in", "role": "STUDENT"})
    return user_id, {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_student_headers():
    other_id = f"usr-other-{uuid.uuid4().hex[:8]}"
    save_user({
        "id": other_id,
        "email": f"{other_id}@skillsetu.gov.in",
        "role": "STUDENT",
        "full_name": "Other Student",
        "name": "Other Student",
    })
    token = create_access_token({"sub": other_id, "email": f"{other_id}@skillsetu.gov.in", "role": "STUDENT"})
    return other_id, {"Authorization": f"Bearer {token}"}


def test_student_portal_end_to_end_acceptance_flow(student_user_and_headers):
    user_id, headers = student_user_and_headers
    client_db = get_client()

    ml_uuid = str(uuid.uuid4())
    client_db.table("skills").rows = [r for r in client_db.table("skills").rows if r.get("name") != "Machine Learning"]
    client_db.table("skills").rows.append({
        "id": ml_uuid,
        "name": "Machine Learning",
        "category": "AI/ML",
        "nsqf_level": 7,
        "synonyms": ["ML", "Statistical Learning"],
    })

    payload = {
        "full_name": "Candidate ML",
        "institution": "Pune Engineering College",
        "degree": "B.Tech Computer Science",
        "education_level": "Undergraduate (B.Tech / B.E / B.Sc)",
        "academic_year": "Final Year",
        "graduation_year": 2026,
        "desired_role": "ML Engineer",
        "target_role": "ML Engineer",
        "preferred_location": "Pune",
        "career_interests": ["Machine Learning", "Autonomous Systems"],
        "skills": [
            {"skill_name": "ml", "proficiency": "intermediate"},
            {"skill_name": "CustomNovelSkillXYZ", "proficiency": "beginner"},
        ],
        "projects": [
            {
                "name": "skill set",
                "description": "Adaptive career platform demo",
                "skills": ["Python", "FastAPI"],
                "url": "https://github.com/skillsetu/demo",
            }
        ],
        "certifications": [
            {
                "name": "x",
                "issuer": "Self-Certified / Industry",
                "issue_date": "2026-01-15",
                "url": "https://verify.cert.org/x",
            }
        ],
        "courses": [
            {
                "course_name": "x",
                "provider": "NPTEL",
                "status": "completed",
            }
        ],
        "experience": [
            {
                "company": "x",
                "role": "c",
                "duration": "6 months",
                "description": "Internship work",
            }
        ],
    }

    with TestClient(app) as http_client:
        create_resp = http_client.post("/api/student/profile", json=payload, headers=headers)
        assert create_resp.status_code == 201
        created_data = create_resp.json()
        assert created_data["status"] == "success"
        prof = created_data["profile"]
        assert prof["user_id"] == user_id
        assert len(prof["skills"]) == 2
        assert len(prof["projects"]) == 1
        assert prof["projects"][0]["name"] == "skill set"
        assert len(prof["certifications"]) == 1
        assert prof["certifications"][0]["name"] == "x"
        assert prof["certifications"][0]["issuer"] == "Self-Certified / Industry"
        assert len(prof["courses"]) == 1
        assert prof["courses"][0]["course_name"] == "x"
        assert len(prof["experience"]) == 1
        assert prof["experience"][0]["company"] == "x"
        assert prof["experience"][0]["role"] == "c"

        get_resp = http_client.get("/api/student/profile", headers=headers)
        assert get_resp.status_code == 200
        reloaded = get_resp.json()["profile"]
        assert reloaded["user_id"] == user_id
        assert reloaded["projects"][0]["name"] == "skill set"
        assert reloaded["certifications"][0]["issuer"] == "Self-Certified / Industry"
        assert reloaded["courses"][0]["course_name"] == "x"
        assert reloaded["experience"][0]["company"] == "x"

    prof_rows = [r for r in client_db.table("student_profiles").rows if r.get("user_id") == user_id]
    assert len(prof_rows) == 1
    stored_skills = prof_rows[0].get("skills") or []
    assert len(stored_skills) == 2
    skill_names = {s.get("skill_name") for s in stored_skills}
    assert "ml" in skill_names
    assert "CustomNovelSkillXYZ" in skill_names

    skill_rows = [r for r in client_db.table("student_skills").rows if r.get("user_id") == user_id]
    assert len(skill_rows) == 1
    assert skill_rows[0]["skill_id"] == ml_uuid
    assert skill_rows[0]["proficiency"] == "intermediate"


def test_taxonomy_uuid_resolution_and_deduplication():
    authoritative_uuid = str(uuid.uuid4())
    taxonomy = [
        {
            "id": authoritative_uuid,
            "name": "Machine Learning",
            "category": "AI/ML",
            "synonyms": ["ML", "Statistical Learning"],
        }
    ]
    client_db = get_client()
    client_db.table("skills").rows = [r for r in client_db.table("skills").rows if r.get("name") != "Machine Learning"]
    client_db.table("skills").rows.extend(taxonomy)

    synonym_input = [{"skill_name": "ml", "proficiency": "intermediate"}]
    resolved_syn = resolve_taxonomy_skill_ids(synonym_input)
    assert len(resolved_syn) == 1
    assert resolved_syn[0]["skill_id"] == authoritative_uuid

    canonical_input = [{"skill_name": "Machine Learning", "proficiency": "advanced"}]
    resolved_canon = resolve_taxonomy_skill_ids(canonical_input)
    assert len(resolved_canon) == 1
    assert resolved_canon[0]["skill_id"] == authoritative_uuid

    custom_input = [{"skill_name": "TotallyUniqueCustomCompetency999", "proficiency": "beginner"}]
    resolved_custom = resolve_taxonomy_skill_ids(custom_input)
    assert len(resolved_custom) == 1
    assert resolved_custom[0]["skill_id"] is None


def test_existing_public_skills_uuid_is_never_regenerated():
    existing_uuid = str(uuid.uuid4())
    input_skills = [
        {
            "id": existing_uuid,
            "name": "Quantum Computing",
            "category": "Emerging",
            "nsqf_level": 8,
            "synonyms": ["QC"],
        },
        {
            "id": "sk-legacy-non-uuid",
            "name": "Robotics Process Automation",
            "category": "Automation",
            "nsqf_level": 6,
            "synonyms": ["RPA"],
        }
    ]

    saved = upsert_skills(input_skills)
    quantum_record = next(s for s in saved if s["name"] == "Quantum Computing")
    rpa_record = next(s for s in saved if s["name"] == "Robotics Process Automation")

    assert quantum_record["id"] == existing_uuid
    assert rpa_record["id"] != "sk-legacy-non-uuid"
    assert uuid.UUID(rpa_record["id"]).version == 5

    resaved = upsert_skills([{"name": "Robotics Process Automation", "category": "Automation"}])
    assert resaved[0]["id"] == rpa_record["id"]


def test_direct_fallback_triggers_only_on_rpc_missing(monkeypatch):
    client_mock = get_client()
    user_id = f"usr-fb-{uuid.uuid4().hex[:8]}"

    def failing_rpc_missing(*args, **kwargs):
        class MissingRPC:
            def execute(self):
                raise RuntimeError("PGRST202: Could not find the function public.sync_student_profile_atomic")
        return MissingRPC()

    monkeypatch.setattr(client_mock, "rpc", failing_rpc_missing)

    payload = {
        "user_id": user_id,
        "full_name": "Fallback Candidate",
        "target_role": "Cloud Architect",
        "skills": [{"skill_name": "Linux", "proficiency": "expert"}],
        "is_demo": False,
    }

    saved = upsert_student_profile(payload)
    assert saved["user_id"] == user_id
    assert saved["target_role"] == "Cloud Architect"

    prof_rows = [r for r in client_mock.table("student_profiles").rows if r.get("user_id") == user_id]
    assert len(prof_rows) == 1


def test_direct_fallback_does_not_mask_real_database_constraint_error(monkeypatch):
    client_mock = get_client()
    user_id = f"usr-real-err-{uuid.uuid4().hex[:8]}"

    def failing_rpc_constraint(*args, **kwargs):
        class ConstraintErrorRPC:
            def execute(self):
                raise RuntimeError("new row for relation violates check constraint 'student_profiles_graduation_year_check'")
        return ConstraintErrorRPC()

    monkeypatch.setattr(client_mock, "rpc", failing_rpc_constraint)

    payload = {
        "user_id": user_id,
        "target_role": "Engineer",
        "graduation_year": 1850,
    }

    with pytest.raises(SupabaseRepositoryError) as exc_info:
        upsert_student_profile(payload)

    assert "student_profiles_graduation_year_check" in str(exc_info.value)
    prof_rows = [r for r in client_mock.table("student_profiles").rows if r.get("user_id") == user_id]
    assert len(prof_rows) == 0


def test_direct_fallback_compensating_rollback_on_partial_failure(monkeypatch):
    client_mock = get_client()
    user_id = f"usr-partial-{uuid.uuid4().hex[:8]}"

    def failing_rpc_missing(*args, **kwargs):
        class MissingRPC:
            def execute(self):
                raise RuntimeError("PGRST202: function not found")
        return MissingRPC()

    monkeypatch.setattr(client_mock, "rpc", failing_rpc_missing)

    original_skills_delete = client_mock.table("student_skills").delete

    def failing_skills_delete(*args, **kwargs):
        raise RuntimeError("Disk IO failure writing student_skills relation")

    client_mock.table("student_skills").delete = failing_skills_delete

    payload = {
        "user_id": user_id,
        "full_name": "Partial Student",
        "target_role": "Security Engineer",
        "skills": [{"skill_name": "Cybersecurity", "proficiency": "advanced"}],
    }

    try:
        with pytest.raises(SupabaseRepositoryError) as exc_info:
            upsert_student_profile(payload)
        assert "Disk IO failure" in str(exc_info.value)

        prof_rows = [r for r in client_mock.table("student_profiles").rows if r.get("user_id") == user_id]
        assert len(prof_rows) == 0
    finally:
        client_mock.table("student_skills").delete = original_skills_delete


def test_authorization_protection_against_cross_user_modification(student_user_and_headers, other_student_headers):
    user_id, headers = student_user_and_headers
    _, other_headers = other_student_headers

    with TestClient(app) as http_client:
        save_resp = http_client.post(
            "/api/student/profile",
            json={"target_role": "Owner Role", "desired_role": "Owner Role"},
            headers=headers,
        )
        assert save_resp.status_code == 201

        patch_other = http_client.patch(
            "/api/student/profile",
            json={"target_role": "Attacker Role"},
            headers=other_headers,
        )
        assert patch_other.status_code in (404, 403)

        get_resp = http_client.get("/api/student/profile", headers=headers)
        assert get_resp.json()["profile"]["target_role"] == "Owner Role"


def test_unauthenticated_request_returns_401():
    with TestClient(app) as http_client:
        get_res = http_client.get("/api/student/profile")
        assert get_res.status_code == 401

        post_res = http_client.post("/api/student/profile", json={"target_role": "Any"})
        assert post_res.status_code == 401


def test_assessment_submission_syncs_resolved_skills(student_user_and_headers):
    user_id, headers = student_user_and_headers
    client_db = get_client()

    ai_uuid = str(uuid.uuid4())
    client_db.table("skills").rows = [r for r in client_db.table("skills").rows if r.get("name") != "Artificial Intelligence"]
    client_db.table("skills").rows.append({
        "id": ai_uuid,
        "name": "Artificial Intelligence",
        "category": "AI/ML",
        "synonyms": ["AI"],
    })

    assessment_payload = {
        "name": "Assessment Student",
        "education": "B.Tech",
        "career_goal": "AI Researcher",
        "district": "Pune",
        "current_skills": [
            {"skill_name": "ai", "proficiency": "advanced"},
            {"skill_name": "UnlistedLabSkill", "proficiency": "intermediate"},
        ],
        "interests": ["Robotics"],
    }

    with TestClient(app) as http_client:
        post_res = http_client.post("/api/student/assessment", json=assessment_payload, headers=headers)
        assert post_res.status_code == 200

        prof_res = http_client.get("/api/student/profile", headers=headers)
        assert prof_res.status_code == 200
        prof = prof_res.json()["profile"]
        assert prof["target_role"] == "AI Researcher"
        skill_names = {s.get("skill_name") for s in prof["skills"]}
        assert "ai" in skill_names
        assert "UnlistedLabSkill" in skill_names

    skill_rows = [r for r in client_db.table("student_skills").rows if r.get("user_id") == user_id]
    assert len(skill_rows) == 1
    assert skill_rows[0]["skill_id"] == ai_uuid
    assert skill_rows[0]["proficiency"] == "advanced"


def test_supplementary_sqlite_database_contract_simulation():
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    cursor.execute(
        "CREATE TABLE users (id TEXT PRIMARY KEY, role TEXT NOT NULL);"
    )
    cursor.execute(
        "CREATE TABLE skills (id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL);"
    )
    cursor.execute(
        "CREATE TABLE student_profiles (user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, target_role TEXT NOT NULL, skills_json TEXT NOT NULL);"
    )
    cursor.execute(
        "CREATE TABLE student_skills (user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, skill_id TEXT NOT NULL REFERENCES skills(id) ON DELETE CASCADE, proficiency TEXT CHECK (proficiency IN ('beginner', 'intermediate', 'advanced', 'expert')) NOT NULL, PRIMARY KEY (user_id, skill_id));"
    )
    conn.commit()

    test_uid = "usr-contract-1"
    valid_skill_id = "sk-valid-1"
    invalid_skill_id = "sk-nonexistent-99"

    cursor.execute("INSERT INTO users VALUES (?, ?)", (test_uid, "STUDENT"))
    cursor.execute("INSERT INTO skills VALUES (?, ?)", (valid_skill_id, "Machine Learning"))
    conn.commit()

    cursor.execute(
        "INSERT INTO student_profiles VALUES (?, ?, ?)",
        (test_uid, "ML Engineer", '[{"skill_name": "ml"}, {"skill_name": "custom"}]'),
    )
    cursor.execute(
        "INSERT INTO student_skills VALUES (?, ?, ?)",
        (test_uid, valid_skill_id, "intermediate"),
    )
    conn.commit()

    cursor.execute("SELECT target_role, skills_json FROM student_profiles WHERE user_id = ?", (test_uid,))
    prof_row = cursor.fetchone()
    assert prof_row[0] == "ML Engineer"
    assert "custom" in prof_row[1]

    cursor.execute("SELECT skill_id, proficiency FROM student_skills WHERE user_id = ?", (test_uid,))
    rel_rows = cursor.fetchall()
    assert len(rel_rows) == 1
    assert rel_rows[0][0] == valid_skill_id
    assert rel_rows[0][1] == "intermediate"

    conn.isolation_level = None
    cursor.execute("BEGIN TRANSACTION;")
    cursor.execute("UPDATE student_profiles SET target_role = 'Invalid State' WHERE user_id = ?", (test_uid,))
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute("INSERT INTO student_skills VALUES (?, ?, ?)", (test_uid, invalid_skill_id, "beginner"))
    cursor.execute("ROLLBACK;")

    cursor.execute("SELECT target_role FROM student_profiles WHERE user_id = ?", (test_uid,))
    assert cursor.fetchone()[0] == "ML Engineer"

    conn.close()
