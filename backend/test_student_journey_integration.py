import uuid
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.core.security import create_access_token
from app.db import save_user


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_authenticated_student_diagnostic_quiz_not_deadlocked(client):
    user_id = f"usr-std-quiz-{uuid.uuid4().hex[:8]}"
    email = f"{user_id}@skillsetu.gov.in"
    save_user({
        "id": user_id,
        "email": email,
        "role": "STUDENT",
        "full_name": "Kavita Shinde",
        "is_active": True,
    })
    token = create_access_token({"sub": user_id, "role": "STUDENT", "email": email})
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/student/assessment/quiz-questions", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data.get("questions", [])) > 0
    assert data.get("status") in ("profile_incomplete", "general_fallback", "success")


def test_assessment_submission_syncs_student_profile_and_passport(client):
    user_id = f"usr-std-sync-{uuid.uuid4().hex[:8]}"
    email = f"{user_id}@skillsetu.gov.in"
    save_user({
        "id": user_id,
        "email": email,
        "role": "STUDENT",
        "full_name": "Siddharth More",
        "is_active": True,
    })
    token = create_access_token({"sub": user_id, "role": "STUDENT", "email": email})
    headers = {"Authorization": f"Bearer {token}"}

    res_empty_prof = client.get("/api/student/profile", headers=headers)
    assert res_empty_prof.status_code == 404

    submit_payload = {
        "name": "Siddharth More",
        "education": "B.Tech Electrical Engineering",
        "career_goal": "EV Technician",
        "district": "Pune",
        "current_skills": [
            {"skill_name": "Python", "proficiency": "intermediate"},
            {"skill_name": "EV Battery Technology", "proficiency": "advanced"},
        ],
        "interests": ["Electric Vehicles", "Robotics & Automation"],
        "quiz_answers": {"q1": "a", "q2": "b"},
    }

    res_submit = client.post("/api/student/assessment", json=submit_payload, headers=headers)
    assert res_submit.status_code == 200
    submit_data = res_submit.json()
    assert submit_data.get("status") == "success"
    assert submit_data["assessment"]["name"] == "Siddharth More"

    res_prof_after = client.get("/api/student/profile", headers=headers)
    assert res_prof_after.status_code == 200
    prof_data = res_prof_after.json()["profile"]
    assert prof_data["full_name"] == "Siddharth More"
    assert prof_data["preferred_location"] == "Pune"
    assert prof_data["target_role"] == "EV Technician"
    assert any(s.get("skill_name") == "EV Battery Technology" for s in prof_data.get("skills", []))

    res_pass = client.get("/api/student/me/passport", headers=headers)
    assert res_pass.status_code == 200
    pass_data = res_pass.json()
    assert pass_data["target_role"] == "EV Technician"
    assert any(s.get("skill_name") == "EV Battery Technology" for s in pass_data.get("current_skills", []))


def test_student_profile_update_takes_precedence_over_stale_assessment(client):
    user_id = f"usr-std-prec-{uuid.uuid4().hex[:8]}"
    email = f"{user_id}@skillsetu.gov.in"
    save_user({
        "id": user_id,
        "email": email,
        "role": "STUDENT",
        "full_name": "Ananya Joshi",
        "is_active": True,
    })
    token = create_access_token({"sub": user_id, "role": "STUDENT", "email": email})
    headers = {"Authorization": f"Bearer {token}"}

    submit_payload = {
        "name": "Ananya Joshi",
        "education": "B.Tech Computer Science",
        "career_goal": "AI Engineer",
        "district": "Mumbai City",
        "current_skills": [
            {"skill_name": "Python", "proficiency": "intermediate"},
        ],
        "interests": ["AI / ML"],
        "quiz_answers": {},
    }
    res_submit = client.post("/api/student/assessment", json=submit_payload, headers=headers)
    assert res_submit.status_code == 200

    profile_update = {
        "full_name": "Ananya Joshi",
        "institution": "VJTI Mumbai",
        "degree": "B.Tech Computer Science",
        "education_level": "Undergraduate (B.Tech / B.E / B.Sc)",
        "academic_year": "Final Year",
        "graduation_year": 2026,
        "target_role": "Full Stack Developer",
        "desired_role": "Full Stack Developer",
        "preferred_location": "Mumbai City",
        "career_interests": ["Web Development", "Cloud"],
        "skills": [
            {"skill_name": "Python", "proficiency": "expert"},
            {"skill_name": "React", "proficiency": "advanced"},
            {"skill_name": "Node.js", "proficiency": "intermediate"},
        ],
        "projects": [],
        "certifications": [],
        "courses": [],
        "experience": [],
    }

    res_put_prof = client.put("/api/student/profile", json=profile_update, headers=headers)
    assert res_put_prof.status_code == 200

    res_pass = client.get("/api/student/me/passport", headers=headers)
    assert res_pass.status_code == 200
    pass_data = res_pass.json()
    assert pass_data["target_role"] == "Full Stack Developer"
    assert any(s.get("skill_name") == "React" for s in pass_data.get("current_skills", []))


def test_career_recommendations_and_opportunities_normalize_profile_fields(client):
    user_id = f"usr-std-rec-{uuid.uuid4().hex[:8]}"
    email = f"{user_id}@skillsetu.gov.in"
    save_user({
        "id": user_id,
        "email": email,
        "role": "STUDENT",
        "full_name": "Meera Kulkarni",
        "is_active": True,
    })
    token = create_access_token({"sub": user_id, "role": "STUDENT", "email": email})
    headers = {"Authorization": f"Bearer {token}"}

    create_profile_payload = {
        "full_name": "Meera Kulkarni",
        "institution": "COEP Tech University",
        "degree": "B.Tech Information Technology",
        "education_level": "Undergraduate (B.Tech / B.E / B.Sc)",
        "academic_year": "Final Year",
        "graduation_year": 2026,
        "target_role": "Cybersecurity Analyst",
        "desired_role": "Cybersecurity Analyst",
        "preferred_location": "Pune",
        "career_interests": ["Cybersecurity", "Network Security"],
        "skills": [
            {"skill_name": "Network Security", "proficiency": "intermediate"},
            {"skill_name": "Linux", "proficiency": "advanced"},
        ],
        "projects": [],
        "certifications": [],
        "courses": [],
        "experience": [],
    }
    res_create = client.post("/api/student/profile", json=create_profile_payload, headers=headers)
    assert res_create.status_code in (200, 201)

    res_recs = client.get("/api/student/recommendations/me", headers=headers)
    assert res_recs.status_code == 200
    recs_data = res_recs.json()
    assert recs_data.get("status") == "success"
    assert recs_data.get("candidate_name") == "Meera Kulkarni"
    assert recs_data.get("candidate_district") == "Pune"
    assert len(recs_data.get("recommended_careers", [])) > 0

    res_gov = client.get("/api/gov/opportunities/recommended/me", headers=headers)
    assert res_gov.status_code == 200
    gov_data = res_gov.json()
    assert "opportunities" in gov_data

    res_schemes = client.get("/api/schemes/recommended/me", headers=headers)
    assert res_schemes.status_code == 200
    schemes_data = res_schemes.json()
    assert "schemes" in schemes_data
