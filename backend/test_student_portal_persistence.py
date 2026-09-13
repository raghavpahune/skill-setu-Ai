from pathlib import Path
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


@pytest.fixture
def admin_user_and_headers():
    admin_id = f"usr-admin-{uuid.uuid4().hex[:8]}"
    save_user({
        "id": admin_id,
        "email": f"{admin_id}@skillsetu.gov.in",
        "role": "ADMIN",
        "full_name": "Portal Admin",
        "name": "Portal Admin",
    })
    token = create_access_token({"sub": admin_id, "email": f"{admin_id}@skillsetu.gov.in", "role": "ADMIN"})
    return admin_id, {"Authorization": f"Bearer {token}"}


def test_student_profile_put_full_flow(student_user_and_headers):
    user_id, headers = student_user_and_headers
    client_db = get_client()

    ml_uuid = str(uuid.uuid4())
    py_uuid = str(uuid.uuid4())
    client_db.table("skills").rows = [
        r for r in client_db.table("skills").rows
        if r.get("name") not in ("Machine Learning", "Python")
    ]
    client_db.table("skills").rows.extend([
        {
            "id": ml_uuid,
            "name": "Machine Learning",
            "category": "AI/ML",
            "nsqf_level": 7,
            "synonyms": ["ML", "Statistical Learning"],
        },
        {
            "id": py_uuid,
            "name": "Python",
            "category": "Programming",
            "nsqf_level": 6,
            "synonyms": ["Python3", "Py"],
        },
    ])

    payload = {
        "full_name": "Full Put Student",
        "institution": "National Institute of Technology",
        "degree": "B.Tech Computer Science and Engineering",
        "education_level": "Undergraduate (B.Tech / B.E / B.Sc)",
        "academic_year": "Final Year",
        "graduation_year": 2026,
        "desired_role": "Machine Learning Engineer",
        "target_role": "Machine Learning Engineer",
        "preferred_location": "Bengaluru",
        "career_interests": ["Deep Learning", "Cloud Computing"],
        "skills": [
            {"skill_name": "Python", "proficiency": "advanced"},
            {"skill_name": "ml", "proficiency": "intermediate"},
            {"skill_name": "ProprietaryFramework99", "proficiency": "beginner"},
        ],
        "projects": [
            {
                "name": "SkillSetu Portal",
                "description": "Production candidate workflow",
                "skills": ["Python", "FastAPI", "React"],
                "url": "https://skillsetu.gov.in/portal",
            }
        ],
        "certifications": [
            {
                "name": "Cloud Practitioner",
                "issuer": "",
                "issue_date": "2026-03-01",
                "url": "https://certs.example.com/123",
            }
        ],
        "courses": [
            {
                "course_name": "Advanced Neural Networks",
                "provider": "Coursera",
                "status": "completed",
            }
        ],
        "experience": [
            {
                "company": "GovTech Labs",
                "role": "Junior Data Intern",
                "duration": "12 months",
                "description": "Engineered analytical pipelines",
            }
        ],
    }

    with TestClient(app) as http_client:
        put_res = http_client.put("/api/student/profile", json=payload, headers=headers)
        assert put_res.status_code == 200
        put_data = put_res.json()
        assert put_data["status"] == "success"
        prof = put_data["profile"]
        assert prof["user_id"] == user_id
        assert prof["full_name"] == "Full Put Student"
        assert len(prof["skills"]) == 3
        assert len(prof["projects"]) == 1
        assert len(prof["certifications"]) == 1
        assert prof["certifications"][0]["issuer"] == "Self-Certified / Industry"
        assert len(prof["courses"]) == 1
        assert len(prof["experience"]) == 1

        get_res = http_client.get("/api/student/profile", headers=headers)
        assert get_res.status_code == 200
        reloaded = get_res.json()["profile"]
        assert reloaded["user_id"] == user_id
        assert reloaded["institution"] == "National Institute of Technology"
        assert reloaded["certifications"][0]["issuer"] == "Self-Certified / Industry"
        assert reloaded["experience"][0]["company"] == "GovTech Labs"

    prof_rows = [r for r in client_db.table("student_profiles").rows if r.get("user_id") == user_id]
    assert len(prof_rows) == 1
    stored_skills = prof_rows[0].get("skills") or []
    assert len(stored_skills) == 3
    skill_names = {s.get("skill_name") for s in stored_skills}
    assert "Python" in skill_names
    assert "ml" in skill_names
    assert "ProprietaryFramework99" in skill_names

    skill_rows = [r for r in client_db.table("student_skills").rows if r.get("user_id") == user_id]
    assert len(skill_rows) == 2
    rel_ids = {r["skill_id"] for r in skill_rows}
    assert py_uuid in rel_ids
    assert ml_uuid in rel_ids


