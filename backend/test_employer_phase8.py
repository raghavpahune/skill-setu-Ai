import pytest
from starlette.testclient import TestClient
from app.main import app
from app.core.security import create_access_token
from app.db import init_db, init_demo_users

init_db()
init_demo_users()
client = TestClient(app)
EMPLOYER_TOKEN = create_access_token({"sub": "usr-employer-001", "email": "employer@skillsetu.gov.in", "role": "EMPLOYER"})
AUTH_HEADERS = {"Authorization": f"Bearer {EMPLOYER_TOKEN}"}


def test_employer_validate_endpoint():
    """Test /api/employer/validate returns enriched validation list and supports filtering."""
    res = client.get("/api/employer/validate")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) > 0

    first = data[0]
    assert "id" in first
    assert "skill_id" in first
    assert "skill_name" in first
    assert "employer_name" in first
    assert "demand_level" in first
    assert "status" in first

    # Test filtering by status
    res_confirmed = client.get("/api/employer/validate?status=confirmed")
    assert res_confirmed.status_code == 200
    for item in res_confirmed.json():
        assert item["status"].lower() == "confirmed"

    # Test filtering by district
    res_pune = client.get("/api/employer/validate?district=pune")
    assert res_pune.status_code == 200
    for item in res_pune.json():
        assert item["district"].lower() == "pune"


def test_employer_feedback_submission():
    """Test /api/employer/feedback accepts confirm, correct, and reject payloads."""
    # Get a valid feedback ID
    vals = client.get("/api/employer/validate").json()
    assert len(vals) > 0
    target_id = vals[0]["id"]

    # 1. Test Confirm
    payload_confirm = {
        "feedback_id": target_id,
        "status": "confirmed",
        "notes": "Verified by industrial hiring committee.",
    }
    res_confirm = client.post("/api/employer/feedback", json=payload_confirm, headers=AUTH_HEADERS)
    assert res_confirm.status_code == 200
    data_confirm = res_confirm.json()
    assert data_confirm.get("status") == "updated"
    assert data_confirm.get("feedback", {}).get("status") == "confirmed"

    # 2. Test Correct
    payload_correct = {
        "feedback_id": target_id,
        "status": "corrected",
        "notes": "Requires production RAG pipeline capstone.",
        "proficiency_required": "advanced",
    }
    res_correct = client.post("/api/employer/feedback", json=payload_correct, headers=AUTH_HEADERS)
    assert res_correct.status_code == 200
    data_correct = res_correct.json()
    assert data_correct.get("status") == "updated"
    assert data_correct.get("feedback", {}).get("status") == "corrected"
    assert data_correct.get("feedback", {}).get("proficiency_required") == "advanced"

    res_404 = client.post(
        "/api/employer/feedback",
        json={"feedback_id": "non-existent-999", "status": "confirmed"},
        headers=AUTH_HEADERS,
    )
    assert res_404.status_code == 404
    assert "not found" in res_404.json().get("detail", "").lower()

    student_token = create_access_token({"sub": "usr-student-001", "email": "student@skillsetu.gov.in", "role": "STUDENT"})
    res_forbidden = client.post(
        "/api/employer/feedback",
        json={"feedback_id": target_id, "status": "confirmed"},
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert res_forbidden.status_code == 403


def test_employer_demand_submission_and_retrieval():
    """Test /api/employer/demand for posting new requirements and /api/employer/demands for retrieval."""
    new_demand = {
        "employer_name": "Persistent Systems AI Division",
        "industry": "IT/ITES",
        "district": "Pune",
        "role_title": "Enterprise Vector DB & LLMOps Architect",
        "skills": ["Generative AI", "RAG", "Kubernetes", "Vector Databases"],
        "proficiency_required": "advanced",
        "nsqf_level": 7,
        "urgency": "immediate",
        "positions_count": 20,
        "hiring_challenge": "Candidates lack hands-on experience with production vector index tuning.",
    }

    # Submit demand
    res_post = client.post("/api/employer/demand", json=new_demand, headers=AUTH_HEADERS)
    assert res_post.status_code == 200
    res_data = res_post.json()
    assert res_data.get("status") == "created"
    saved = res_data.get("demand", {})
    assert saved.get("id", "").startswith("ed-")
    assert saved.get("role_title") == new_demand["role_title"]
    assert saved.get("positions_count") == 20

    # Retrieve demands
    res_list = client.get("/api/employer/demands")
    assert res_list.status_code == 200
    demands_list = res_list.json()
    assert isinstance(demands_list, list)
    assert any(d.get("id") == saved.get("id") for d in demands_list)

    # Filter demands by district
    res_pune = client.get("/api/employer/demands?district=pune")
    assert res_pune.status_code == 200
    for d in res_pune.json():
        assert d.get("district", "").lower() == "pune"


def test_employer_difficult_skills_endpoint():
    """Test /api/employer/difficult-skills returns hard-to-hire competencies with metrics."""
    res = client.get("/api/employer/difficult-skills")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) > 0

    first = data[0]
    assert "skill_name" in first
    assert "deficit_score" in first
    assert "avg_days_to_fill" in first
    assert "shortage_reason" in first
    assert "suggested_intervention" in first
    assert isinstance(first["deficit_score"], (int, float))


def test_employer_summary_endpoint():
    """Test /api/employer/summary returns telemetry KPIs and consensus statistics."""
    res = client.get("/api/employer/summary")
    assert res.status_code == 200
    summary = res.json()

    assert "total_validations" in summary
    assert "confirmed_count" in summary
    assert "pending_count" in summary
    assert "approval_rate" in summary
    assert "active_employers_count" in summary
    assert "hard_to_hire_count" in summary
    assert "top_industries" in summary

    assert isinstance(summary["approval_rate"], (int, float))
    assert summary["active_employers_count"] > 0
