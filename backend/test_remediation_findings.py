import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from app.core.time import parse_iso_timestamp, UTC_MIN
from app.services.roadmap_service import _extract_student_skills, _get_target_role
from app.repositories.supabase_repository import get_employee_profile, SupabaseRepositoryError
from app.config import settings


def test_parse_iso_timestamp_z():
    res = parse_iso_timestamp("2026-09-10T12:00:00Z")
    assert res == datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)


def test_parse_iso_timestamp_offset():
    res = parse_iso_timestamp("2026-09-10T12:00:00+05:30")
    assert res.tzinfo is not None


def test_parse_iso_timestamp_naive():
    res = parse_iso_timestamp("2026-09-10T12:00:00")
    assert res == datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)


def test_parse_iso_timestamp_invalid():
    assert parse_iso_timestamp("") == UTC_MIN
    assert parse_iso_timestamp("not-a-timestamp") == UTC_MIN
    assert parse_iso_timestamp(None) == UTC_MIN


def test_roadmap_skills_newer_profile_wins():
    profile = {
        "updated_at": "2026-09-10T12:00:00Z",
        "skills": [
            {"skill_id": "sk-001", "name": "Python", "proficiency": "beginner"},
            {"skill_id": "sk-002", "name": "SQL", "proficiency": "intermediate"},
        ]
    }
    assessment = {
        "updated_at": "2026-09-08T12:00:00Z",
        "current_skills": [
            {"skill_id": "sk-001", "skill_name": "Python", "proficiency": "expert"},
            {"skill_id": "sk-003", "skill_name": "Docker", "proficiency": "advanced"},
        ]
    }

    skills_by_id = {
        "sk-001": {"id": "sk-001", "name": "Python", "category": "Tech", "nsqf_level": 5},
        "sk-002": {"id": "sk-002", "name": "SQL", "category": "Tech", "nsqf_level": 4},
        "sk-003": {"id": "sk-003", "name": "Docker", "category": "DevOps", "nsqf_level": 6},
    }
    skills_by_name = {
        "python": skills_by_id["sk-001"],
        "sql": skills_by_id["sk-002"],
        "docker": skills_by_id["sk-003"],
    }

    skills = _extract_student_skills(profile, assessment, skills_by_id, skills_by_name)
    assert skills["sk-001"]["proficiency"] == "beginner"
    assert skills["sk-002"]["proficiency"] == "intermediate"
    assert skills["sk-003"]["proficiency"] == "advanced"


def test_roadmap_skills_newer_assessment_wins():
    profile = {
        "updated_at": "2026-09-05T12:00:00Z",
        "skills": [
            {"skill_id": "sk-001", "name": "Python", "proficiency": "expert"},
        ]
    }
    assessment = {
        "updated_at": "2026-09-09T12:00:00Z",
        "current_skills": [
            {"skill_id": "sk-001", "skill_name": "Python", "proficiency": "beginner"},
            {"skill_id": "sk-004", "skill_name": "Kubernetes", "proficiency": "intermediate"},
        ]
    }

    skills_by_id = {
        "sk-001": {"id": "sk-001", "name": "Python", "category": "Tech", "nsqf_level": 5},
        "sk-004": {"id": "sk-004", "name": "Kubernetes", "category": "DevOps", "nsqf_level": 7},
    }
    skills_by_name = {
        "python": skills_by_id["sk-001"],
        "kubernetes": skills_by_id["sk-004"],
    }

    skills = _extract_student_skills(profile, assessment, skills_by_id, skills_by_name)
    assert skills["sk-001"]["proficiency"] == "beginner"
    assert skills["sk-004"]["proficiency"] == "intermediate"


def test_roadmap_get_target_role_precedence():
    profile = {
        "updated_at": "2026-09-10T10:00:00Z",
        "target_role": "Data Scientist",
    }
    assessment = {
        "updated_at": "2026-09-09T10:00:00Z",
        "career_goal": "Cloud Architect",
    }
    assert _get_target_role("student_1", None, profile, assessment) == "Data Scientist"

    profile["updated_at"] = "2026-09-08T10:00:00Z"
    assert _get_target_role("student_1", None, profile, assessment) == "Cloud Architect"


