import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token
from app.services.accreditation_service import (
    determine_accreditation_tier,
    calculate_training_roi,
    get_evidence_confidence_tier,
    compute_institute_scorecard,
    compute_district_roi_analytics,
)


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
def gov_headers():
    return auth_header({
        "sub": "usr-gov-001",
        "email": "government@skillsetu.gov.in",
        "role": "GOVERNMENT",
    })


@pytest.fixture
def coep_headers():
    return auth_header({
        "sub": "usr-institute-001",
        "email": "institute@skillsetu.gov.in",
        "role": "INSTITUTE",
        "organization_id": "inst-coep",
    })


@pytest.fixture
def vjti_headers():
    return auth_header({
        "sub": "usr-institute-002",
        "email": "institute2@skillsetu.gov.in",
        "role": "INSTITUTE",
        "organization_id": "inst-vjti",
    })


@pytest.fixture
def student_headers():
    return auth_header({
        "sub": "usr-student-001",
        "email": "student@skillsetu.gov.in",
        "role": "STUDENT",
    })


def test_accreditation_tier_boundaries():
    assert determine_accreditation_tier(88.5, 80.0, 25) == "TIER_1_EXCELLENCE"
    assert determine_accreditation_tier(85.0, 75.0, 15) == "TIER_1_EXCELLENCE"
    assert determine_accreditation_tier(84.9, 75.0, 15) == "TIER_2_ACCREDITED"
    assert determine_accreditation_tier(70.0, 65.0, 12) == "TIER_2_ACCREDITED"
    assert determine_accreditation_tier(69.9, 65.0, 12) == "TIER_3_PROVISIONAL"
    assert determine_accreditation_tier(55.0, 50.0, 10) == "TIER_3_PROVISIONAL"
    assert determine_accreditation_tier(54.9, 50.0, 10) == "TIER_4_PERFORMANCE_WATCH"
    assert determine_accreditation_tier(40.0, 30.0, 10) == "TIER_4_PERFORMANCE_WATCH"


def test_sample_quorum_safeguard():
    assert determine_accreditation_tier(92.0, 90.0, 5) == "TIER_3_PROVISIONAL"
    assert determine_accreditation_tier(86.0, 85.0, 9) == "TIER_3_PROVISIONAL"
    assert determine_accreditation_tier(45.0, 40.0, 5) == "TIER_4_PERFORMANCE_WATCH"


def test_placement_under_45_rule():
    assert determine_accreditation_tier(88.0, 44.9, 20) == "TIER_4_PERFORMANCE_WATCH"
    assert determine_accreditation_tier(86.0, 30.0, 50) == "TIER_4_PERFORMANCE_WATCH"


def test_evidence_confidence_tiers():
    assert get_evidence_confidence_tier(0) == "INSUFFICIENT_EVIDENCE"
    assert get_evidence_confidence_tier(4) == "LOW"
    assert get_evidence_confidence_tier(9) == "MODERATE"
    assert get_evidence_confidence_tier(10) == "HIGH"
    assert get_evidence_confidence_tier(50) == "HIGH"


def test_roi_mathematics():
    roi = calculate_training_roi(
        placed_count=40,
        average_salary_inr=500000,
        total_students=50,
        capital_grants_inr=250000,
    )
    assert roi["annual_economic_output_inr"] == 20000000
    assert roi["operational_training_cost_inr"] == 1750000
    assert roi["public_training_investment_inr"] == 2000000
    assert roi["net_economic_benefit_inr"] == 18000000
    assert roi["roi_multiplier"] == 10.0
    assert roi["payback_period_months"] == 1.2


def test_roi_zero_division_safety():
    roi = calculate_training_roi(
        placed_count=0,
        average_salary_inr=0,
        total_students=0,
        capital_grants_inr=0,
    )
    assert roi["annual_economic_output_inr"] == 0
    assert roi["public_training_investment_inr"] == 0
    assert roi["roi_multiplier"] == 0.0
    assert roi["payback_period_months"] == 0.0


def test_compute_institute_scorecard_structure():
    scorecard = compute_institute_scorecard("inst-coep", is_demo=True)
    assert scorecard["institute_id"] == "inst-coep"
    assert "composite_score" in scorecard
    assert "accreditation_tier" in scorecard
    assert "dimension_breakdown" in scorecard
    assert "roi_metrics" in scorecard
    assert "retention_metrics" in scorecard

    breakdown = scorecard["dimension_breakdown"]
    assert "placement_employment_rate" in breakdown
    assert "curriculum_modernity" in breakdown
    assert "employer_readiness_feedback" in breakdown
    assert "wage_premium" in breakdown


def test_compute_district_roi_analytics():
    analytics = compute_district_roi_analytics(is_demo=True)
    assert "districts_analyzed" in analytics
    assert "statewide_summary" in analytics
    assert "district_leaderboard" in analytics
    assert analytics["districts_analyzed"] > 0
    assert analytics["statewide_summary"]["statewide_roi_multiplier"] > 0


