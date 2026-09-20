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
    assert determine_accreditation_tier(88.0, 74.9, 20) == "TIER_2_ACCREDITED"
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

    res_p1 = client.get("/api/accreditation/institutes?is_demo=true&limit=2&offset=0")
    assert res_p1.status_code == 200
    p1_data = res_p1.json()
    assert len(p1_data["accreditations"]) == 2

    res_p2 = client.get("/api/accreditation/institutes?is_demo=true&limit=2&offset=2")
    assert res_p2.status_code == 200
    p2_data = res_p2.json()
    p1_ids = [a["institute_id"] for a in p1_data["accreditations"]]
    p2_ids = [a["institute_id"] for a in p2_data["accreditations"]]
    assert not any(i in p1_ids for i in p2_ids)


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

    patch_inst = client.patch(
        f"/api/accreditation/notices/{notice_id}",
        json={"status": "IN_REMEDIATION", "remediation_notes": "Procured 5 new CNC simulation benches and scheduled faculty training."},
        headers=coep_headers,
    )
    assert patch_inst.status_code == 200
    assert patch_inst.json()["audit_notice"]["status"] == "IN_REMEDIATION"
    assert patch_inst.json()["audit_notice"]["remediation_notes"] == "Procured 5 new CNC simulation benches and scheduled faculty training."

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


def test_real_demo_isolation_accreditation_and_roi():
    from app.db import _cache
    inst_id = "inst-isolation-test"
    course_real = {
        "id": "cr-iso-real",
        "institute_id": inst_id,
        "institute": "Isolation Test Institute Real",
        "district": "Nashik",
        "is_demo": False,
        "source": "INSTITUTE_SUBMITTED",
        "enrolment_count": 30,
    }
    course_demo = {
        "id": "cr-iso-demo",
        "institute_id": inst_id,
        "institute": "Isolation Test Institute Demo",
        "district": "Nashik",
        "is_demo": True,
        "source": "DEMO_SYNTHETIC",
        "enrolment_count": 50,
    }
    outcome_real = {
        "id": "po-iso-real",
        "course_id": "cr-iso-real",
        "institute_id": inst_id,
        "district": "Nashik",
        "status": "PLACED",
        "verification_status": "VERIFIED",
        "salary_annual_inr": 400000,
        "is_demo": False,
        "source": "INSTITUTE_SUBMITTED",
    }
    outcome_demo = {
        "id": "po-iso-demo",
        "course_id": "cr-iso-demo",
        "institute_id": inst_id,
        "district": "Nashik",
        "status": "PLACED",
        "verification_status": "VERIFIED",
        "salary_annual_inr": 900000,
        "is_demo": True,
        "source": "DEMO_SYNTHETIC",
    }

    _cache.setdefault("courses", []).extend([course_real, course_demo])
    _cache.setdefault("placement_outcomes", []).extend([outcome_real, outcome_demo])

    try:
        scorecard_real = compute_institute_scorecard(inst_id, is_demo=False)
        scorecard_demo = compute_institute_scorecard(inst_id, is_demo=True)
        scorecard_default = compute_institute_scorecard(inst_id, is_demo=None)

        assert scorecard_real["dimension_breakdown"]["placement_employment_rate"]["placed_candidates"] == 1
        assert scorecard_real["dimension_breakdown"]["wage_premium"]["average_salary_inr"] == 400000

        assert scorecard_demo["dimension_breakdown"]["placement_employment_rate"]["placed_candidates"] == 1
        assert scorecard_demo["dimension_breakdown"]["wage_premium"]["average_salary_inr"] == 900000

        assert scorecard_default["dimension_breakdown"]["wage_premium"]["average_salary_inr"] == 400000

        roi_real = compute_district_roi_analytics("Nashik", is_demo=False)
        roi_demo = compute_district_roi_analytics("Nashik", is_demo=True)

        nashik_real = next((d for d in roi_real["district_leaderboard"] if d["district"] == "Nashik"), None)
        nashik_demo = next((d for d in roi_demo["district_leaderboard"] if d["district"] == "Nashik"), None)

        assert nashik_real is not None
        assert nashik_demo is not None
        assert nashik_real["placed_candidates"] >= 1
        assert nashik_demo["placed_candidates"] >= 1
    finally:
        _cache["courses"] = [c for c in _cache["courses"] if c.get("id") not in ("cr-iso-real", "cr-iso-demo")]
        _cache["placement_outcomes"] = [o for o in _cache["placement_outcomes"] if o.get("id") not in ("po-iso-real", "po-iso-demo")]


