import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token


@pytest.fixture
def client():
    return TestClient(app)


def auth_header(user_dict: dict) -> dict[str, str]:
    token = create_access_token(data=user_dict)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers():
    return auth_header({
        "sub": "73e35d08-a564-4cd2-b503-a641a8a0a5aa",
        "email": "admin@skillsetu.gov.in",
        "role": "ADMIN",
    })


@pytest.fixture
def coep_headers():
    return auth_header({
        "sub": "usr-institute-001",
        "email": "institute@skillsetu.gov.in",
        "role": "INSTITUTE",
    })


@pytest.fixture
def vjti_headers():
    return auth_header({
        "sub": "usr-institute-002",
        "email": "institute2@skillsetu.gov.in",
        "role": "INSTITUTE",
    })


@pytest.fixture
def tcs_headers():
    return auth_header({
        "sub": "usr-employer-001",
        "email": "employer@skillsetu.gov.in",
        "role": "EMPLOYER",
    })


@pytest.fixture
def persistent_headers():
    return auth_header({
        "sub": "usr-employer-002",
        "email": "employer2@skillsetu.gov.in",
        "role": "EMPLOYER",
    })


@pytest.fixture
def gov_headers():
    return auth_header({
        "sub": "usr-gov-001",
        "email": "government@skillsetu.gov.in",
        "role": "GOVERNMENT",
    })


@pytest.fixture
def student_headers():
    return auth_header({
        "sub": "usr-student-001",
        "email": "student@skillsetu.gov.in",
        "role": "STUDENT",
    })


