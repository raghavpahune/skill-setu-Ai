"""Test suite for Phase 12: Student Data Collection & Assessment Flow."""
import pytest
from starlette.testclient import TestClient
from app.main import app
from app.db import init_db, get_demo

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


def test_quiz_questions_endpoint():
    """GET /api/student/assessment/quiz-questions returns structured diagnostic questions."""
    res = client.get("/api/student/assessment/quiz-questions")
    assert res.status_code == 200
    data = res.json()
    assert "questions" in data
    questions = data["questions"]
    assert len(questions) >= 5

    for q in questions:
        assert "id" in q
        assert "category" in q
        assert "question" in q
        assert "options" in q
        assert len(q["options"]) >= 4
        for opt in q["options"]:
            assert "key" in opt
            assert "text" in opt


def test_submit_student_assessment_success():
    """POST /api/student/assessment validates input, computes score and gaps, and returns report."""
    payload = {
        "name": "Devendra Shinde",
        "education": "BE Artificial Intelligence & Data Science (3rd Year)",
        "district": "Pune",
        "career_goal": "AI Engineer",
        "interests": ["AI / ML", "Data Science", "Cloud Computing"],
        "current_skills": [
            {"skill_name": "Python", "proficiency": "advanced"},
            {"skill_name": "SQL", "proficiency": "intermediate"},
            {"skill_name": "Machine Learning", "proficiency": "beginner"},
        ],
        "quiz_answers": {
            "q1": "b",
            "q2": "c",
            "q3": "a",
            "q4": "b",
            "q5": "b",
        },
    }

    res = client.post("/api/student/assessment", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "assessment" in data

    ast = data["assessment"]
    assert ast["id"].startswith("ast-usr-")
    assert ast["name"] == "Devendra Shinde"
    assert ast["education"] == "BE Artificial Intelligence & Data Science (3rd Year)"
    assert ast["career_goal"] == "AI Engineer"
    assert ast["district"] == "Pune"
    assert ast["source"] == "USER_SUBMITTED"
    assert ast["is_demo"] is False
    assert ast["data_provenance"] == "SELF_REPORTED_ASSESSMENT"

    # Evaluation calculations
    assert "quiz_score_pct" in ast
    assert ast["quiz_score_pct"] == 100  # selected all optimal options
    assert "skill_match_pct" in ast
    assert isinstance(ast["skill_match_pct"], int)
    assert "combined_readiness_score" in ast

    summary = ast["evaluation_summary"]
    assert "readiness_level" in summary
    assert "target_role" in summary
    assert "missing_skills" in summary
    assert isinstance(summary["missing_skills"], list)
    assert "recommended_next_steps" in summary
    assert len(summary["recommended_next_steps"]) >= 1


def test_submit_student_assessment_validation_errors():
    """POST /api/student/assessment rejects invalid or missing fields with 422."""
    # 1. Missing name
    res1 = client.post("/api/student/assessment", json={
        "education": "BCA",
        "career_goal": "Data Analyst",
    })
    assert res1.status_code == 422

    # 2. Name too short (min 2 chars)
    res2 = client.post("/api/student/assessment", json={
        "name": "A",
        "education": "BCA",
        "career_goal": "Data Analyst",
    })
    assert res2.status_code == 422

    # 3. Missing career goal
    res3 = client.post("/api/student/assessment", json={
        "name": "Devendra Shinde",
        "education": "BCA",
    })
    assert res3.status_code == 422


def test_list_student_assessments_with_source_filter():
    """GET /api/student/assessments returns records and separates user-submitted from demo data."""
    # First submit a user record
    client.post("/api/student/assessment", json={
        "name": "Ananya Kulkarni",
        "education": "Diploma in EV Technology",
        "district": "Nashik",
        "career_goal": "EV Technician",
        "interests": ["Electric Vehicles"],
        "current_skills": [{"skill_name": "Electrical Maintenance", "proficiency": "intermediate"}],
        "quiz_answers": {"q1": "b", "q2": "b"},
    })

    # Query all
    res_all = client.get("/api/student/assessments")
    assert res_all.status_code == 200
    data_all = res_all.json()
    assert "assessments" in data_all
    assert len(data_all["assessments"]) >= 1

    # Query only user-submitted
    res_user = client.get("/api/student/assessments?source=USER_SUBMITTED")
    assert res_user.status_code == 200
    for item in res_user.json()["assessments"]:
        assert item["source"] == "USER_SUBMITTED"
        assert item["is_demo"] is False

    # Query only demo-synthetic
    res_demo = client.get("/api/student/assessments?source=DEMO_SYNTHETIC")
    assert res_demo.status_code == 200
    for item in res_demo.json()["assessments"]:
        assert item["source"] == "DEMO_SYNTHETIC"
        assert item["is_demo"] is True


def test_get_student_assessment_by_id():
    from app.core.security import create_access_token
    from app.db import save_user

    user_id = "usr-p12-test-std"
    save_user({
        "id": user_id,
        "email": "tanmay@test.gov.in",
        "role": "STUDENT",
        "full_name": "Tanmay Joshi",
        "is_active": True,
    })
    token = create_access_token({"sub": user_id, "role": "STUDENT", "email": "tanmay@test.gov.in"})
    headers = {"Authorization": f"Bearer {token}"}

    sub_res = client.post("/api/student/assessment", json={
        "name": "Tanmay Joshi",
        "education": "B.Sc Computer Science",
        "career_goal": "Full Stack Developer",
        "interests": ["Web Development"],
        "current_skills": [{"skill_name": "React", "proficiency": "intermediate"}],
        "quiz_answers": {"q1": "b"},
    }, headers=headers)
    ast_id = sub_res.json()["assessment"]["id"]

    assert client.get(f"/api/student/assessment/{ast_id}").status_code == 401

    get_res = client.get(f"/api/student/assessment/{ast_id}", headers=headers)
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["assessment"]["id"] == ast_id
    assert data["assessment"]["name"] == "Tanmay Joshi"

    bad_res = client.get("/api/student/assessment/ast-nonexistent-999")
    assert bad_res.status_code == 404
