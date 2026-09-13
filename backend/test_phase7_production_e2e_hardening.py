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


def test_student_profile_skills_persistence_and_readback(client):
    user_id = f"usr-std-p7-{uuid.uuid4().hex[:8]}"
    email = f"{user_id}@skillsetu.gov.in"
    save_user({
        "id": user_id,
        "email": email,
        "role": "STUDENT",
        "full_name": "Radhika Deshmukh",
        "is_active": True,
    })
    token = create_access_token({"sub": user_id, "role": "STUDENT", "email": email})
    headers = {"Authorization": f"Bearer {token}"}

    empty_res = client.get("/api/student/profile", headers=headers)
    assert empty_res.status_code == 404

    payload = {
        "full_name": "Radhika Deshmukh",
        "institution": "Government College of Engineering, Pune",
        "degree": "B.Tech Computer Science",
        "education_level": "Undergraduate (B.Tech / B.E / B.Sc)",
        "academic_year": "Final Year",
        "graduation_year": 2026,
        "target_role": "AI Robotics Engineer",
        "desired_role": "AI Robotics Engineer",
        "preferred_location": "Pune",
        "career_interests": ["Machine Learning", "Autonomous Navigation"],
        "skills": [
            {"skill_name": "Python", "proficiency": "advanced"},
            {"skill_name": "python", "proficiency": "expert"},
            {"skill_name": "ROS2", "proficiency": "intermediate"},
        ],
        "projects": [
            {
                "name": "Warehouse Robot Fleet",
                "description": "Multi-agent pathfinding simulation in ROS2",
                "skills": ["ROS2", "Python"],
                "url": "https://github.com/example/warehouse-fleet",
            }
        ],
        "certifications": [
            {
                "name": "ROS2 Developer Certification",
                "issuer": "Open Robotics",
                "issue_date": "2025-06-15",
                "url": "https://certs.openrobotics.org/123",
            }
        ],
        "courses": [
            {
                "course_name": "Autonomous Mobile Robots",
                "provider": "NPTEL",
                "status": "completed",
            }
        ],
        "experience": [],
    }

    create_res = client.post("/api/student/profile", json=payload, headers=headers)
    assert create_res.status_code == 201
    created_profile = create_res.json()["profile"]
    assert created_profile["user_id"] == user_id
    assert created_profile["full_name"] == "Radhika Deshmukh"
    assert created_profile["target_role"] == "AI Robotics Engineer"
    assert len(created_profile["skills"]) == 2
    python_skill = next(s for s in created_profile["skills"] if s["skill_name"].lower() == "python")
    assert python_skill["proficiency"] == "expert"

    get_res = client.get("/api/student/profile", headers=headers)
    assert get_res.status_code == 200
    read_profile = get_res.json()["profile"]
    assert read_profile["user_id"] == user_id
    assert read_profile["institution"] == "Government College of Engineering, Pune"
    assert len(read_profile["skills"]) == 2
    assert len(read_profile["projects"]) == 1

    skills_update_payload = {
        "skills": [
            {"skill_name": "Python", "proficiency": "expert"},
            {"skill_name": "ROS2", "proficiency": "advanced"},
            {"skill_name": "C++", "proficiency": "intermediate"},
        ]
    }
    skills_put_res = client.put("/api/student/profile/skills", json=skills_update_payload, headers=headers)
    assert skills_put_res.status_code == 200
    updated_skills = skills_put_res.json()["skills"]
    assert len(updated_skills) == 3

    verify_res = client.get("/api/student/profile", headers=headers)
    assert verify_res.status_code == 200
    assert len(verify_res.json()["profile"]["skills"]) == 3