def test_create_placement_outcome_institute_success(client, coep_headers):
    payload = {
        "course_id": "cr-001",
        "candidate_id": "cand-test-01",
        "candidate_name": "Rohan Deshmukh",
        "role_title": "Junior Python Developer",
        "district": "Pune",
        "industry": "IT/ITES",
        "status": "TRAINING_COMPLETED",
        "skills_utilized": ["Python", "Machine Learning"],
    }
    resp = client.post("/api/placements/outcomes", json=payload, headers=coep_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "success"
    outcome = data["placement_outcome"]
    assert outcome["course_id"] == "cr-001"
    assert outcome["institute_id"] == "inst-coep"
    assert outcome["candidate_name"] == "Rohan Deshmukh"
    assert outcome["data_provenance"] == "INSTITUTE_AUTHORITATIVE"
    assert outcome["status"] == "TRAINING_COMPLETED"


def test_create_placement_outcome_forbidden_for_different_institute(client, vjti_headers):
    payload = {
        "course_id": "cr-001",
        "candidate_id": "cand-test-02",
        "candidate_name": "Sneha Kulkarni",
        "role_title": "AI Trainee",
    }
    resp = client.post("/api/placements/outcomes", json=payload, headers=vjti_headers)
    assert resp.status_code == 403
    assert "Forbidden" in resp.json()["detail"]


def test_list_placement_outcomes_with_scoping(client, coep_headers, admin_headers):
    resp_coep = client.get("/api/placements/outcomes", headers=coep_headers)
    assert resp_coep.status_code == 200
    data_coep = resp_coep.json()
    for o in data_coep["placement_outcomes"]:
        assert o["institute_id"] == "inst-coep"

    resp_admin = client.get("/api/placements/outcomes", headers=admin_headers)
    assert resp_admin.status_code == 200
    data_admin = resp_admin.json()
    assert data_admin["total_count"] >= len(data_coep["placement_outcomes"])


def test_get_placement_outcome_idor(client, vjti_headers, coep_headers, student_headers):
    c_resp = client.post("/api/placements/outcomes", json={
        "course_id": "cr-001",
        "candidate_id": "usr-student-001",
        "candidate_name": "Aarav Patil",
        "role_title": "Junior Python Dev",
        "status": "TRAINING_COMPLETED",
    }, headers=coep_headers)
    assert c_resp.status_code == 201
    created_id = c_resp.json()["placement_outcome"]["id"]

    resp_vjti = client.get(f"/api/placements/outcomes/{created_id}", headers=vjti_headers)
    assert resp_vjti.status_code == 403

    resp_stu_own = client.get(f"/api/placements/outcomes/{created_id}", headers=student_headers)
    assert resp_stu_own.status_code == 200
    assert resp_stu_own.json()["placement_outcome"]["candidate_id"] == "usr-student-001"


def test_update_placement_outcome_lifecycle(client, coep_headers):
    create_payload = {
        "course_id": "cr-001",
        "candidate_id": "cand-lifecycle-01",
        "candidate_name": "Ananya Joshi",
        "role_title": "Software Trainee",
        "status": "TRAINING_COMPLETED",
    }
    c_resp = client.post("/api/placements/outcomes", json=create_payload, headers=coep_headers)
    assert c_resp.status_code == 201
    oid = c_resp.json()["placement_outcome"]["id"]

    u_resp = client.patch(f"/api/placements/outcomes/{oid}", json={
        "status": "PLACED",
        "employer_id": "emp-001",
        "employer_name": "Tata Motors",
        "salary_annual_inr": 600000,
    }, headers=coep_headers)
    assert u_resp.status_code == 200
    assert u_resp.json()["placement_outcome"]["status"] == "PLACED"
    assert u_resp.json()["placement_outcome"]["salary_annual_inr"] == 600000

    inv_resp = client.patch(f"/api/placements/outcomes/{oid}", json={
        "status": "INVALID_STATE_XYZ",
    }, headers=coep_headers)
    assert inv_resp.status_code == 400


def test_submit_employer_feedback_success_and_idor(client, coep_headers, tcs_headers, persistent_headers, admin_headers):
    c_resp = client.post("/api/placements/outcomes", json={
        "course_id": "cr-001",
        "candidate_id": "cand-fb-01",
        "candidate_name": "Vikas Shinde",
        "role_title": "ML Engineer",
        "status": "PLACED",
        "employer_id": "emp-001",
        "employer_name": "Tata Motors",
    }, headers=coep_headers)
    assert c_resp.status_code == 201
    oid = c_resp.json()["placement_outcome"]["id"]

    fb_data = {
        "skill_adequacy_score": 4,
        "practical_readiness": "PRODUCTION_READY",
        "missing_skills": ["Docker", "Kubernetes"],
        "training_relevance": "HIGHLY_RELEVANT",
        "hiring_difficulty": "MODERATE",
        "feedback_notes": "Candidate exhibits strong fundamentals in Python and ML.",
    }

    wrong_resp = client.post(f"/api/placements/outcomes/{oid}/feedback", json=fb_data, headers=persistent_headers)
    assert wrong_resp.status_code == 403

    ok_resp = client.post(f"/api/placements/outcomes/{oid}/feedback", json=fb_data, headers=tcs_headers)
    assert ok_resp.status_code == 201
    fb_res = ok_resp.json()["feedback"]
    assert fb_res["skill_adequacy_score"] == 4
    assert fb_res["practical_readiness"] == "PRODUCTION_READY"
    assert "Docker" in fb_res["missing_skills"]
    assert fb_res["data_provenance"] in ("EMPLOYER_VERIFIED", "UNVERIFIED_EMPLOYER")

    o_after = client.get(f"/api/placements/outcomes/{oid}", headers=tcs_headers).json()["placement_outcome"]
    assert o_after["status"] == "FEEDBACK_RECEIVED"

    dup_resp = client.post(f"/api/placements/outcomes/{oid}/feedback", json=fb_data, headers=tcs_headers)
    assert dup_resp.status_code == 409

    unplaced_resp = client.post("/api/placements/outcomes", json={
        "course_id": "cr-001",
        "candidate_id": "cand-fb-02",
        "candidate_name": "Suresh Kale",
        "role_title": "Trainee",
        "status": "TRAINING_COMPLETED",
    }, headers=coep_headers)
    assert unplaced_resp.status_code == 201
    unplaced_oid = unplaced_resp.json()["placement_outcome"]["id"]

    unassigned_resp = client.post(f"/api/placements/outcomes/{unplaced_oid}/feedback", json=fb_data, headers=tcs_headers)
    assert unassigned_resp.status_code == 403

    lifecycle_resp = client.post(f"/api/placements/outcomes/{unplaced_oid}/feedback", json=fb_data, headers=admin_headers)
    assert lifecycle_resp.status_code == 400


def test_course_placement_performance_intelligence(client):
    resp = client.get("/api/placements/course/cr-001/performance")
    assert resp.status_code == 200
    perf = resp.json()["performance"]
    assert perf["course_id"] == "cr-001"
    assert perf["total_candidates_tracked"] >= 3
    assert "placement_rate_pct" in perf
    assert perf["confidence_tier"] in ("HIGH", "MODERATE", "LOW")
    assert "feedback_summary" in perf
    assert "employer_reported_missing_skills" in perf["feedback_summary"]


def test_skill_placement_signals(client):
    resp = client.get("/api/placements/analytics/skills")
    assert resp.status_code == 200
    signals = resp.json()["skill_signals"]
    assert "most_placed_skills" in signals
    assert "employer_reported_deficits" in signals
    assert signals["total_outcomes_analyzed"] >= 0


def test_statewide_placement_analytics_rbac(client, gov_headers, student_headers):
    resp_stu = client.get("/api/placements/analytics/statewide", headers=student_headers)
    assert resp_stu.status_code == 403

    resp_gov = client.get("/api/placements/analytics/statewide", headers=gov_headers)
    assert resp_gov.status_code == 200
    data = resp_gov.json()["analytics"]
    assert "overall_placement_rate_pct" in data
    assert "district_breakdown" in data
    assert "industry_breakdown" in data
    assert "top_performing_courses" in data


def test_curriculum_modernization_integrates_placement_feedback(client):
    audit_resp = client.get("/api/curriculum/audit")
    assert audit_resp.status_code == 200
    courses = audit_resp.json()["courses"]
    cr001 = next((c for c in courses if c["course_id"] == "cr-001"), None)
    assert cr001 is not None
    ev = cr001["evidence_summary"]
    assert "placement_outcomes_count" in ev
    assert "placement_feedback_count" in ev
    assert "employer_reported_missing_skills" in ev

    blueprint_resp = client.get("/api/curriculum/recommendations/cr-001")
    assert blueprint_resp.status_code == 200
    bp = blueprint_resp.json()
    action_plan = bp["modernization_blueprint"]["action_plan"]
    assert len(action_plan) > 0
    if ev.get("employer_reported_missing_skills"):
        first_step = action_plan[0]
        assert "Competency Alignment" in first_step.get("phase", "") or "Competency" in first_step.get("title", "")