def test_get_employee_profile_demo_fallback_on_connection_error():
    with patch("app.repositories.supabase_repository.get_client") as mock_client:
        mock_client.side_effect = Exception("Supabase connection refused")
        with patch.object(settings, "use_demo_data", True):
            with patch("app.db._cache", {"employee_profiles": [{"user_id": "emp-demo-001", "name": "Demo Emp"}]}):
                res = get_employee_profile("emp-demo-001")
                assert res is not None
                assert res["name"] == "Demo Emp"

                with pytest.raises(SupabaseRepositoryError):
                    get_employee_profile("usr-real-prod-999")


def test_skill_explainability_idor_protection():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.security import create_access_token
    from app.db import save_user
    import uuid

    client = TestClient(app)
    real_user_1 = f"usr-std-{uuid.uuid4().hex[:8]}"
    real_user_2 = f"usr-std-{uuid.uuid4().hex[:8]}"

    save_user({"id": real_user_1, "email": f"{real_user_1}@test.gov.in", "role": "STUDENT", "full_name": "Test User 1", "is_active": True})
    token_1 = create_access_token({"sub": real_user_1, "role": "STUDENT", "email": f"{real_user_1}@test.gov.in"})
    headers_1 = {"Authorization": f"Bearer {token_1}"}

    res_unauth = client.get(f"/api/student/skill-explainability/sk-001?student_id={real_user_1}")
    assert res_unauth.status_code == 401

    res_cross = client.get(f"/api/student/skill-explainability/sk-001?student_id={real_user_2}", headers=headers_1)
    assert res_cross.status_code == 403

    res_public = client.get("/api/student/skill-explainability/sk-001")
    assert res_public.status_code == 200

    res_demo = client.get("/api/student/skill-explainability/sk-001?student_id=stu-001")
    assert res_demo.status_code == 200


def test_gov_opportunities_and_schemes_recommended_authorization():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.security import create_access_token
    from app.db import save_user
    import uuid

    client = TestClient(app)
    real_user_1 = f"usr-std-{uuid.uuid4().hex[:8]}"
    real_user_2 = f"usr-std-{uuid.uuid4().hex[:8]}"
    admin_user = f"usr-adm-{uuid.uuid4().hex[:8]}"

    save_user({"id": real_user_1, "email": f"{real_user_1}@test.gov.in", "role": "STUDENT", "full_name": "Student 1", "is_active": True})
    save_user({"id": real_user_2, "email": f"{real_user_2}@test.gov.in", "role": "STUDENT", "full_name": "Student 2", "is_active": True})
    save_user({"id": admin_user, "email": f"{admin_user}@test.gov.in", "role": "ADMIN", "full_name": "Admin", "is_active": True})

    token_1 = create_access_token({"sub": real_user_1, "role": "STUDENT", "email": f"{real_user_1}@test.gov.in"})
    token_2 = create_access_token({"sub": real_user_2, "role": "STUDENT", "email": f"{real_user_2}@test.gov.in"})
    token_admin = create_access_token({"sub": admin_user, "role": "ADMIN", "email": f"{admin_user}@test.gov.in"})

    headers_1 = {"Authorization": f"Bearer {token_1}"}
    headers_2 = {"Authorization": f"Bearer {token_2}"}
    headers_admin = {"Authorization": f"Bearer {token_admin}"}

    mock_profile_1 = {
        "id": real_user_1,
        "user_id": real_user_1,
        "name": "Student 1",
        "skills": [{"skill_id": "sk-001", "name": "Python", "proficiency": "intermediate"}],
        "district": "Pune",
        "education": "B.Tech",
        "target_role": "Software Engineer",
        "source": "USER_SUBMITTED",
        "is_demo": False,
    }

    endpoints = [
        f"/api/gov/opportunities/recommended/{real_user_1}",
        f"/api/schemes/recommended/{real_user_1}",
    ]

    with patch("app.repositories.supabase_repository.get_student_profile", return_value=mock_profile_1):
        for ep in endpoints:
            res_unauth = client.get(ep)
            assert res_unauth.status_code == 401

            res_cross = client.get(ep, headers=headers_2)
            assert res_cross.status_code == 403

            res_owner = client.get(ep, headers=headers_1)
            assert res_owner.status_code == 200

            res_admin = client.get(ep, headers=headers_admin)
            assert res_admin.status_code == 200

    demo_endpoints = [
        "/api/gov/opportunities/recommended/stu-001",
        "/api/schemes/recommended/stu-001",
    ]
    for ep in demo_endpoints:
        res_demo = client.get(ep)
        assert res_demo.status_code == 200


