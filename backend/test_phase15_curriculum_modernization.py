from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import create_access_token
from app.services import curriculum_engine
from app.repositories import supabase_repository


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin_headers():
    token = create_access_token(
        data={"sub": "73e35d08-a564-4cd2-b503-a641a8a0a5aa", "email": "admin@skillsetu.gov.in", "role": "ADMIN"}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def gov_headers():
    token = create_access_token(
        data={"sub": "usr-gov-001", "email": "government@skillsetu.gov.in", "role": "GOVERNMENT"}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def institute_a_headers():
    token = create_access_token(
        data={"sub": "usr-institute-001", "email": "institute@skillsetu.gov.in", "role": "INSTITUTE"}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def institute_b_headers():
    token = create_access_token(
        data={"sub": "usr-institute-002", "email": "institute2@skillsetu.gov.in", "role": "INSTITUTE"}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def student_headers():
    token = create_access_token(
        data={"sub": "usr-student-001", "email": "student@skillsetu.gov.in", "role": "STUDENT"}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def employer_headers():
    token = create_access_token(
        data={"sub": "usr-employer-001", "email": "employer@skillsetu.gov.in", "role": "EMPLOYER"}
    )
    return {"Authorization": f"Bearer {token}"}


def test_unauthenticated_proposal_access_denied(client):
    res = client.get("/api/curriculum/proposals")
    assert res.status_code == 401

    res = client.post("/api/curriculum/proposals", json={"course_id": "cr-001", "academic_cycle": "2026-2027"})
    assert res.status_code == 401

    res = client.get("/api/curriculum/proposals/prop-test-001")
    assert res.status_code == 401

    res = client.post("/api/curriculum/proposals/prop-test-001/submit")
    assert res.status_code == 401

    res = client.post("/api/curriculum/proposals/prop-test-001/review", json={"review_action": "APPROVED"})
    assert res.status_code == 401

    res = client.post("/api/curriculum/proposals/prop-test-001/adopt")
    assert res.status_code == 401


def test_student_and_employer_forbidden_from_curriculum_proposals(client, student_headers, employer_headers):
    res = client.get("/api/curriculum/proposals", headers=student_headers)
    assert res.status_code == 403

    res = client.post(
        "/api/curriculum/proposals",
        json={"course_id": "cr-001", "academic_cycle": "2026-2027"},
        headers=student_headers,
    )
    assert res.status_code == 403

    res = client.get("/api/curriculum/proposals", headers=employer_headers)
    assert res.status_code == 403

    res = client.post(
        "/api/curriculum/proposals",
        json={"course_id": "cr-001", "academic_cycle": "2026-2027"},
        headers=employer_headers,
    )
    assert res.status_code == 403


def test_curriculum_engine_synthesizes_labour_market_and_employer_evidence():
    blueprint = curriculum_engine.get_course_modernization_blueprint("cr-001")
    assert blueprint is not None
    assert "health_summary" in blueprint
    assert "modernization_blueprint" in blueprint
    assert "evidence_summary" in blueprint
    assert "proposal_ready_blueprint" in blueprint

    evidence = blueprint["evidence_summary"]
    assert "live_jobs_matched" in evidence
    assert "verified_employer_openings" in evidence
    assert "verified_employers" in evidence
    assert "gov_opportunities_count" in evidence

    top_missing = blueprint["modernization_blueprint"].get("top_missing_skills", [])
    assert len(top_missing) > 0
    for sk in top_missing:
        assert "skill_name" in sk
        assert "job_demand_count" in sk
        assert "verified_employer_openings" in sk
        assert "verified_employers" in sk
        assert "gov_opportunities_count" in sk


def test_sparse_course_blueprint_graceful_handling():
    invalid = curriculum_engine.get_course_modernization_blueprint("cr-invalid-999")
    assert invalid is None


def test_institute_proposal_creation_and_ownership(client, institute_a_headers):
    create_res = client.post(
        "/api/curriculum/proposals",
        json={
            "course_id": "cr-001",
            "academic_cycle": "2026-2027",
            "proposed_changes_summary": "Modernizing curriculum to address industry gaps.",
        },
        headers=institute_a_headers,
    )
    assert create_res.status_code == 201
    body = create_res.json()
    assert body["status"] == "success"
    proposal = body["proposal"]
    assert proposal["status"] == "DRAFT"
    assert proposal["created_by"] == "usr-institute-001"
    assert proposal["institute_id"] == "inst-coep"
    assert proposal["course_id"] == "cr-001"
    assert proposal["academic_cycle"] == "2026-2027"
    assert len(proposal["proposed_skills_to_add"]) > 0


def test_cross_institute_idor_protection(client, institute_a_headers, institute_b_headers):
    forbidden_create = client.post(
        "/api/curriculum/proposals",
        json={
            "course_id": "cr-001",
            "academic_cycle": "2026-2027",
        },
        headers=institute_b_headers,
    )
    assert forbidden_create.status_code == 403

    create_res = client.post(
        "/api/curriculum/proposals",
        json={
            "course_id": "cr-001",
            "academic_cycle": "2026-2027",
        },
        headers=institute_a_headers,
    )
    assert create_res.status_code == 201
    proposal_id = create_res.json()["proposal"]["proposal_id"]

    get_res = client.get(f"/api/curriculum/proposals/{proposal_id}", headers=institute_b_headers)
    assert get_res.status_code == 403

    patch_res = client.patch(
        f"/api/curriculum/proposals/{proposal_id}",
        json={"proposed_changes_summary": "Malicious override attempt"},
        headers=institute_b_headers,
    )
    assert patch_res.status_code == 403

    submit_res = client.post(f"/api/curriculum/proposals/{proposal_id}/submit", headers=institute_b_headers)
    assert submit_res.status_code == 403

    adopt_res = client.post(f"/api/curriculum/proposals/{proposal_id}/adopt", headers=institute_b_headers)
    assert adopt_res.status_code == 403


def test_proposal_lifecycle_valid_state_transitions(client, institute_a_headers, gov_headers):
    create_res = client.post(
        "/api/curriculum/proposals",
        json={
            "course_id": "cr-001",
            "academic_cycle": "2026-2027",
        },
        headers=institute_a_headers,
    )
    assert create_res.status_code == 201
    proposal_id = create_res.json()["proposal"]["proposal_id"]
    assert create_res.json()["proposal"]["status"] == "DRAFT"

    submit_res = client.post(f"/api/curriculum/proposals/{proposal_id}/submit", headers=institute_a_headers)
    assert submit_res.status_code == 200
    assert submit_res.json()["proposal"]["status"] == "SUBMITTED"

    review_res = client.post(
        f"/api/curriculum/proposals/{proposal_id}/review",
        json={
            "review_action": "APPROVED",
            "review_notes": "Syllabus changes verified against industry demand standards.",
        },
        headers=gov_headers,
    )
    assert review_res.status_code == 200
    reviewed_proposal = review_res.json()["proposal"]
    assert reviewed_proposal["status"] == "APPROVED"
    assert reviewed_proposal["reviewed_by"] == "usr-gov-001"
    assert reviewed_proposal["reviewed_at"] is not None

    adopt_res = client.post(f"/api/curriculum/proposals/{proposal_id}/adopt", headers=institute_a_headers)
    assert adopt_res.status_code == 200
    adopted_proposal = adopt_res.json()["proposal"]
    assert adopted_proposal["status"] == "ADOPTED"
    assert adopted_proposal["adopted_at"] is not None
    assert adopted_proposal["adopted_by"] == "usr-institute-001"
    assert adopted_proposal["previous_curriculum_snapshot"] is not None
    assert adopted_proposal["adopted_curriculum_snapshot"] is not None


def test_rejection_requires_mandatory_notes_and_permits_resubmission(client, institute_a_headers, gov_headers):
    create_res = client.post(
        "/api/curriculum/proposals",
        json={
            "course_id": "cr-001",
            "academic_cycle": "2026-2027",
        },
        headers=institute_a_headers,
    )
    assert create_res.status_code == 201
    proposal_id = create_res.json()["proposal"]["proposal_id"]

    client.post(f"/api/curriculum/proposals/{proposal_id}/submit", headers=institute_a_headers)

    bad_reject_res = client.post(
        f"/api/curriculum/proposals/{proposal_id}/review",
        json={
            "review_action": "REJECTED",
            "review_notes": "   ",
        },
        headers=gov_headers,
    )
    assert bad_reject_res.status_code == 400
    assert "mandatory" in bad_reject_res.json()["detail"].lower()

    reject_res = client.post(
        f"/api/curriculum/proposals/{proposal_id}/review",
        json={
            "review_action": "REJECTED",
            "review_notes": "Please include 40 practical training hours on IoT sensors.",
        },
        headers=gov_headers,
    )
    assert reject_res.status_code == 200
    assert reject_res.json()["proposal"]["status"] == "REJECTED"

    patch_res = client.patch(
        f"/api/curriculum/proposals/{proposal_id}",
        json={
            "proposed_changes_summary": "Updated with 40 practical training hours on IoT sensors.",
            "proposed_skills_to_add": ["Industrial IoT", "Sensor Calibration"],
        },
        headers=institute_a_headers,
    )
    assert patch_res.status_code == 200
    assert "Industrial IoT" in patch_res.json()["proposal"]["proposed_skills_to_add"]

    resubmit_res = client.post(f"/api/curriculum/proposals/{proposal_id}/submit", headers=institute_a_headers)
    assert resubmit_res.status_code == 200
    assert resubmit_res.json()["proposal"]["status"] == "SUBMITTED"


def test_invalid_state_transitions_fail_closed(client, institute_a_headers, gov_headers):
    create_res = client.post(
        "/api/curriculum/proposals",
        json={
            "course_id": "cr-001",
            "academic_cycle": "2026-2027",
        },
        headers=institute_a_headers,
    )
    proposal_id = create_res.json()["proposal"]["proposal_id"]

    adopt_draft_res = client.post(f"/api/curriculum/proposals/{proposal_id}/adopt", headers=institute_a_headers)
    assert adopt_draft_res.status_code == 400

    review_draft_res = client.post(
        f"/api/curriculum/proposals/{proposal_id}/review",
        json={"review_action": "APPROVED"},
        headers=gov_headers,
    )
    assert review_draft_res.status_code == 400

    client.post(f"/api/curriculum/proposals/{proposal_id}/submit", headers=institute_a_headers)
    adopt_submitted_res = client.post(f"/api/curriculum/proposals/{proposal_id}/adopt", headers=institute_a_headers)
    assert adopt_submitted_res.status_code == 400


def test_historical_curriculum_integrity_on_adoption(client, institute_a_headers, gov_headers):
    original_course = supabase_repository.get_course("cr-001")
    assert original_course is not None
    original_skills = list(original_course.get("skills") or original_course.get("skills_taught") or [])
    original_version = original_course.get("curriculum_version") or 1

    create_res = client.post(
        "/api/curriculum/proposals",
        json={
            "course_id": "cr-001",
            "academic_cycle": "2026-2027",
            "proposed_skills_to_add": ["Cloud Robotics", "Predictive Maintenance"],
            "proposed_skills_to_remove": [original_skills[0]] if original_skills else [],
        },
        headers=institute_a_headers,
    )
    assert create_res.status_code == 201
    proposal_id = create_res.json()["proposal"]["proposal_id"]

    client.post(f"/api/curriculum/proposals/{proposal_id}/submit", headers=institute_a_headers)
    client.post(
        f"/api/curriculum/proposals/{proposal_id}/review",
        json={"review_action": "APPROVED", "review_notes": "Meets state syllabus modernization criteria."},
        headers=gov_headers,
    )
    adopt_res = client.post(f"/api/curriculum/proposals/{proposal_id}/adopt", headers=institute_a_headers)
    assert adopt_res.status_code == 200

    updated_course = supabase_repository.get_course("cr-001")
    assert updated_course["curriculum_version"] == original_version + 1
    assert updated_course["modernization_proposal_id"] == proposal_id
    assert updated_course["last_curriculum_modernization_at"] is not None
    assert "Cloud Robotics" in updated_course["skills"]
    assert "Predictive Maintenance" in updated_course["skills"]
    if original_skills:
        assert original_skills[0] not in updated_course["skills"]

    proposal_row = supabase_repository.get_curriculum_proposal(proposal_id)
    assert proposal_row["previous_curriculum_snapshot"] is not None
    assert proposal_row["previous_curriculum_snapshot"]["skills"] == original_skills
    assert proposal_row["adopted_curriculum_snapshot"] is not None
    assert "Cloud Robotics" in proposal_row["adopted_curriculum_snapshot"]["skills"]


def test_government_and_admin_curriculum_proposal_listing(client, institute_a_headers, gov_headers, admin_headers):
    create_res = client.post(
        "/api/curriculum/proposals",
        json={
            "course_id": "cr-001",
            "academic_cycle": "2026-2027",
        },
        headers=institute_a_headers,
    )
    proposal_id = create_res.json()["proposal"]["proposal_id"]

    gov_list_res = client.get("/api/curriculum/proposals", headers=gov_headers)
    assert gov_list_res.status_code == 200
    assert any(p["proposal_id"] == proposal_id for p in gov_list_res.json()["proposals"])

    admin_list_res = client.get("/api/curriculum/proposals", headers=admin_headers)
    assert admin_list_res.status_code == 200
    assert any(p["proposal_id"] == proposal_id for p in admin_list_res.json()["proposals"])

    gov_adopt_res = client.post(f"/api/curriculum/proposals/{proposal_id}/adopt", headers=gov_headers)
    assert gov_adopt_res.status_code == 403
