import uuid
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.core.security import create_access_token
from app.db import save_user
from app.repositories.supabase_repository import delete_employee_profile, get_employee_profile


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_employee_profile_authoritative_ownership_and_crud(client):
    emp_id = f"usr-emp-{uuid.uuid4().hex[:8]}"
    email = f"{emp_id}@skillsetu.gov.in"
    save_user({"id": emp_id, "email": email, "role": "EMPLOYEE", "full_name": "Test Employee", "is_active": True})
    token = create_access_token({"sub": emp_id, "role": "EMPLOYEE", "email": email})
    headers = {"Authorization": f"Bearer {token}"}

    delete_employee_profile(emp_id)

    res_empty = client.get("/api/employee/profile", headers=headers)
    assert res_empty.status_code == 404

    payload = {
        "current_role": "Robotics Integration Lead",
        "years_of_experience": 4.5,
        "industry": "Manufacturing",
        "education": "M.Tech Mechatronics",
        "target_role": "Chief Automation Architect",
        "preferred_location": "Pune",
        "skills": [
            {"skill_name": "PLC Programming", "proficiency": "advanced"},
            {"skill_name": "plc programming", "proficiency": "expert"},
            {"skill_name": "Python", "proficiency": "intermediate"},
        ],
        "certifications": [
            {
                "name": "Siemens Certified Automation Engineer",
                "issuer": "Siemens",
                "issue_date": "2025-01-10",
                "url": "https://siemens.cert/auto-1",
            }
        ],
    }

    res_post = client.post("/api/employee/profile", json=payload, headers=headers)
    assert res_post.status_code == 201
    created = res_post.json()["profile"]
    assert created["user_id"] == emp_id
    assert created["current_role"] == "Robotics Integration Lead"
    assert created["years_of_experience"] == 4.5
    assert len(created["skills"]) == 2

    res_get = client.get("/api/employee/profile", headers=headers)
    assert res_get.status_code == 200
    retrieved = res_get.json()["profile"]
    assert retrieved["user_id"] == emp_id
    assert retrieved["target_role"] == "Chief Automation Architect"

    update_payload = {
        "current_role": "Senior Robotics Specialist",
        "years_of_experience": 5.0,
        "industry": "Automotive & EV",
        "education": "M.Tech Mechatronics",
        "target_role": "Chief Technology Officer",
        "preferred_location": "Mumbai",
        "skills": [
            {"skill_name": "PLC Programming", "proficiency": "expert"},
        ],
        "certifications": [],
    }
    res_put = client.put("/api/employee/profile", json=update_payload, headers=headers)
    assert res_put.status_code == 200
    updated = res_put.json()["profile"]
    assert updated["user_id"] == emp_id
    assert updated["current_role"] == "Senior Robotics Specialist"
    assert updated["years_of_experience"] == 5.0
    assert len(updated["skills"]) == 1

    patch_payload = {
        "preferred_location": "Nagpur",
    }
    res_patch = client.patch("/api/employee/profile", json=patch_payload, headers=headers)
    assert res_patch.status_code == 200
    patched = res_patch.json()["profile"]
    assert patched["preferred_location"] == "Nagpur"
    assert patched["current_role"] == "Senior Robotics Specialist"


def test_employee_profile_role_authorization_and_isolation(client):
    student_id = f"usr-std-{uuid.uuid4().hex[:8]}"
    save_user({"id": student_id, "email": f"{student_id}@test.gov.in", "role": "STUDENT", "is_active": True})
    student_token = create_access_token({"sub": student_id, "role": "STUDENT", "email": f"{student_id}@test.gov.in"})
    student_headers = {"Authorization": f"Bearer {student_token}"}

    res_unauth = client.get("/api/employee/profile")
    assert res_unauth.status_code == 401

    res_forbidden = client.get("/api/employee/profile", headers=student_headers)
    assert res_forbidden.status_code == 403

    payload = {"current_role": "Engineer"}
    res_post_forbidden = client.post("/api/employee/profile", json=payload, headers=student_headers)
    assert res_post_forbidden.status_code == 403


def test_employee_profile_proficiency_validation(client):
    emp_id = f"usr-emp-{uuid.uuid4().hex[:8]}"
    email = f"{emp_id}@skillsetu.gov.in"
    save_user({"id": emp_id, "email": email, "role": "EMPLOYEE", "is_active": True})
    token = create_access_token({"sub": emp_id, "role": "EMPLOYEE", "email": email})
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "current_role": "Cloud Architect",
        "skills": [
            {"skill_name": "Cloud Computing", "proficiency": "god_tier"}
        ],
    }
    res = client.post("/api/employee/profile", json=payload, headers=headers)
    assert res.status_code == 422


def test_real_employee_never_receives_synthetic_demo_fallback(client):
    real_emp_id = f"usr-emp-real-{uuid.uuid4().hex[:8]}"
    email = f"{real_emp_id}@realcompany.com"
    save_user({"id": real_emp_id, "email": email, "role": "EMPLOYEE", "is_active": True})
    token = create_access_token({"sub": real_emp_id, "role": "EMPLOYEE", "email": email})
    headers = {"Authorization": f"Bearer {token}"}

    delete_employee_profile(real_emp_id)

    res = client.get("/api/employee/profile", headers=headers)
    assert res.status_code == 404
    assert get_employee_profile(real_emp_id) is None