def test_student_profile_experience_endpoint(student_user_and_headers):
    user_id, headers = student_user_and_headers

    with TestClient(app) as http_client:
        init_res = http_client.put(
            "/api/student/profile",
            json={"target_role": "Backend Engineer"},
            headers=headers,
        )
        assert init_res.status_code == 200

        exp_payload = {
            "experience": [
                {
                    "company": "Tech Corp",
                    "role": "Software Engineer",
                    "duration": "2 years",
                    "description": "Backend API development",
                }
            ]
        }
        exp_res = http_client.put("/api/student/profile/experience", json=exp_payload, headers=headers)
        assert exp_res.status_code == 200
        assert len(exp_res.json()["experience"]) == 1

        get_res = http_client.get("/api/student/profile", headers=headers)
        assert get_res.status_code == 200
        prof = get_res.json()["profile"]
        assert len(prof["experience"]) == 1
        assert prof["experience"][0]["company"] == "Tech Corp"


def test_student_profile_cross_user_user_id_query_param(
    student_user_and_headers,
    other_student_headers,
    admin_user_and_headers,
):
    user_a_id, headers_a = student_user_and_headers
    user_b_id, headers_b = other_student_headers
    admin_id, admin_headers = admin_user_and_headers

    with TestClient(app) as http_client:
        create_res = http_client.put(
            "/api/student/profile",
            json={"target_role": "Target Student A", "full_name": "Student A Original"},
            headers=headers_a,
        )
        assert create_res.status_code == 200

        forbidden_get = http_client.get(f"/api/student/profile?user_id={user_a_id}", headers=headers_b)
        assert forbidden_get.status_code == 403

        forbidden_put = http_client.put(
            f"/api/student/profile?user_id={user_a_id}",
            json={"target_role": "Hacked Role"},
            headers=headers_b,
        )
        assert forbidden_put.status_code == 403

        admin_get = http_client.get(f"/api/student/profile?user_id={user_a_id}", headers=admin_headers)
        assert admin_get.status_code == 200
        assert admin_get.json()["profile"]["target_role"] == "Target Student A"

        admin_put = http_client.put(
            f"/api/student/profile?user_id={user_a_id}",
            json={"target_role": "Admin Updated Role", "full_name": "Student A Updated"},
            headers=admin_headers,
        )
        assert admin_put.status_code == 200
        assert admin_put.json()["profile"]["target_role"] == "Admin Updated Role"

        owner_get = http_client.get("/api/student/profile", headers=headers_a)
        assert owner_get.status_code == 200
        assert owner_get.json()["profile"]["target_role"] == "Admin Updated Role"


def test_student_profile_with_fake_uuid_resolves_cleanly(student_user_and_headers):
    user_id, headers = student_user_and_headers
    client_db = get_client()

    authoritative_uuid = str(uuid.uuid4())
    client_db.table("skills").rows = [
        r for r in client_db.table("skills").rows if r.get("name") != "Machine Learning"
    ]
    client_db.table("skills").rows.append({
        "id": authoritative_uuid,
        "name": "Machine Learning",
        "category": "AI/ML",
        "synonyms": ["ML"],
    })

    fake_uuid_1 = "11111111-2222-3333-4444-555555555555"
    fake_uuid_2 = "99999999-8888-7777-6666-555555555555"

    payload = {
        "target_role": "ML Engineer",
        "skills": [
            {
                "skill_id": fake_uuid_1,
                "skill_name": "Machine Learning",
                "proficiency": "advanced",
            },
            {
                "skill_id": fake_uuid_2,
                "skill_name": "TotallyCustomSkillWithFakeUuid",
                "proficiency": "beginner",
            },
        ],
    }

    with TestClient(app) as http_client:
        put_res = http_client.put("/api/student/profile", json=payload, headers=headers)
        assert put_res.status_code == 200
        prof = put_res.json()["profile"]
        assert len(prof["skills"]) == 2

        skills_by_name = {s["skill_name"]: s for s in prof["skills"]}
        assert skills_by_name["Machine Learning"]["skill_id"] == authoritative_uuid
        assert skills_by_name["TotallyCustomSkillWithFakeUuid"]["skill_id"] is None

    skill_rows = [r for r in client_db.table("student_skills").rows if r.get("user_id") == user_id]
    assert len(skill_rows) == 1
    assert skill_rows[0]["skill_id"] == authoritative_uuid
    assert skill_rows[0]["proficiency"] == "advanced"