def test_employee_profile_skills_persistence_and_readback(client):
    user_id = f"usr-emp-p7-{uuid.uuid4().hex[:8]}"
    email = f"{user_id}@skillsetu.gov.in"
    save_user({
        "id": user_id,
        "email": email,
        "role": "EMPLOYEE",
        "full_name": "Karan Patil",
        "is_active": True,
    })
    token = create_access_token({"sub": user_id, "role": "EMPLOYEE", "email": email})
    headers = {"Authorization": f"Bearer {token}"}

    empty_res = client.get("/api/employee/profile", headers=headers)
    assert empty_res.status_code == 404

    payload = {
        "full_name": "Karan Patil",
        "current_role": "Industrial Automation Engineer",
        "years_of_experience": 6.5,
        "industry": "Electric Vehicles & Automotive",
        "education": "B.E Instrumentation",
        "target_role": "Smart Manufacturing Systems Architect",
        "preferred_location": "Chakan, Pune",
        "skills": [
            {"skill_name": "SCADA", "proficiency": "advanced"},
            {"skill_name": "scada", "proficiency": "expert"},
            {"skill_name": "PLC Programming", "proficiency": "advanced"},
        ],
        "certifications": [
            {
                "name": "Siemens Certified Specialist",
                "issuer": "Siemens India",
                "issue_date": "2024-03-20",
                "url": "https://siemens.in/cert/123",
            }
        ],
    }

    create_res = client.post("/api/employee/profile", json=payload, headers=headers)
    assert create_res.status_code == 201
    created_profile = create_res.json()["profile"]
    assert created_profile["user_id"] == user_id
    assert created_profile["current_role"] == "Industrial Automation Engineer"
    assert created_profile["years_of_experience"] == 6.5
    assert len(created_profile["skills"]) == 2
    scada_skill = next(s for s in created_profile["skills"] if s["skill_name"].lower() == "scada")
    assert scada_skill["proficiency"] == "expert"

    get_res = client.get("/api/employee/profile", headers=headers)
    assert get_res.status_code == 200
    read_profile = get_res.json()["profile"]
    assert read_profile["user_id"] == user_id
    assert read_profile["target_role"] == "Smart Manufacturing Systems Architect"
    assert len(read_profile["skills"]) == 2

    skills_update_payload = {
        "skills": [
            {"skill_name": "SCADA", "proficiency": "expert"},
            {"skill_name": "PLC Programming", "proficiency": "expert"},
            {"skill_name": "Industrial IoT", "proficiency": "intermediate"},
        ]
    }
    skills_put_res = client.put("/api/employee/profile/skills", json=skills_update_payload, headers=headers)
    assert skills_put_res.status_code == 200
    assert len(skills_put_res.json()["skills"]) == 3

    verify_res = client.get("/api/employee/profile", headers=headers)
    assert verify_res.status_code == 200
    assert len(verify_res.json()["profile"]["skills"]) == 3


def test_gov_opportunities_and_industry_signals_integrity(client):
    gov_user_id = f"usr-gov-p7-{uuid.uuid4().hex[:8]}"
    gov_email = f"{gov_user_id}@skillsetu.gov.in"
    save_user({
        "id": gov_user_id,
        "email": gov_email,
        "role": "GOVERNMENT",
        "full_name": "Director of Skill Development",
        "is_active": True,
    })
    gov_token = create_access_token({"sub": gov_user_id, "role": "GOVERNMENT", "email": gov_email})
    gov_headers = {"Authorization": f"Bearer {gov_token}"}

    student_user_id = f"usr-std-forbidden-{uuid.uuid4().hex[:8]}"
    student_email = f"{student_user_id}@skillsetu.gov.in"
    save_user({
        "id": student_user_id,
        "email": student_email,
        "role": "STUDENT",
        "full_name": "Unauthorized Student",
        "is_active": True,
    })
    student_token = create_access_token({"sub": student_user_id, "role": "STUDENT", "email": student_email})
    student_headers = {"Authorization": f"Bearer {student_token}"}

    opp_payload = {
        "name": "Maharashtra EV Assembly Apprenticeship 2026",
        "department": "Department of Skills, Employment, Entrepreneurship & Innovation",
        "description": "Hands-on battery pack integration and electrical validation apprenticeship in Pune.",
        "eligibility_criteria": "Diploma or Degree in Electrical, Mechatronics, or Mechanical Engineering",
        "target_skills": ["EV Battery Technology", "Electrical Harnessing", "Safety Protocols"],
        "district_coverage": ["Pune", "Aurangabad"],
        "opportunity_type": "APPRENTICESHIP",
        "application_url": "https://mahaswayam.gov.in/apprenticeships/ev-2026",
        "status": "active",
    }

    forbidden_res = client.post("/api/gov/opportunities", json=opp_payload, headers=student_headers)
    assert forbidden_res.status_code == 403

    create_res = client.post("/api/gov/opportunities", json=opp_payload, headers=gov_headers)
    assert create_res.status_code == 201
    created_opp = create_res.json()["opportunity"]
    assert created_opp["name"] == "Maharashtra EV Assembly Apprenticeship 2026"
    assert created_opp["data_provenance"] == "GOVERNMENT_OFFICIAL"
    assert created_opp["is_demo"] is False

    list_res = client.get("/api/gov/opportunities?is_demo=false", headers=gov_headers)
    assert list_res.status_code == 200
    items = list_res.json()
    assert any(o["id"] == created_opp["id"] for o in items)

    filtered_res = client.get("/api/gov/opportunities?is_demo=false&district=Pune", headers=gov_headers)
    assert filtered_res.status_code == 200
    pune_items = filtered_res.json()
    assert any(o["id"] == created_opp["id"] for o in pune_items)


