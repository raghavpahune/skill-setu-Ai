import uuid
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.core.security import create_access_token
from app.db import save_user
from app.repositories.supabase_repository import delete_employee_profile


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_employee_profile_creation_and_passport_retrieval(client):
    user_id = f"usr-emp-pass-{uuid.uuid4().hex[:8]}"
    email = f"{user_id}@skillsetu.gov.in"
    save_user({
        "id": user_id,
        "email": email,
        "role": "EMPLOYEE",
        "full_name": "Rohan Deshmukh",
        "is_active": True,
    })
    token = create_access_token({"sub": user_id, "role": "EMPLOYEE", "email": email})
    headers = {"Authorization": f"Bearer {token}"}

    delete_employee_profile(user_id)

    profile_payload = {
        "current_role": "Software Developer",
        "years_of_experience": 3.0,
        "industry": "IT / Software Services",
        "education": "B.E Computer Engineering",
        "target_role": "AI Engineer",
        "preferred_location": "Pune",
        "skills": [
            {"skill_name": "Python", "proficiency": "advanced"},
            {"skill_name": "SQL", "proficiency": "intermediate"},
        ],
        "certifications": [
            {
                "name": "AWS Certified Developer",
                "issuer": "Amazon Web Services",
                "issue_date": "2025-02-15",
                "url": "https://aws.cert/dev-1",
            }
        ],
    }

    create_res = client.post("/api/employee/profile", json=profile_payload, headers=headers)
    assert create_res.status_code == 201
    assert create_res.json()["profile"]["target_role"] == "AI Engineer"

    pass_res = client.get("/api/student/me/passport", headers=headers)
    assert pass_res.status_code == 200
    pass_data = pass_res.json()
    assert pass_data["user_id"] == user_id
    assert pass_data["target_role"] == "AI Engineer"
    assert pass_data["is_personalized"] is True
    assert len(pass_data["current_skills"]) >= 2
    assert any("Python" in s["skill_name"] for s in pass_data["current_skills"])


def test_employee_career_recommendations(client):
    user_id = f"usr-emp-rec-{uuid.uuid4().hex[:8]}"
    email = f"{user_id}@skillsetu.gov.in"
    save_user({
        "id": user_id,
        "email": email,
        "role": "EMPLOYEE",
        "full_name": "Snehal Kulkarni",
        "is_active": True,
    })
    token = create_access_token({"sub": user_id, "role": "EMPLOYEE", "email": email})
    headers = {"Authorization": f"Bearer {token}"}

    delete_employee_profile(user_id)

    profile_payload = {
        "current_role": "Mechanical Engineer",
        "years_of_experience": 4.0,
        "industry": "Electric Vehicles & Automotive",
        "education": "B.Tech Mechanical",
        "target_role": "Smart Manufacturing Engineer",
        "preferred_location": "Pune",
        "skills": [
            {"skill_name": "AutoCAD", "proficiency": "advanced"},
            {"skill_name": "CNC Programming", "proficiency": "intermediate"},
        ],
        "certifications": [],
    }

    create_res = client.post("/api/employee/profile", json=profile_payload, headers=headers)
    assert create_res.status_code == 201

    rec_res = client.get("/api/student/recommendations/me", headers=headers)
    assert rec_res.status_code == 200
    rec_data = rec_res.json()
    assert rec_data["candidate_name"] == "Snehal Kulkarni"
    assert rec_data["target_career_goal"] == "Smart Manufacturing Engineer"
    assert "overall_readiness" in rec_data
    assert len(rec_data.get("recommended_careers", [])) >= 1