def test_unverified_placement_outcomes_excluded_from_accreditation():
    from app.db import _cache
    inst_id = "inst-verif-test"
    course = {
        "id": "cr-verif-test",
        "institute_id": inst_id,
        "institute": "Verification Test Institute",
        "district": "Pune",
        "is_demo": True,
        "source": "DEMO_SYNTHETIC",
        "enrolment_count": 20,
    }
    po_verified = {
        "id": "po-vt-verified",
        "course_id": "cr-verif-test",
        "institute_id": inst_id,
        "district": "Pune",
        "status": "PLACED",
        "verification_status": "VERIFIED",
        "salary_annual_inr": 500000,
        "is_demo": True,
        "source": "DEMO_SYNTHETIC",
    }
    po_pending = {
        "id": "po-vt-pending",
        "course_id": "cr-verif-test",
        "institute_id": inst_id,
        "district": "Pune",
        "status": "PLACED",
        "verification_status": "PENDING",
        "salary_annual_inr": 1000000,
        "is_demo": True,
        "source": "DEMO_SYNTHETIC",
    }
    po_rejected = {
        "id": "po-vt-rejected",
        "course_id": "cr-verif-test",
        "institute_id": inst_id,
        "district": "Pune",
        "status": "PLACED",
        "verification_status": "REJECTED",
        "salary_annual_inr": 1200000,
        "is_demo": True,
        "source": "DEMO_SYNTHETIC",
    }
    fb_verified_emp = {
        "id": "fb-vt-ver-emp",
        "placement_outcome_id": "po-vt-verified",
        "skill_adequacy_score": 5,
        "practical_readiness": "PRODUCTION_READY",
        "is_verified_employer": True,
        "data_provenance": "EMPLOYER_VERIFIED",
        "is_demo": True,
    }
    fb_unverified_emp = {
        "id": "fb-vt-unver-emp",
        "placement_outcome_id": "po-vt-pending",
        "skill_adequacy_score": 1,
        "practical_readiness": "UNPREPARED",
        "is_verified_employer": False,
        "data_provenance": "UNVERIFIED_EMPLOYER",
        "is_demo": True,
    }

    _cache.setdefault("courses", []).append(course)
    _cache.setdefault("placement_outcomes", []).extend([po_verified, po_pending, po_rejected])
    _cache.setdefault("placement_employer_feedback", []).extend([fb_verified_emp, fb_unverified_emp])

    try:
        scorecard = compute_institute_scorecard(inst_id, is_demo=True)
        assert scorecard["dimension_breakdown"]["placement_employment_rate"]["placed_candidates"] == 1
        assert scorecard["dimension_breakdown"]["placement_employment_rate"]["total_candidates_tracked"] == 3
        assert scorecard["dimension_breakdown"]["wage_premium"]["average_salary_inr"] == 500000
        assert scorecard["dimension_breakdown"]["employer_readiness_feedback"]["feedback_responses_count"] == 1
        assert scorecard["dimension_breakdown"]["employer_readiness_feedback"]["score"] == 100.0
    finally:
        _cache["courses"] = [c for c in _cache["courses"] if c.get("id") != "cr-verif-test"]
        _cache["placement_outcomes"] = [o for o in _cache["placement_outcomes"] if o.get("id") not in ("po-vt-verified", "po-vt-pending", "po-vt-rejected")]
        _cache["placement_employer_feedback"] = [f for f in _cache["placement_employer_feedback"] if f.get("id") not in ("fb-vt-ver-emp", "fb-vt-unver-emp")]