def test_student_assessments_and_registry_authorization():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.security import create_access_token
    from app.db import save_user
    import uuid

    client = TestClient(app)
    real_user_1 = f"usr-std-{uuid.uuid4().hex[:8]}"
    real_user_2 = f"usr-std-{uuid.uuid4().hex[:8]}"
    admin_user = f"usr-adm-{uuid.uuid4().hex[:8]}"

    save_user({"id": real_user_1, "email": f"{real_user_1}@test.gov.in", "role": "STUDENT", "full_name": "Student 1", "is_active": True})
    save_user({"id": real_user_2, "email": f"{real_user_2}@test.gov.in", "role": "STUDENT", "full_name": "Student 2", "is_active": True})
    save_user({"id": admin_user, "email": f"{admin_user}@test.gov.in", "role": "ADMIN", "full_name": "Admin", "is_active": True})

    token_1 = create_access_token({"sub": real_user_1, "role": "STUDENT", "email": f"{real_user_1}@test.gov.in"})
    token_2 = create_access_token({"sub": real_user_2, "role": "STUDENT", "email": f"{real_user_2}@test.gov.in"})
    token_admin = create_access_token({"sub": admin_user, "role": "ADMIN", "email": f"{admin_user}@test.gov.in"})

    headers_1 = {"Authorization": f"Bearer {token_1}"}
    headers_2 = {"Authorization": f"Bearer {token_2}"}
    headers_admin = {"Authorization": f"Bearer {token_admin}"}

    mock_assessments = [
        {"id": "ast-demo-1", "user_id": "stu-001", "name": "Demo Student", "source": "DEMO_SYNTHETIC", "is_demo": True},
        {"id": "ast-real-1", "user_id": real_user_1, "name": "Student 1", "source": "USER_SUBMITTED", "is_demo": False},
        {"id": "ast-anon-1", "user_id": None, "name": "Anonymous Student", "source": "USER_SUBMITTED", "is_demo": False},
    ]

    with patch("app.repositories.supabase_repository.list_student_assessments", return_value=mock_assessments):
        res_unauth = client.get("/api/student/assessments")
        assert res_unauth.status_code == 200
        unauth_ids = [a["id"] for a in res_unauth.json()["assessments"]]
        assert "ast-demo-1" in unauth_ids
        assert "ast-real-1" not in unauth_ids
        assert "ast-anon-1" not in unauth_ids

        res_other = client.get("/api/student/assessments", headers=headers_2)
        assert res_other.status_code == 200
        other_ids = [a["id"] for a in res_other.json()["assessments"]]
        assert "ast-demo-1" in other_ids
        assert "ast-real-1" not in other_ids
        assert "ast-anon-1" not in other_ids

        res_owner = client.get("/api/student/assessments", headers=headers_1)
        assert res_owner.status_code == 200
        owner_ids = [a["id"] for a in res_owner.json()["assessments"]]
        assert "ast-demo-1" in owner_ids
        assert "ast-real-1" in owner_ids
        assert "ast-anon-1" not in owner_ids

        res_admin = client.get("/api/student/assessments", headers=headers_admin)
        assert res_admin.status_code == 200
        admin_ids = [a["id"] for a in res_admin.json()["assessments"]]
        assert "ast-demo-1" in admin_ids
        assert "ast-real-1" in admin_ids
        assert "ast-anon-1" in admin_ids

    with patch("app.repositories.supabase_repository.get_student_assessment", return_value={"id": "ast-anon-1", "user_id": None, "name": "Anonymous Student", "source": "USER_SUBMITTED", "is_demo": False}):
        assert client.get("/api/student/assessment/ast-anon-1").status_code == 401
        assert client.get("/api/student/assessment/ast-anon-1", headers=headers_1).status_code == 403
        assert client.get("/api/student/assessment/ast-anon-1", headers=headers_admin).status_code == 200

    mock_profiles = [
        {"id": "prof-1", "user_id": real_user_1, "name": "Student 1", "target_role": "AI Engineer", "skill_match_pct": 80, "source": "USER_SUBMITTED"},
    ]
    with patch("app.repositories.supabase_repository.list_student_profiles", return_value=mock_profiles), \
         patch("app.repositories.supabase_repository.list_student_assessments", return_value=[]):
        res_reg_unauth = client.get("/api/students")
        assert res_reg_unauth.status_code == 200
        reg_unauth_ids = [s["user_id"] for s in res_reg_unauth.json()]
        assert "stu-001" in reg_unauth_ids
        assert real_user_1 not in reg_unauth_ids

        res_reg_student = client.get("/api/students", headers=headers_1)
        assert res_reg_student.status_code == 200
        reg_std_ids = [s["user_id"] for s in res_reg_student.json()]
        assert "stu-001" in reg_std_ids
        assert real_user_1 not in reg_std_ids

        res_reg_admin = client.get("/api/students", headers=headers_admin)
        assert res_reg_admin.status_code == 200
        reg_admin_ids = [s["user_id"] for s in res_reg_admin.json()]
        assert real_user_1 in reg_admin_ids