def test_employee_personalized_industry_alerts(client):
    user_id = f"usr-emp-alert-{uuid.uuid4().hex[:8]}"
    email = f"{user_id}@skillsetu.gov.in"
    save_user({
        "id": user_id,
        "email": email,
        "role": "EMPLOYEE",
        "full_name": "Amit Jadhav",
        "is_active": True,
    })
    token = create_access_token({"sub": user_id, "role": "EMPLOYEE", "email": email})
    headers = {"Authorization": f"Bearer {token}"}

    delete_employee_profile(user_id)

    profile_payload = {
        "current_role": "Data Analyst",
        "years_of_experience": 2.5,
        "industry": "IT / Software Services",
        "education": "B.Sc Statistics",
        "target_role": "AI Engineer",
        "preferred_location": "Mumbai",
        "skills": [
            {"skill_name": "Python", "proficiency": "advanced"},
            {"skill_name": "Machine Learning", "proficiency": "intermediate"},
        ],
        "certifications": [],
    }

    client.post("/api/employee/profile", json=profile_payload, headers=headers)

    alert_res = client.get(f"/api/student/industry-alerts?student_id={user_id}&domain=ai_ml", headers=headers)
    assert alert_res.status_code == 200
    alert_data = alert_res.json()
    assert "alerts" in alert_data
    assert len(alert_data["alerts"]) >= 1


def test_employee_copilot_transition_query(client):
    user_id = f"usr-emp-copilot-{uuid.uuid4().hex[:8]}"
    email = f"{user_id}@skillsetu.gov.in"
    save_user({
        "id": user_id,
        "email": email,
        "role": "EMPLOYEE",
        "full_name": "Pooja Gaikwad",
        "is_active": True,
    })
    token = create_access_token({"sub": user_id, "role": "EMPLOYEE", "email": email})
    headers = {"Authorization": f"Bearer {token}"}

    delete_employee_profile(user_id)

    profile_payload = {
        "current_role": "Electrical Maintenance Technician",
        "years_of_experience": 3.5,
        "industry": "Electric Vehicles & Automotive",
        "education": "Diploma Electrical",
        "target_role": "EV Powertrain Specialist",
        "preferred_location": "Pune",
        "skills": [
            {"skill_name": "Circuit Analysis", "proficiency": "expert"},
            {"skill_name": "EV Battery Technology", "proficiency": "intermediate"},
        ],
        "certifications": [],
    }

    client.post("/api/employee/profile", json=profile_payload, headers=headers)

    query_payload = {
        "question": "How can I transition from my current role to an advanced technology role in Maharashtra?",
        "role": "employee",
        "district": "Pune",
        "student_id": user_id,
        "is_demo": True,
    }

    copilot_res = client.post("/api/copilot/ask", json=query_payload, headers=headers)
    assert copilot_res.status_code == 200
    copilot_data = copilot_res.json()
    assert copilot_data["role"] == "employee"
    assert len(copilot_data.get("answer", "")) > 50


def test_employee_data_isolation_and_authorization(client):
    emp_id = f"usr-emp-iso-{uuid.uuid4().hex[:8]}"
    other_student_id = f"usr-std-iso-{uuid.uuid4().hex[:8]}"

    save_user({"id": emp_id, "email": f"{emp_id}@skillsetu.gov.in", "role": "EMPLOYEE", "full_name": "Target Employee", "is_active": True})
    save_user({"id": other_student_id, "email": f"{other_student_id}@skillsetu.gov.in", "role": "STUDENT", "full_name": "Other Student", "is_active": True})

    emp_token = create_access_token({"sub": emp_id, "role": "EMPLOYEE", "email": f"{emp_id}@skillsetu.gov.in"})
    student_token = create_access_token({"sub": other_student_id, "role": "STUDENT", "email": f"{other_student_id}@skillsetu.gov.in"})

    emp_headers = {"Authorization": f"Bearer {emp_token}"}
    student_headers = {"Authorization": f"Bearer {student_token}"}

    delete_employee_profile(emp_id)

    profile_payload = {
        "current_role": "Software Engineer",
        "years_of_experience": 2.0,
        "industry": "IT / Software Services",
        "education": "B.Tech IT",
        "target_role": "Cloud Architect",
        "preferred_location": "Pune",
        "skills": [{"skill_name": "Python", "proficiency": "advanced"}],
        "certifications": [],
    }

    client.post("/api/employee/profile", json=profile_payload, headers=emp_headers)

    cross_rec = client.get(f"/api/student/recommendations/{emp_id}", headers=student_headers)
    assert cross_rec.status_code == 403

    cross_pass = client.get(f"/api/student/{emp_id}/passport", headers=student_headers)
    assert cross_pass.status_code == 403