def test_institute_cannot_modify_government_audit_directives(client, gov_headers, coep_headers, vjti_headers):
    create_payload = {
        "notice_type": "COMPLIANCE_REVIEW",
        "severity": "CRITICAL",
        "title": "Safety and Curriculum Non-Compliance",
        "description": "Lab safety protocol revision required immediately.",
        "mandated_action": "Replace obsolete high-voltage trainers.",
        "deadline_date": "2026-11-30",
    }
    create_res = client.post("/api/accreditation/institutes/inst-coep/notices", json=create_payload, headers=gov_headers)
    assert create_res.status_code == 201
    notice_id = create_res.json()["audit_notice"]["id"]

    patch_action = client.patch(
        f"/api/accreditation/notices/{notice_id}",
        json={"mandated_action": "Unauthorized self-exemption."},
        headers=coep_headers,
    )
    assert patch_action.status_code == 403

    patch_deadline = client.patch(
        f"/api/accreditation/notices/{notice_id}",
        json={"deadline_date": "2030-01-01"},
        headers=coep_headers,
    )
    assert patch_deadline.status_code == 403

    patch_status_invalid = client.patch(
        f"/api/accreditation/notices/{notice_id}",
        json={"status": "RESOLVED"},
        headers=coep_headers,
    )
    assert patch_status_invalid.status_code == 403

    patch_idor = client.patch(
        f"/api/accreditation/notices/{notice_id}",
        json={"status": "IN_REMEDIATION", "remediation_notes": "Trying to modify other institute notice."},
        headers=vjti_headers,
    )
    assert patch_idor.status_code == 403

    patch_remediation_valid = client.patch(
        f"/api/accreditation/notices/{notice_id}",
        json={"status": "IN_REMEDIATION", "remediation_notes": "Replaced high-voltage trainer benches and scheduled faculty safety drill."},
        headers=coep_headers,
    )
    assert patch_remediation_valid.status_code == 200
    assert patch_remediation_valid.json()["audit_notice"]["status"] == "IN_REMEDIATION"
    assert patch_remediation_valid.json()["audit_notice"]["mandated_action"] == "Replace obsolete high-voltage trainers."
    assert patch_remediation_valid.json()["audit_notice"]["deadline_date"] == "2026-11-30"

    patch_gov_directive = client.patch(
        f"/api/accreditation/notices/{notice_id}",
        json={
            "mandated_action": "Submit comprehensive equipment safety certification.",
            "deadline_date": "2026-12-15",
            "status": "RESOLVED",
        },
        headers=gov_headers,
    )
    assert patch_gov_directive.status_code == 200
    assert patch_gov_directive.json()["audit_notice"]["status"] == "RESOLVED"
    assert patch_gov_directive.json()["audit_notice"]["mandated_action"] == "Submit comprehensive equipment safety certification."
    assert patch_gov_directive.json()["audit_notice"]["deadline_date"] == "2026-12-15"


def test_retention_lifecycle_enforcement_rules(client, coep_headers):
    res_tc = client.post(
        "/api/placements/outcomes",
        json={
            "course_id": "cr-001",
            "candidate_name": "Test Candidate TC",
            "role_title": "Trainee",
            "status": "TRAINING_COMPLETED",
            "retention_status": "6_MONTH_RETAINED",
        },
        headers=coep_headers,
    )
    assert res_tc.status_code == 400

    res_np = client.post(
        "/api/placements/outcomes",
        json={
            "course_id": "cr-001",
            "candidate_name": "Test Candidate NP",
            "role_title": "Trainee",
            "status": "NOT_PLACED",
            "retention_status": "12_MONTH_RETAINED",
        },
        headers=coep_headers,
    )
    assert res_np.status_code == 400

    res_withdrawn = client.post(
        "/api/placements/outcomes",
        json={
            "course_id": "cr-001",
            "candidate_name": "Test Candidate Withdrawn",
            "role_title": "Trainee",
            "status": "WITHDRAWN",
            "retention_status": "ATTRITED",
        },
        headers=coep_headers,
    )
    assert res_withdrawn.status_code == 400

    res_valid_create = client.post(
        "/api/placements/outcomes",
        json={
            "course_id": "cr-001",
            "candidate_name": "Test Candidate Placed",
            "role_title": "CNC Specialist",
            "status": "PLACED",
            "retention_status": "6_MONTH_RETAINED",
            "salary_annual_inr": 450000,
        },
        headers=coep_headers,
    )
    assert res_valid_create.status_code == 201
    outcome_id = res_valid_create.json()["placement_outcome"]["id"]

    res_regress = client.patch(
        f"/api/placements/outcomes/{outcome_id}",
        json={"retention_status": "6_MONTH_RETAINED"},
        headers=coep_headers,
    )
    assert res_regress.status_code == 200

    res_12m = client.patch(
        f"/api/placements/outcomes/{outcome_id}",
        json={"retention_status": "12_MONTH_RETAINED"},
        headers=coep_headers,
    )
    assert res_12m.status_code == 200

    res_regress_invalid = client.patch(
        f"/api/placements/outcomes/{outcome_id}",
        json={"retention_status": "6_MONTH_RETAINED"},
        headers=coep_headers,
    )
    assert res_regress_invalid.status_code == 400

    res_attrited = client.patch(
        f"/api/placements/outcomes/{outcome_id}",
        json={"retention_status": "ATTRITED"},
        headers=coep_headers,
    )
    assert res_attrited.status_code == 200

    res_attrited_revert = client.patch(
        f"/api/placements/outcomes/{outcome_id}",
        json={"retention_status": "12_MONTH_RETAINED"},
        headers=coep_headers,
    )
    assert res_attrited_revert.status_code == 400

    res_incompatible_status = client.patch(
        f"/api/placements/outcomes/{outcome_id}",
        json={"status": "WITHDRAWN"},
        headers=coep_headers,
    )
    assert res_incompatible_status.status_code == 400