def test_retention_status_in_placement_lifecycle(client, coep_headers):
    create_payload = {
        "course_id": "cr-001",
        "candidate_name": "Siddharth Shinde",
        "role_title": "Junior Automation Engineer",
        "district": "Pune",
        "industry": "Manufacturing",
        "status": "PLACED",
        "retention_status": "6_MONTH_RETAINED",
        "salary_annual_inr": 480000,
    }
    create_res = client.post("/api/placements/outcomes", json=create_payload, headers=coep_headers)
    assert create_res.status_code == 201
    created_id = create_res.json()["placement_outcome"]["id"]
    assert create_res.json()["placement_outcome"]["retention_status"] == "6_MONTH_RETAINED"

    update_payload = {
        "retention_status": "12_MONTH_RETAINED",
    }
    update_res = client.patch(f"/api/placements/outcomes/{created_id}", json=update_payload, headers=coep_headers)
    assert update_res.status_code == 200
    assert update_res.json()["placement_outcome"]["retention_status"] == "12_MONTH_RETAINED"


def test_invalid_retention_status_rejected(client, coep_headers):
    invalid_payload = {
        "course_id": "cr-001",
        "candidate_name": "Invalid Candidate",
        "role_title": "Test Role",
        "retention_status": "INVALID_STATUS",
    }
    res = client.post("/api/placements/outcomes", json=invalid_payload, headers=coep_headers)
    assert res.status_code == 422


def test_list_accredited_institutes(client):
    res = client.get("/api/accreditation/institutes?is_demo=true")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "tier_distribution" in data
    assert "accreditations" in data
    assert len(data["accreditations"]) > 0


def test_get_institute_scorecard_endpoint(client):
    res = client.get("/api/accreditation/institutes/inst-coep?is_demo=true")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["scorecard"]["institute_id"] == "inst-coep"


def test_evaluate_institute_accreditation_rbac(client, gov_headers, coep_headers, student_headers):
    res_gov = client.post("/api/accreditation/institutes/inst-coep/evaluate?is_demo=true", headers=gov_headers)
    assert res_gov.status_code == 200
    assert res_gov.json()["status"] == "success"
    assert res_gov.json()["accreditation"]["data_provenance"] == "STATE_DETERMINISTIC_ACCREDITATION"

    res_inst = client.post("/api/accreditation/institutes/inst-coep/evaluate?is_demo=true", headers=coep_headers)
    assert res_inst.status_code == 403

    res_stu = client.post("/api/accreditation/institutes/inst-coep/evaluate?is_demo=true", headers=student_headers)
    assert res_stu.status_code == 403


def test_audit_notice_lifecycle_and_rbac(client, gov_headers, coep_headers, vjti_headers, student_headers):
    notice_payload = {
        "notice_type": "PERFORMANCE_WARNING",
        "severity": "HIGH",
        "title": "Placement Benchmark Warning",
        "description": "Graduating batch conversion is below state standard.",
        "mandated_action": "Submit curriculum revision proposal.",
        "deadline_date": "2026-12-31",
    }
    create_res = client.post("/api/accreditation/institutes/inst-coep/notices", json=notice_payload, headers=gov_headers)
    assert create_res.status_code == 201
    notice_id = create_res.json()["audit_notice"]["id"]

    inst_fail = client.post("/api/accreditation/institutes/inst-coep/notices", json=notice_payload, headers=coep_headers)
    assert inst_fail.status_code == 403

    view_own = client.get("/api/accreditation/institutes/inst-coep/notices", headers=coep_headers)
    assert view_own.status_code == 200
    assert any(n["id"] == notice_id for n in view_own.json()["audit_notices"])

    view_other_idor = client.get("/api/accreditation/institutes/inst-coep/notices", headers=vjti_headers)
    assert view_other_idor.status_code == 403

    view_stu = client.get("/api/accreditation/institutes/inst-coep/notices", headers=student_headers)
    assert view_stu.status_code == 403

    patch_inst = client.patch(f"/api/accreditation/notices/{notice_id}", json={"status": "IN_REMEDIATION"}, headers=coep_headers)
    assert patch_inst.status_code == 200
    assert patch_inst.json()["audit_notice"]["status"] == "IN_REMEDIATION"

    patch_inst_invalid = client.patch(f"/api/accreditation/notices/{notice_id}", json={"status": "RESOLVED"}, headers=coep_headers)
    assert patch_inst_invalid.status_code == 403

    patch_gov = client.patch(f"/api/accreditation/notices/{notice_id}", json={"status": "RESOLVED"}, headers=gov_headers)
    assert patch_gov.status_code == 200
    assert patch_gov.json()["audit_notice"]["status"] == "RESOLVED"


def test_district_and_statewide_roi_endpoints(client):
    res_districts = client.get("/api/analytics/roi/districts?is_demo=true")
    assert res_districts.status_code == 200
    assert "district_leaderboard" in res_districts.json()["roi_analytics"]

    res_single = client.get("/api/analytics/roi/districts/Pune?is_demo=true")
    assert res_single.status_code == 200
    assert res_single.json()["district_roi"]["district"] == "Pune"

    res_state = client.get("/api/analytics/roi/statewide?is_demo=true")
    assert res_state.status_code == 200
    assert "statewide_summary" in res_state.json()