def test_student_profile_career_interests_persistence_and_round_trip(student_user_and_headers):
    user_id, headers = student_user_and_headers
    client_db = get_client()

    initial_interests = ["Machine Learning", "Autonomous Systems", "Cloud Computing"]
    payload_initial = {
        "full_name": "Career Interest Tester",
        "institution": "Tech Institute",
        "degree": "Computer Science",
        "target_role": "ML Engineer",
        "career_interests": initial_interests,
        "skills": [],
    }

    with TestClient(app) as http_client:
        put_response = http_client.put("/api/student/profile", json=payload_initial, headers=headers)
        assert put_response.status_code == 200
        put_body = put_response.json()
        assert put_body["status"] == "success"
        assert put_body["profile"]["career_interests"] == initial_interests

        get_response = http_client.get("/api/student/profile", headers=headers)
        assert get_response.status_code == 200
        get_body = get_response.json()
        assert get_body["status"] == "success"
        assert get_body["profile"]["career_interests"] == initial_interests

    stored_profiles = [r for r in client_db.table("student_profiles").rows if r.get("user_id") == user_id]
    assert len(stored_profiles) == 1
    assert stored_profiles[0]["career_interests"] == initial_interests

    updated_interests = ["Deep Learning", "Generative AI"]
    payload_update = {
        "career_interests": updated_interests,
    }

    with TestClient(app) as http_client:
        patch_response = http_client.patch("/api/student/profile", json=payload_update, headers=headers)
        assert patch_response.status_code == 200
        patch_body = patch_response.json()
        assert patch_body["status"] == "success"
        assert patch_body["profile"]["career_interests"] == updated_interests

        recheck_response = http_client.get("/api/student/profile", headers=headers)
        assert recheck_response.status_code == 200
        recheck_body = recheck_response.json()
        assert recheck_body["profile"]["career_interests"] == updated_interests

    updated_profiles = [r for r in client_db.table("student_profiles").rows if r.get("user_id") == user_id]
    assert len(updated_profiles) == 1
    assert updated_profiles[0]["career_interests"] == updated_interests


def test_student_profile_missing_columns_migration_and_rpc_contract():
    project_root = Path(__file__).resolve().parent.parent
    migration_file = project_root / "data" / "migrations" / "20260913_add_missing_student_profile_columns.sql"
    assert migration_file.is_file()
    migration_sql = migration_file.read_text(encoding="utf-8")

    expected_column_definitions = [
        "ALTER TABLE public.student_profiles ADD COLUMN IF NOT EXISTS full_name TEXT;",
        "ALTER TABLE public.student_profiles ADD COLUMN IF NOT EXISTS institution TEXT;",
        "ALTER TABLE public.student_profiles ADD COLUMN IF NOT EXISTS degree TEXT;",
        "ALTER TABLE public.student_profiles ADD COLUMN IF NOT EXISTS education_level TEXT;",
        "ALTER TABLE public.student_profiles ADD COLUMN IF NOT EXISTS academic_year TEXT;",
        "ALTER TABLE public.student_profiles ADD COLUMN IF NOT EXISTS graduation_year INT;",
        "ALTER TABLE public.student_profiles ADD COLUMN IF NOT EXISTS desired_role TEXT;",
        "ALTER TABLE public.student_profiles ADD COLUMN IF NOT EXISTS preferred_location TEXT;",
        "ALTER TABLE public.student_profiles ADD COLUMN IF NOT EXISTS career_interests TEXT[] DEFAULT '{}';",
        "ALTER TABLE public.student_profiles ADD COLUMN IF NOT EXISTS skills JSONB DEFAULT '[]'::jsonb;",
        "ALTER TABLE public.student_profiles ADD COLUMN IF NOT EXISTS projects JSONB DEFAULT '[]'::jsonb;",
        "ALTER TABLE public.student_profiles ADD COLUMN IF NOT EXISTS certifications JSONB DEFAULT '[]'::jsonb;",
        "ALTER TABLE public.student_profiles ADD COLUMN IF NOT EXISTS courses JSONB DEFAULT '[]'::jsonb;",
        "ALTER TABLE public.student_profiles ADD COLUMN IF NOT EXISTS experience JSONB DEFAULT '[]'::jsonb;",
        "ALTER TABLE public.student_profiles ADD COLUMN IF NOT EXISTS skill_match_pct INT DEFAULT 0;",
        "ALTER TABLE public.student_profiles ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'USER_SUBMITTED';",
        "ALTER TABLE public.student_profiles ADD COLUMN IF NOT EXISTS is_demo BOOLEAN DEFAULT FALSE;",
        "ALTER TABLE public.student_profiles ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now();",
        "ALTER TABLE public.student_profiles ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();",
    ]

    for col_def in expected_column_definitions:
        assert col_def in migration_sql

    schema_file = project_root / "data" / "schema.sql"
    assert schema_file.is_file()
    schema_sql = schema_file.read_text(encoding="utf-8")
    assert "career_interests TEXT[] DEFAULT '{}'" in schema_sql
    assert "experience JSONB DEFAULT '[]'::jsonb" in schema_sql
    assert "ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS career_interests TEXT[] DEFAULT '{}';" in schema_sql
    assert "ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS experience JSONB DEFAULT '[]'::jsonb;" in schema_sql

    rpc_file = project_root / "data" / "migrations" / "20260912_fix_student_profile_sync_atomic.sql"
    assert rpc_file.is_file()
    rpc_sql = rpc_file.read_text(encoding="utf-8")
    assert "career_interests," in rpc_sql
    assert "experience," in rpc_sql