def test_employee_cross_user_industry_alerts_authorization(client):
    emp_id = f"usr-emp-alert-{uuid.uuid4().hex[:8]}"
    other_student_id = f"usr-std-alert-{uuid.uuid4().hex[:8]}"
    admin_id = f"usr-admin-alert-{uuid.uuid4().hex[:8]}"

    save_user({"id": emp_id, "email": f"{emp_id}@skillsetu.gov.in", "role": "EMPLOYEE", "full_name": "Alert Employee", "is_active": True})
    save_user({"id": other_student_id, "email": f"{other_student_id}@skillsetu.gov.in", "role": "STUDENT", "full_name": "Other Student", "is_active": True})
    save_user({"id": admin_id, "email": f"{admin_id}@skillsetu.gov.in", "role": "ADMIN", "full_name": "Admin User", "is_active": True})

    emp_token = create_access_token({"sub": emp_id, "role": "EMPLOYEE", "email": f"{emp_id}@skillsetu.gov.in"})
    student_token = create_access_token({"sub": other_student_id, "role": "STUDENT", "email": f"{other_student_id}@skillsetu.gov.in"})
    admin_token = create_access_token({"sub": admin_id, "role": "ADMIN", "email": f"{admin_id}@skillsetu.gov.in"})

    emp_headers = {"Authorization": f"Bearer {emp_token}"}
    student_headers = {"Authorization": f"Bearer {student_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    delete_employee_profile(emp_id)
    profile_payload = {
        "current_role": "Data Analyst",
        "years_of_experience": 2.0,
        "industry": "IT / Software Services",
        "education": "B.Sc Statistics",
        "target_role": "Data Scientist",
        "preferred_location": "Pune",
        "skills": [{"skill_name": "Python", "proficiency": "advanced"}],
        "certifications": [],
    }
    client.post("/api/employee/profile", json=profile_payload, headers=emp_headers)

    unauth_res = client.get(f"/api/student/industry-alerts?student_id={emp_id}")
    assert unauth_res.status_code == 401

    cross_res = client.get(f"/api/student/industry-alerts?student_id={emp_id}", headers=student_headers)
    assert cross_res.status_code == 403

    owner_res = client.get(f"/api/student/industry-alerts?student_id={emp_id}", headers=emp_headers)
    assert owner_res.status_code == 200

    admin_res = client.get(f"/api/student/industry-alerts?student_id={emp_id}", headers=admin_headers)
    assert admin_res.status_code == 200


@pytest.mark.anyio
async def test_demo_provider_forecast_dispatch_with_employee_profile():
    from ai.demo_provider import DemoProvider
    provider = DemoProvider()

    ctx = {
        "employee_profile": {
            "current_role": "Software Engineer",
            "target_role": "AI Architect",
            "skills": ["Python", "Docker"],
            "certifications": ["AWS"],
        }
    }

    forecast_ans = await provider.generate("What is the skill forecast for emerging tech?", ctx)
    assert "### 12-to-24 Month Skill Forecast" in forecast_ans
    assert "Rising Exponentially" in forecast_ans

    trend_ans = await provider.generate("What are the rising technology trends?", ctx)
    assert "### 12-to-24 Month Skill Forecast" in trend_ans

    trans_ans = await provider.generate("How can I transition to AI Architect?", ctx)
    assert "### Career Transition & Upskilling Intelligence" in trans_ans


@pytest.mark.anyio
async def test_copilot_market_intelligence_restricted_when_unindexed_despite_employee_profile(monkeypatch):
    from ai.copilot import handle_question
    from app.repositories.supabase_repository import SupabaseRepositoryError

    fake_skills = [{"id": "sk-real-100", "name": "Python", "category": "IT"}]
    monkeypatch.setattr("app.repositories.supabase_repository.list_skills", lambda: fake_skills)
    monkeypatch.setattr("app.repositories.supabase_repository.list_jobs", lambda **kwargs: [{"id": "job-1", "title": "Dev", "district": "Pune"}])
    def fail_job_skills(**kwargs):
        raise SupabaseRepositoryError("Query failed")
    monkeypatch.setattr("app.repositories.supabase_repository.list_job_skills", fail_job_skills)
    monkeypatch.setattr("app.repositories.supabase_repository.list_courses", lambda **kwargs: [])
    monkeypatch.setattr("app.repositories.supabase_repository.list_course_skills", lambda **kwargs: [])

    fake_ep = {
        "id": "usr-emp-123",
        "full_name": "Test Employee",
        "current_role": "Developer",
        "target_role": "Senior Dev",
        "skills": [{"skill_name": "Python"}],
        "certifications": [],
    }
    monkeypatch.setattr("app.repositories.supabase_repository.get_employee_profile", lambda uid: fake_ep)

    res = await handle_question(
        question="Tell me about Python",
        role="employee",
        student_id="usr-emp-123",
        is_demo=False,
    )
    assert res["provenance_label"] == "⚠️ No Authoritative Data"
    assert res["data_grounded"] is False


def test_passport_assessment_newer_than_profile_selection(client, monkeypatch):
    user_id = f"usr-std-pref-{uuid.uuid4().hex[:8]}"
    email = f"{user_id}@skillsetu.gov.in"
    save_user({"id": user_id, "email": email, "role": "STUDENT", "full_name": "Time Student", "is_active": True})
    token = create_access_token({"sub": user_id, "role": "STUDENT", "email": email})
    headers = {"Authorization": f"Bearer {token}"}

    old_profile = {
        "id": user_id,
        "user_id": user_id,
        "name": "Time Student",
        "skills": [{"skill_id": "sk-001", "skill_name": "Old Profile Skill", "proficiency": "beginner"}],
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    newer_assessment = {
        "id": f"asst-{user_id}",
        "user_id": user_id,
        "current_skills": [{"skill_id": "sk-002", "skill_name": "New Assessment Skill", "proficiency": "advanced"}],
        "created_at": "2026-02-01T00:00:00Z",
        "updated_at": "2026-02-01T00:00:00Z",
    }

    monkeypatch.setattr("app.repositories.supabase_repository.get_student_profile", lambda uid: old_profile)
    monkeypatch.setattr("app.repositories.supabase_repository.get_student_assessment_by_user", lambda **kwargs: newer_assessment)
    monkeypatch.setattr("app.repositories.supabase_repository.get_student_assessment", lambda sid: newer_assessment)

    res = client.get("/api/student/me/passport", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert any("New Assessment Skill" in s.get("skill_name", "") for s in data.get("current_skills", []))

    newer_profile = {
        **old_profile,
        "updated_at": "2026-03-01T00:00:00Z",
        "skills": [{"skill_id": "sk-001", "skill_name": "Newer Profile Skill", "proficiency": "expert"}],
    }
    monkeypatch.setattr("app.repositories.supabase_repository.get_student_profile", lambda uid: newer_profile)
    res_prof = client.get("/api/student/me/passport", headers=headers)
    assert res_prof.status_code == 200
    data_prof = res_prof.json()
    assert any("Newer Profile Skill" in s.get("skill_name", "") for s in data_prof.get("current_skills", []))

    res_sp = client.get(f"/api/student/{user_id}/passport", headers=headers)
    assert res_sp.status_code == 200
    data_sp = res_sp.json()
    assert any("Newer Profile Skill" in s.get("skill_name", "") for s in data_sp.get("current_skills", []))