def test_copilot_authoritative_data_and_idor_protection(client):
    student_1_id = f"usr-std-auth1-{uuid.uuid4().hex[:8]}"
    student_1_email = f"{student_1_id}@skillsetu.gov.in"
    save_user({
        "id": student_1_id,
        "email": student_1_email,
        "role": "STUDENT",
        "full_name": "Student One",
        "is_active": True,
    })
    token_1 = create_access_token({"sub": student_1_id, "role": "STUDENT", "email": student_1_email})
    headers_1 = {"Authorization": f"Bearer {token_1}"}

    student_1_profile_payload = {
        "full_name": "Student One",
        "institution": "Government Polytechnic Pune",
        "degree": "Diploma",
        "education_level": "Polytechnic Diploma",
        "academic_year": "Final Year",
        "graduation_year": 2026,
        "target_role": "Industrial Automation Engineer",
        "skills": [{"skill_name": "PLC Programming", "proficiency": "advanced"}],
    }
    client.post("/api/student/profile", json=student_1_profile_payload, headers=headers_1)

    student_2_id = f"usr-std-auth2-{uuid.uuid4().hex[:8]}"
    student_2_email = f"{student_2_id}@skillsetu.gov.in"
    save_user({
        "id": student_2_id,
        "email": student_2_email,
        "role": "STUDENT",
        "full_name": "Student Two",
        "is_active": True,
    })
    token_2 = create_access_token({"sub": student_2_id, "role": "STUDENT", "email": student_2_email})
    headers_2 = {"Authorization": f"Bearer {token_2}"}

    idor_query = {
        "question": "What are my recommended career paths and missing skills?",
        "role": "student",
        "student_id": student_1_id,
        "is_demo": False,
    }
    idor_res = client.post("/api/copilot/ask", json=idor_query, headers=headers_2)
    assert idor_res.status_code == 403

    authorized_query = {
        "question": "What skills are required for Industrial Automation?",
        "role": "student",
        "student_id": student_1_id,
        "is_demo": False,
    }
    auth_res = client.post("/api/copilot/ask", json=authorized_query, headers=headers_1)
    assert auth_res.status_code == 200
    answer_payload = auth_res.json()
    assert "answer" in answer_payload
    assert answer_payload.get("demo_mode") is False


def test_real_mode_no_demo_fallback_guarantees(client):
    real_opps_res = client.get("/api/gov/opportunities?is_demo=false")
    assert real_opps_res.status_code == 200
    real_opps = real_opps_res.json()
    for opp in real_opps:
        assert opp.get("is_demo") is not True
        assert opp.get("source") != "DEMO_SYNTHETIC"

    copilot_query = {
        "question": "Provide labour market statistics for Maharashtra.",
        "role": "student",
        "is_demo": False,
    }
    copilot_res = client.post("/api/copilot/ask", json=copilot_query)
    assert copilot_res.status_code == 200
    body = copilot_res.json()
    assert body.get("demo_mode") is False
    assert "DemoProvider" not in body.get("model", "")


def test_honest_empty_states_under_real_mode(client):
    res_empty_district = client.get("/api/gov/opportunities?is_demo=false&district=NonExistentDistrictXYZ")
    assert res_empty_district.status_code == 200
    assert res_empty_district.json() == []

    nonexistent_user_id = f"usr-emp-none-{uuid.uuid4().hex[:8]}"
    nonexistent_email = f"{nonexistent_user_id}@skillsetu.gov.in"
    save_user({
        "id": nonexistent_user_id,
        "email": nonexistent_email,
        "role": "EMPLOYEE",
        "full_name": "No Profile Employee",
        "is_active": True,
    })
    token = create_access_token({"sub": nonexistent_user_id, "role": "EMPLOYEE", "email": nonexistent_email})
    headers = {"Authorization": f"Bearer {token}"}
    res_profile_404 = client.get("/api/employee/profile", headers=headers)
    assert res_profile_404.status_code == 404
