import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app
from app.services.trainer_service import (
    compute_course_trainer_capacity,
    compute_institute_faculty_scorecard,
    compute_statewide_trainer_analytics,
)

client = TestClient(app)


def _get_headers(role: str, user_id: str = "usr-institute-001", email: str = "institute@skillsetu.gov.in", org_id: str = "inst-coep") -> dict[str, str]:
    token = create_access_token(data={
        "id": user_id,
        "sub": user_id,
        "email": email,
        "role": role,
        "organization_id": org_id,
        "institute_id": org_id,
    })
    return {"Authorization": f"Bearer {token}"}


def test_nsqf_norm_calculation():
    course_60 = {"id": "c-test-1", "name": "AI Course", "enrolment_capacity": 60, "skills": ["Python", "PyTorch"]}
    trainers = [
        {"id": "tr-1", "name": "Trainer 1", "assigned_course_ids": ["c-test-1"], "certified_skills": ["Python"], "status": "ACTIVE"},
        {"id": "tr-2", "name": "Trainer 2", "assigned_course_ids": ["c-test-1"], "certified_skills": ["PyTorch"], "status": "ACTIVE"},
    ]
    res = compute_course_trainer_capacity(course_60, trainers)
    assert res["required_trainers"] == 3
    assert res["assigned_trainers_count"] == 2
    assert res["capacity_ratio_pct"] == 66.7
    assert res["competency_score_pct"] == 100.0
    assert len(res["uncovered_skills"]) == 0

    course_20 = {"id": "c-test-2", "name": "EV Course", "enrolment_capacity": 20, "skills": ["CAN Bus", "BMS Diagnostics"]}
    res2 = compute_course_trainer_capacity(course_20, [])
    assert res2["required_trainers"] == 1
    assert res2["assigned_trainers_count"] == 0
    assert res2["capacity_ratio_pct"] == 0.0
    assert len(res2["uncovered_skills"]) == 2


def test_institute_faculty_scorecard_deterministic():
    scorecard = compute_institute_faculty_scorecard("inst-coep", is_demo=True)
    assert scorecard["institute_id"] == "inst-coep"
    assert "faculty_readiness_index" in scorecard
    assert isinstance(scorecard["faculty_readiness_index"], float)
    assert scorecard["overall_compliance_status"] in ("COMPLIANT", "UNDERSTAFFED")
    assert "1:" in scorecard["overall_student_trainer_ratio"]
    assert len(scorecard["course_capacities"]) > 0


def test_statewide_trainer_analytics_deterministic():
    analytics = compute_statewide_trainer_analytics(is_demo=True)
    assert "summary" in analytics
    assert analytics["summary"]["total_trainers"] >= 4
    assert "district_breakdown" in analytics
    assert len(analytics["district_breakdown"]) > 0
    first_dist = analytics["district_breakdown"][0]
    assert "district" in first_dist
    assert "compliance_status" in first_dist


def test_list_and_filter_trainers_api():
    headers = _get_headers("INSTITUTE", user_id="usr-institute-001", email="institute@skillsetu.gov.in", org_id="inst-coep")
    resp = client.get("/api/trainers?is_demo=true", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "trainers" in data
    assert all(t["institute_id"] == "inst-coep" for t in data["trainers"])


def test_institute_register_trainer_api():
    headers = _get_headers("INSTITUTE", user_id="usr-institute-001", email="institute@skillsetu.gov.in", org_id="inst-coep")
    payload = {
        "name": "Prof. Aniket Deshmukh",
        "employee_id": "EMP-COEP-998",
        "primary_trade": "Advanced Robotics",
        "skills": ["ROS2", "PLC Programming", "Industrial Automation"],
        "certifications": ["Certified Robotics Engineer"],
        "experience_years": 8.0,
        "industry_experience_years": 4.0,
        "highest_qualification": "M.Tech Robotics",
        "status": "ACTIVE",
    }
    resp = client.post("/api/trainers", json=payload, headers=headers)
    assert resp.status_code == 201
    created = resp.json()
    assert created["id"].startswith("tr-")
    assert created["institute_id"] == "inst-coep"
    assert created["data_provenance"] == "INSTITUTE_AUTHORITATIVE"


def test_idor_protection_trainer_scorecard():
    headers_coep = _get_headers("INSTITUTE", user_id="usr-institute-001", email="institute@skillsetu.gov.in", org_id="inst-coep")
    resp = client.get("/api/trainers/institutes/inst-vjti/scorecard?is_demo=true", headers=headers_coep)
    assert resp.status_code == 403

    headers_gov = _get_headers("GOVERNMENT", user_id="usr-gov-001", email="government@skillsetu.gov.in", org_id="state-gov")
    resp_gov = client.get("/api/trainers/institutes/inst-vjti/scorecard?is_demo=true", headers=headers_gov)
    assert resp_gov.status_code == 200


def test_faculty_nomination_lifecycle_and_sanction():
    headers_coep = _get_headers("INSTITUTE", user_id="usr-institute-001", email="institute@skillsetu.gov.in", org_id="inst-coep")
    nom_payload = {
        "trainer_id": "trn-demo-001",
        "program_code": "FDP-AI-01",
        "program_title": "Applied Deep Learning & Generative AI for Technical Faculty",
        "domain": "Artificial Intelligence",
        "partner_agency": "IIT Bombay / NPTEL",
        "duration_weeks": 4,
        "budget_inr": 25000,
        "rationale": "Required to modernise B.Tech AI lab curriculum.",
    }
    create_resp = client.post("/api/trainers/nominations", json=nom_payload, headers=headers_coep)
    assert create_resp.status_code == 201
    nom_data = create_resp.json()
    nom_id = nom_data["id"]
    assert nom_data["status"] == "NOMINATED"

    inst_sanction_attempt = client.patch(
        f"/api/trainers/nominations/{nom_id}",
        json={"status": "SANCTIONED"},
        headers=headers_coep,
    )
    assert inst_sanction_attempt.status_code == 403

    headers_gov = _get_headers("GOVERNMENT", user_id="usr-gov-001", email="government@skillsetu.gov.in", org_id="msde-maha")
    gov_sanction = client.patch(
        f"/api/trainers/nominations/{nom_id}",
        json={"status": "SANCTIONED", "sanction_amount_inr": 25000},
        headers=headers_gov,
    )
    assert gov_sanction.status_code == 200
    sanctioned_data = gov_sanction.json()
    assert sanctioned_data["status"] == "SANCTIONED"
    assert sanctioned_data["data_provenance"] == "STATE_SANCTIONED_FDP"
    assert "sanction_reference" in sanctioned_data

    inst_completion = client.patch(
        f"/api/trainers/nominations/{nom_id}",
        json={
            "status": "COMPLETED",
            "completion_date": "2026-10-15",
            "certification_earned": "NPTEL Certified AI Master Trainer",
        },
        headers=headers_coep,
    )
    assert inst_completion.status_code == 200
    completed_data = inst_completion.json()
    assert completed_data["status"] == "COMPLETED"

    trainer_resp = client.get("/api/trainers/trn-demo-001", headers=headers_coep)
    assert trainer_resp.status_code == 200
    trainer_data = trainer_resp.json()
    assert "NPTEL Certified AI Master Trainer" in trainer_data["certifications"]