def test_copilot_context_data_student_id_forwarding():
    from fastapi.testclient import TestClient
    from unittest.mock import patch, AsyncMock
    from app.main import app
    from app.core.security import create_access_token
    from app.db import save_user
    import uuid

    client = TestClient(app)
    real_user_1 = f"usr-std-{uuid.uuid4().hex[:8]}"
    real_user_2 = f"usr-std-{uuid.uuid4().hex[:8]}"
    admin_user = f"usr-adm-{uuid.uuid4().hex[:8]}"

    save_user({"id": real_user_1, "email": f"{real_user_1}@test.gov.in", "role": "STUDENT", "full_name": "Student 1", "is_active": True})
    save_user({"id": real_user_2, "email": f"{real_user_2}@test.gov.in", "role": "STUDENT", "full_name": "Student 2", "is_active": True})
    save_user({"id": admin_user, "email": f"{admin_user}@test.gov.in", "role": "ADMIN", "full_name": "Admin", "is_active": True})

    from app.repositories.supabase_repository import upsert_student_profile
    upsert_student_profile({
        "user_id": real_user_1,
        "name": "Student 1",
        "full_name": "Student 1",
        "skills": [{"skill_name": "Python", "proficiency": "intermediate"}],
        "source": "USER_SUBMITTED",
        "is_demo": False,
    })

    token_1 = create_access_token({"sub": real_user_1, "role": "STUDENT", "email": f"{real_user_1}@test.gov.in"})
    token_2 = create_access_token({"sub": real_user_2, "role": "STUDENT", "email": f"{real_user_2}@test.gov.in"})
    token_admin = create_access_token({"sub": admin_user, "role": "ADMIN", "email": f"{admin_user}@test.gov.in"})

    headers_1 = {"Authorization": f"Bearer {token_1}"}
    headers_2 = {"Authorization": f"Bearer {token_2}"}
    headers_admin = {"Authorization": f"Bearer {token_admin}"}

    payload = {
        "question": "Explain skills",
        "context_data": {"student_id": real_user_1},
    }

    assert client.post("/api/copilot/ask", json=payload).status_code == 401
    assert client.post("/api/copilot/ask", json=payload, headers=headers_2).status_code == 403

    with patch("ai.copilot.handle_question", new_callable=AsyncMock) as mock_handle:
        mock_handle.return_value = {"answer": "mocked answer"}
        res_owner = client.post("/api/copilot/ask", json=payload, headers=headers_1)
        assert res_owner.status_code == 200
        assert mock_handle.call_args.kwargs["student_id"] == real_user_1

        res_admin = client.post("/api/copilot/ask", json=payload, headers=headers_admin)
        assert res_admin.status_code == 200
        assert mock_handle.call_args.kwargs["student_id"] == real_user_1



