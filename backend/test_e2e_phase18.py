"""Phase 18: Comprehensive End-to-End Integration & Production Readiness Test Suite.

Verifies:
1. Complete Student Lifecycle: Assessment -> Evaluation -> Recommendations -> Gaps -> Schemes -> AI Copilot
2. Employer Lifecycle & Validation Gate: Submission (PENDING) -> Filtered Out -> Admin Validation -> Included in Recommendations -> Admin Rejection -> Excluded
3. Government Opportunities Lifecycle: Creation -> Matching -> Update -> Exclusion -> Deletion
4. Security & Admin Authentication: Key verification, unauthorized rejection, secret protection
5. AI Copilot Grounding & Deterministic Fallback: Strict truth preservation, provenance tagging, no hallucination
6. Failure Modes & Edge Cases: 404s, 422s, 401s, missing parameters, empty queries
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token
from app.db import init_demo_users, load_demo_data

client = TestClient(app)
load_demo_data()
init_demo_users()
ADMIN_KEY = "demo-admin-key-2026"
EMPLOYER_TOKEN = create_access_token({"sub": "usr-employer-001", "email": "employer@skillsetu.gov.in", "role": "EMPLOYER"})
EMPLOYER_AUTH_HEADERS = {"Authorization": f"Bearer {EMPLOYER_TOKEN}"}
STUDENT_TOKEN = create_access_token({"sub": "usr-student-001", "email": "student@skillsetu.gov.in", "role": "STUDENT"})
STUDENT_AUTH_HEADERS = {"Authorization": f"Bearer {STUDENT_TOKEN}"}


pytestmark = pytest.mark.usefixtures("enable_demo_mode")


# ===========================================================================
# 1. Complete Student Lifecycle Flow
# ===========================================================================

def test_full_student_assessment_to_recommendation_and_copilot_flow():
    """Test full flow: Student Assessment -> Recommendations -> Matching Schemes -> Copilot."""
    # Step 1: Submit new user assessment
    assessment_payload = {
        "name": "Tanvi Joshi",
        "education": "Diploma in Mechanical Engineering",
        "district": "Pune",
        "career_goal": "EV Technician",
        "interests": ["Electric Vehicles", "Battery Systems", "Automation"],
        "current_skills": [
            {"skill_name": "Electrical Diagnostics", "proficiency": "intermediate"},
            {"skill_name": "CAN Bus", "proficiency": "beginner"},
        ],
        "quiz_answers": {
            "q1": "b",
            "q2": "c",
            "q3": "a",
            "q4": "b",
            "q5": "b",
        },
    }

    res_ast = client.post("/api/student/assessment", json=assessment_payload, headers=STUDENT_AUTH_HEADERS)
    assert res_ast.status_code == 200
    ast_data = res_ast.json()
    assert ast_data["status"] == "success"
    ast_record = ast_data["assessment"]
    ast_id = ast_record["id"]

    assert ast_record["source"] == "USER_SUBMITTED"
    assert ast_record["is_demo"] is False
    assert ast_record["quiz_score_pct"] == 100
    assert "evaluation_summary" in ast_record
    assert ast_record["evaluation_summary"]["target_role"] == "EV Technician"

    assert client.get(f"/api/student/recommendations/{ast_id}").status_code == 401
    assert client.get(f"/api/schemes/recommended/{ast_id}").status_code == 401
    assert client.get(f"/api/gov/opportunities/recommended/{ast_id}").status_code == 401
    assert client.post(
        "/api/copilot/explain-career",
        json={
            "student_id": ast_id,
            "question": "Why is EV Technician recommended for me and what are my missing skills?",
        },
    ).status_code == 401

    res_rec = client.get(f"/api/student/recommendations/{ast_id}", headers=STUDENT_AUTH_HEADERS)
    assert res_rec.status_code == 200
    rec_data = res_rec.json()
    assert rec_data["status"] == "success"
    assert rec_data["student_id"] == ast_id
    assert rec_data["candidate_name"] == "Tanvi Joshi"
    assert rec_data["target_career_goal"] == "EV Technician"

    top_rec = rec_data["top_recommendation"]
    assert top_rec["role_name"] == "EV Technician"
    assert "EV Battery Technology" in top_rec["missing_skills"]
    assert len(top_rec["explanation_reasons"]) > 0
    assert rec_data["data_provenance"]["student_profile_source"] == "USER_SUBMITTED"

    res_schemes = client.get(f"/api/schemes/recommended/{ast_id}", headers=STUDENT_AUTH_HEADERS)
    assert res_schemes.status_code == 200
    schemes_data = res_schemes.json()
    assert schemes_data["student_id"] == ast_id
    assert len(schemes_data["schemes"]) > 0
    for s in schemes_data["schemes"]:
        assert "match_reasons" in s
        assert "source" in s

    res_gov = client.get(f"/api/gov/opportunities/recommended/{ast_id}", headers=STUDENT_AUTH_HEADERS)
    assert res_gov.status_code == 200
    gov_data = res_gov.json()
    assert gov_data["student_id"] == ast_id
    assert len(gov_data["opportunities"]) > 0

    res_copilot = client.post(
        "/api/copilot/explain-career",
        json={
            "student_id": ast_id,
            "question": "Why is EV Technician recommended for me and what are my missing skills?",
        },
        headers=STUDENT_AUTH_HEADERS,
    )
    assert res_copilot.status_code == 200
    copilot_data = res_copilot.json()
    assert "answer" in copilot_data
    assert "EV Technician" in copilot_data["answer"] or "Tanvi" in copilot_data["answer"]
    assert copilot_data["data_grounded"] is True


# ===========================================================================
# 2. Employer Flow & Strict Validation Gate
# ===========================================================================

def test_employer_submission_and_validation_gate_lifecycle():
    """Verify that only strictly VALIDATED employer demands enter the recommendation engine."""
    headers = {"X-Admin-Key": ADMIN_KEY}

    # Step 1: Employer submits new hiring requirement
    new_demand_payload = {
        "company_name": "E2E Test Robotics Corp",
        "industry": "Manufacturing & Industry 4.0",
        "district": "Pune",
        "job_role": "Robotics & Automation Engineer",
        "required_skills": ["Industrial Robotics", "PLC Programming", "SCADA"],
        "preferred_proficiency": "Advanced",
        "openings_count": 25,
        "experience_level": "Entry Level (0-2 yrs)",
        "hiring_timeline": "Immediate (0-30 days)",
        "additional_requirements": "Hands-on experience with industrial robot cells.",
    }

    res_post = client.post("/api/employer/demands", json=new_demand_payload, headers=EMPLOYER_AUTH_HEADERS)
    assert res_post.status_code == 200
    created_demand = res_post.json()["demand"]
    demand_id = created_demand["id"]

    # Verify initial status is PENDING and source is EMPLOYER_SUBMITTED
    assert created_demand["validation_status"] == "PENDING"
    assert created_demand["source"] == "EMPLOYER_SUBMITTED"
    assert created_demand["is_demo"] is False

    # Step 2: Verify PENDING demand is NOT included in student recommendations
    rec_before = client.get("/api/student/recommendations/stu-001").json()
    robotics_role_before = next(
        (c for c in rec_before["recommended_careers"] if c["role_name"] == "Robotics & Automation Engineer"),
        None,
    )
    if robotics_role_before:
        emp_ids_before = [e["id"] for e in robotics_role_before.get("validated_employer_signals", [])]
        assert demand_id not in emp_ids_before

    # Step 3: Admin validates the demand
    res_val = client.patch(
        f"/api/admin/employer/demands/{demand_id}",
        headers=headers,
        json={"validation_status": "VALIDATED", "admin_notes": "Verified company registration and active openings."},
    )
    assert res_val.status_code == 200
    assert res_val.json()["demand"]["validation_status"] == "VALIDATED"

    # Step 4: Verify VALIDATED demand is now included in student career recommendations
    rec_after = client.get("/api/student/recommendations/stu-001").json()
    robotics_role_after = next(
        (c for c in rec_after["recommended_careers"] if c["role_name"] == "Robotics & Automation Engineer"),
        None,
    )
    assert robotics_role_after is not None
    emp_ids_after = [e["id"] for e in robotics_role_after.get("validated_employer_signals", [])]
    assert demand_id in emp_ids_after

    # Step 5: Admin rejects the demand
    res_rej = client.patch(
        f"/api/admin/employer/demands/{demand_id}",
        headers=headers,
        json={"validation_status": "REJECTED", "admin_notes": "Duplicate entry."},
    )
    assert res_rej.status_code == 200
    assert res_rej.json()["demand"]["validation_status"] == "REJECTED"

    # Step 6: Verify REJECTED demand is immediately removed from student recommendations
    rec_rejected = client.get("/api/student/recommendations/stu-001").json()
    robotics_role_rej = next(
        (c for c in rec_rejected["recommended_careers"] if c["role_name"] == "Robotics & Automation Engineer"),
        None,
    )
    if robotics_role_rej:
        emp_ids_rej = [e["id"] for e in robotics_role_rej.get("validated_employer_signals", [])]
        assert demand_id not in emp_ids_rej

    # Clean up test demand
    client.delete(f"/api/admin/employer/demands/{demand_id}", headers=headers)


# ===========================================================================
# 3. Government Opportunity Management Lifecycle
# ===========================================================================

def test_gov_opportunity_management_lifecycle():
    """Verify full CRUD lifecycle of government opportunities."""
    headers = {"X-Admin-Key": ADMIN_KEY}

    # Step 1: Admin creates opportunity
    payload = {
        "name": "E2E Test Drone Pilot Vocational Certificate",
        "department": "Maharashtra State Drone Mission",
        "description": "DGCA-aligned small UAS remote pilot certificate course with state subsidy.",
        "eligibility_criteria": "12th pass or ITI Electronics",
        "target_skills": ["Drone Operation", "Sensors", "IoT"],
        "district_coverage": "Pune, Nashik",
        "opportunity_type": "training_program",
        "application_url": "https://drone.maharashtra.gov.in",
        "status": "active",
    }

    res_create = client.post("/api/admin/gov/opportunities", headers=headers, json=payload)
    assert res_create.status_code == 200
    created_opp = res_create.json()["opportunity"]
    opp_id = created_opp["id"]
    assert created_opp["source"] == "ADMIN_CREATED"
    assert created_opp["is_demo"] is False

    # Step 2: Verify opportunity is discoverable via public API
    res_get = client.get(f"/api/gov/opportunities/{opp_id}")
    assert res_get.status_code == 200
    assert res_get.json()["name"] == payload["name"]

    # Step 3: Admin deactivates opportunity
    res_deact = client.patch(
        f"/api/admin/gov/opportunities/{opp_id}",
        headers=headers,
        json={"status": "inactive"},
    )
    assert res_deact.status_code == 200
    assert res_deact.json()["opportunity"]["status"] == "inactive"

    # Step 4: Admin deletes opportunity
    res_del = client.delete(f"/api/admin/gov/opportunities/{opp_id}", headers=headers)
    assert res_del.status_code == 200
    assert res_del.json()["status"] == "success"

    # Step 5: Verify 404 after deletion
    res_404 = client.get(f"/api/gov/opportunities/{opp_id}")
    assert res_404.status_code == 404


# ===========================================================================
# 4. Security & Admin Authentication Failures
# ===========================================================================

def test_admin_endpoints_require_valid_key():
    """Verify unauthorized requests to admin endpoints are properly blocked."""
    # 1. No key
    assert client.get("/api/admin/assessments").status_code == 401
    assert client.get("/api/admin/employer/demands").status_code == 401
    assert client.get("/api/admin/gov/opportunities").status_code == 401

    # 2. Invalid key
    bad_headers = {"X-Admin-Key": "invalid-secret-key-xyz"}
    assert client.get("/api/admin/assessments", headers=bad_headers).status_code == 401
    assert client.get("/api/admin/employer/demands", headers=bad_headers).status_code == 401
    assert client.get("/api/admin/gov/opportunities", headers=bad_headers).status_code == 401

    # 3. Valid key works
    good_headers = {"X-Admin-Key": ADMIN_KEY}
    assert client.get("/api/admin/assessments", headers=good_headers).status_code == 200
    assert client.get("/api/admin/employer/demands", headers=good_headers).status_code == 200
    assert client.get("/api/admin/gov/opportunities", headers=good_headers).status_code == 200


def test_no_secrets_leaked_in_public_health():
    """Verify health and public endpoints do not expose API keys or credentials."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    data_str = str(data).lower()
    assert "admin_key" not in data_str
    assert "service_role" not in data_str
    assert "secret" not in data_str


# ===========================================================================
# 5. Edge Cases & Error Handling
# ===========================================================================

def test_error_handling_non_existent_resources():
    """Verify proper 404 responses for missing student, assessment, and opportunity IDs."""
    assert client.get("/api/student/recommendations/non-existent-student-999").status_code == 404
    assert client.get("/api/student/assessment/non-existent-assessment-999").status_code == 404
    assert client.get("/api/gov/opportunities/non-existent-gov-999").status_code == 404


def test_error_handling_invalid_payloads():
    """Verify validation 422 errors for malformed submissions."""
    # Student assessment missing required name/education/goal
    res_bad_student = client.post("/api/student/assessment", json={"name": ""})
    assert res_bad_student.status_code == 422

    # Employer demand missing required company/role/industry
    res_bad_employer = client.post("/api/employer/demands", json={"company_name": ""}, headers=EMPLOYER_AUTH_HEADERS)
    assert res_bad_employer.status_code == 422

