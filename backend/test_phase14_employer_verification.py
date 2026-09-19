from __future__ import annotations

import datetime
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import create_access_token
from app.repositories.supabase_repository import get_employer, upsert_employer


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
def employer_a_headers():
    token = create_access_token(
        data={"sub": "usr-employer-001", "email": "employer@skillsetu.gov.in", "role": "EMPLOYER"}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def employer_b_headers():
    token = create_access_token(
        data={"sub": "usr-employer-002", "email": "employer2@skillsetu.gov.in", "role": "EMPLOYER"}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def student_headers():
    token = create_access_token(
        data={"sub": "usr-student-001", "email": "student@skillsetu.gov.in", "role": "STUDENT"}
    )
    return {"Authorization": f"Bearer {token}"}


def test_unauthenticated_verification_access_denied(client):
    res = client.get("/api/employer/verification")
    assert res.status_code == 401

    res = client.post("/api/employer/verification/submit", json={"company_name": "Test Org", "industry": "Tech", "district": "Pune"})
    assert res.status_code == 401

    res = client.get("/api/employer/verification/emp-001")
    assert res.status_code == 401

    res = client.get("/api/admin/employer/verifications")
    assert res.status_code == 401

    res = client.get("/api/admin/employer/verifications/emp-001")
    assert res.status_code == 401

    res = client.post("/api/admin/employer/verifications/emp-001/approve", json={})
    assert res.status_code == 401

    res = client.post("/api/admin/employer/verifications/emp-001/reject", json={"rejection_reason": "Invalid data"})
    assert res.status_code == 401


def test_student_role_denied_employer_and_admin_verification(client, student_headers):
    res = client.get("/api/employer/verification", headers=student_headers)
    assert res.status_code == 403

    res = client.post(
        "/api/employer/verification/submit",
        json={"company_name": "Student Co", "industry": "Tech", "district": "Pune"},
        headers=student_headers,
    )
    assert res.status_code == 403

    res = client.get("/api/employer/verification/emp-001", headers=student_headers)
    assert res.status_code == 403

    res = client.get("/api/admin/employer/verifications", headers=student_headers)
    assert res.status_code == 403

    res = client.get("/api/admin/employer/verifications/emp-001", headers=student_headers)
    assert res.status_code == 403

    res = client.post("/api/admin/employer/verifications/emp-001/approve", json={}, headers=student_headers)
    assert res.status_code == 403

    res = client.post(
        "/api/admin/employer/verifications/emp-001/reject",
        json={"rejection_reason": "No access"},
        headers=student_headers,
    )
    assert res.status_code == 403


def test_employer_denied_admin_verification_endpoints(client, employer_a_headers):
    res = client.get("/api/admin/employer/verifications", headers=employer_a_headers)
    assert res.status_code == 403

    res = client.get("/api/admin/employer/verifications/emp-001", headers=employer_a_headers)
    assert res.status_code == 403

    res = client.post("/api/admin/employer/verifications/emp-001/approve", json={}, headers=employer_a_headers)
    assert res.status_code == 403

    res = client.post(
        "/api/admin/employer/verifications/emp-001/reject",
        json={"rejection_reason": "Not allowed"},
        headers=employer_a_headers,
    )
    assert res.status_code == 403


def test_idor_employer_a_cannot_access_or_modify_employer_b(client, employer_a_headers, employer_b_headers):
    res = client.get("/api/employer/verification/emp-002", headers=employer_a_headers)
    assert res.status_code == 403

    res = client.get("/api/employer/verification/emp-001", headers=employer_b_headers)
    assert res.status_code == 403

    res = client.get("/api/employer/verification/emp-002/../emp-001", headers=employer_b_headers)
    assert res.status_code in (403, 404)


def test_new_employer_defaults_to_unverified(client, employer_a_headers):
    res = client.get("/api/employer/verification", headers=employer_a_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["verification_status"] == "UNVERIFIED"
    assert data["is_verified"] is False
    assert data["verified_at"] is None
    assert data["verified_by"] is None


def test_employer_self_declaration_becomes_pending_never_verified(client, employer_a_headers):
    payload = {
        "company_name": "Tata Motors Tech",
        "industry": "Automotive & EV",
        "district": "Pune",
        "gstin": "27AAACT2727Q1ZW",
        "corporate_website": "https://tatamotors.com",
        "official_documents": ["https://tatamotors.com/docs/cin.pdf"],
        "notes": "Corporate headquarters verification submission",
    }
    res = client.post("/api/employer/verification/submit", json=payload, headers=employer_a_headers)
    assert res.status_code == 200
    sub_data = res.json()
    assert sub_data["status"] == "submitted"
    assert sub_data["verification_status"] == "PENDING"
    assert sub_data["is_verified"] is False
    assert sub_data["data_provenance"] == "EMPLOYER_SELF_DECLARED"

    status_res = client.get("/api/employer/verification", headers=employer_a_headers)
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["verification_status"] == "PENDING"
    assert status_data["is_verified"] is False
    assert status_data["data_provenance"] == "EMPLOYER_SELF_DECLARED"
    assert status_data["gstin"] == "27AAACT2727Q1ZW"


def test_admin_can_view_verification_queue_and_detail(client, employer_a_headers, admin_headers):
    client.post(
        "/api/employer/verification/submit",
        json={
            "company_name": "Tata Motors Tech",
            "industry": "Automotive & EV",
            "district": "Pune",
            "gstin": "27AAACT2727Q1ZW",
        },
        headers=employer_a_headers,
    )

    queue_res = client.get("/api/admin/employer/verifications?status=PENDING", headers=admin_headers)
    assert queue_res.status_code == 200
    q_data = queue_res.json()
    assert q_data["status"] == "success"
    assert q_data["total"] >= 1
    assert any(v["employer_id"] == "emp-001" and v["verification_status"] == "PENDING" for v in q_data["verifications"])

    detail_res = client.get("/api/admin/employer/verifications/emp-001", headers=admin_headers)
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["status"] == "success"
    assert detail_data["employer"]["employer_id"] == "emp-001"
    assert detail_data["employer"]["verification_status"] == "PENDING"
    assert len(detail_data["history"]) >= 1


def test_admin_approval_transitions_to_verified_with_authoritative_provenance(client, employer_a_headers, admin_headers):
    client.post(
        "/api/employer/verification/submit",
        json={
            "company_name": "Tata Motors Tech",
            "industry": "Automotive & EV",
            "district": "Pune",
            "gstin": "27AAACT2727Q1ZW",
        },
        headers=employer_a_headers,
    )

    app_res = client.post(
        "/api/admin/employer/verifications/emp-001/approve",
        json={"admin_notes": "Official Maharashtra MCA database and GSTIN verified."},
        headers=admin_headers,
    )
    assert app_res.status_code == 200
    app_data = app_res.json()
    assert app_data["status"] == "approved"
    assert app_data["employer"]["verification_status"] == "VERIFIED"
    assert app_data["employer"]["data_provenance"] == "AUTHORITATIVE_VERIFIED"
    assert app_data["employer"]["verification_source"] == "AUTHORITATIVE_ADMIN_VERIFICATION"
    assert app_data["employer"]["confidence"] == 95
    assert app_data["employer"]["verified_at"] is not None
    assert app_data["employer"]["verified_by"] is not None

    status_res = client.get("/api/employer/verification", headers=employer_a_headers)
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["verification_status"] == "VERIFIED"
    assert status_data["is_verified"] is True
    assert status_data["data_provenance"] == "AUTHORITATIVE_VERIFIED"


def test_admin_rejection_requires_reason_and_transitions_to_rejected(client, employer_b_headers, admin_headers):
    client.post(
        "/api/employer/verification/submit",
        json={
            "company_name": "Bajaj Talent Division",
            "industry": "Manufacturing",
            "district": "Pune",
            "gstin": "27AAACB1234F1Z5",
        },
        headers=employer_b_headers,
    )

    empty_rej = client.post(
        "/api/admin/employer/verifications/emp-002/reject",
        json={"rejection_reason": ""},
        headers=admin_headers,
    )
    assert empty_rej.status_code == 422

    missing_rej = client.post(
        "/api/admin/employer/verifications/emp-002/reject",
        json={},
        headers=admin_headers,
    )
    assert missing_rej.status_code == 422

    valid_rej = client.post(
        "/api/admin/employer/verifications/emp-002/reject",
        json={"rejection_reason": "GSTIN registration does not match company legal name."},
        headers=admin_headers,
    )
    assert valid_rej.status_code == 200
    rej_data = valid_rej.json()
    assert rej_data["status"] == "rejected"
    assert rej_data["rejection_reason"] == "GSTIN registration does not match company legal name."
    assert rej_data["employer"]["verification_status"] == "REJECTED"
    assert rej_data["employer"]["data_provenance"] == "ADMIN_REJECTED"
    assert rej_data["employer"]["confidence"] == 0

    status_res = client.get("/api/employer/verification", headers=employer_b_headers)
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["verification_status"] == "REJECTED"
    assert status_data["is_verified"] is False
    assert status_data["rejection_reason"] == "GSTIN registration does not match company legal name."


def test_rejected_employer_can_resubmit_evidence_to_become_pending_not_verified(client, employer_b_headers, admin_headers):
    client.post(
        "/api/employer/verification/submit",
        json={
            "company_name": "Bajaj Talent Division",
            "industry": "Manufacturing",
            "district": "Pune",
            "gstin": "27AAACB1234F1Z5",
        },
        headers=employer_b_headers,
    )
    client.post(
        "/api/admin/employer/verifications/emp-002/reject",
        json={"rejection_reason": "Discrepancy in address"},
        headers=admin_headers,
    )

    resub = client.post(
        "/api/employer/verification/submit",
        json={
            "company_name": "Bajaj Auto Limited",
            "industry": "Manufacturing",
            "district": "Pune",
            "gstin": "27AAACB1234F1Z5",
            "notes": "Updated address matching certificate.",
        },
        headers=employer_b_headers,
    )
    assert resub.status_code == 200
    assert resub.json()["verification_status"] == "PENDING"
    assert resub.json()["is_verified"] is False

    status_res = client.get("/api/employer/verification", headers=employer_b_headers)
    assert status_res.status_code == 200
    assert status_res.json()["verification_status"] == "PENDING"
    assert status_res.json()["is_verified"] is False
    assert status_res.json()["rejection_reason"] is None


def test_invalid_state_transitions_fail(client, employer_a_headers, admin_headers):
    client.post(
        "/api/employer/verification/submit",
        json={
            "company_name": "Tata Motors Tech",
            "industry": "Automotive & EV",
            "district": "Pune",
        },
        headers=employer_a_headers,
    )
    app_res = client.post(
        "/api/admin/employer/verifications/emp-001/approve",
        json={},
        headers=admin_headers,
    )
    assert app_res.status_code == 200

    double_app = client.post(
        "/api/admin/employer/verifications/emp-001/approve",
        json={},
        headers=admin_headers,
    )
    assert double_app.status_code == 400

    re_sub = client.post(
        "/api/employer/verification/submit",
        json={"company_name": "Tata Motors Tech", "industry": "Automotive & EV", "district": "Pune"},
        headers=employer_a_headers,
    )
    assert re_sub.status_code == 400

    nonexistent_app = client.post(
        "/api/admin/employer/verifications/emp-does-not-exist/approve",
        json={},
        headers=admin_headers,
    )
    assert nonexistent_app.status_code == 404

    nonexistent_rej = client.post(
        "/api/admin/employer/verifications/emp-does-not-exist/reject",
        json={"rejection_reason": "Doesn't exist"},
        headers=admin_headers,
    )
    assert nonexistent_rej.status_code == 404


def test_missing_or_invalid_evidence_fails_closed(client, employer_a_headers):
    bad_name = client.post(
        "/api/employer/verification/submit",
        json={"company_name": "X", "industry": "Tech", "district": "Pune"},
        headers=employer_a_headers,
    )
    assert bad_name.status_code == 422

    bad_gstin = client.post(
        "/api/employer/verification/submit",
        json={"company_name": "Valid Company", "industry": "Tech", "district": "Pune", "gstin": "INVALID123"},
        headers=employer_a_headers,
    )
    assert bad_gstin.status_code == 422


def test_real_mode_excludes_demo_employers_and_synthetic_verification(client, admin_headers):
    real_queue = client.get("/api/admin/employer/verifications", headers=admin_headers)
    assert real_queue.status_code == 200
    real_data = real_queue.json()
    assert all(not v.get("is_demo") and v.get("data_provenance") != "DEMO_SYNTHETIC" for v in real_data["verifications"])

    demo_queue = client.get("/api/admin/employer/verifications?is_demo=true", headers=admin_headers)
    assert demo_queue.status_code == 200
    demo_data = demo_queue.json()
    assert demo_data["total"] >= 1
    assert any(v.get("is_demo") is True for v in demo_data["verifications"])


def test_job_integration_does_not_imply_employer_verification(client, employer_a_headers, admin_headers, student_headers):
    status_before = client.get("/api/employer/verification", headers=employer_a_headers).json()
    assert status_before["verification_status"] == "UNVERIFIED"

    future_deadline = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)).isoformat()
    job_payload = {
        "title": "Cloud Systems Architect",
        "company": "Tata Motors Tech",
        "district": "Pune",
        "industry": "Information Technology",
        "apply_url": "https://tatamotors.com/careers/job100",
        "description": "Production architecture and Kubernetes infrastructure engineering.",
        "skills": ["Cloud Architecture", "Python"],
        "deadline": future_deadline,
    }
    job_res = client.post("/api/jobs", json=job_payload, headers=employer_a_headers)
    assert job_res.status_code == 201
    created_job = job_res.json()["job"]

    assert created_job["is_employer_verified"] is False
    assert created_job["employer_verification_status"] == "UNVERIFIED"

    status_after = client.get("/api/employer/verification", headers=employer_a_headers).json()
    assert status_after["verification_status"] == "UNVERIFIED"
    assert status_after["is_verified"] is False

    client.post(
        "/api/employer/verification/submit",
        json={
            "company_name": "Tata Motors Tech",
            "industry": "Information Technology",
            "district": "Pune",
            "gstin": "27AAACT2727Q1ZW",
        },
        headers=employer_a_headers,
    )
    client.post(
        "/api/admin/employer/verifications/emp-001/approve",
        json={"admin_notes": "Authoritatively verified enterprise"},
        headers=admin_headers,
    )

    jobs_list_res = client.get("/api/jobs?district=pune")
    assert jobs_list_res.status_code == 200
    jobs_data = jobs_list_res.json()
    matching_job = next((j for j in jobs_data if j.get("id") == created_job["id"]), None)
    if matching_job:
        assert matching_job["is_employer_verified"] is True
        assert matching_job["employer_verification_status"] == "VERIFIED"

    opps_res = client.get("/api/opportunities?district=pune")
    assert opps_res.status_code == 200
    opps_data = opps_res.json()
    matching_opp = next((o for o in opps_data if o.get("id") == created_job["id"]), None)
    if matching_opp:
        assert matching_opp["is_employer_verified"] is True
        assert matching_opp["employer_verification_status"] == "VERIFIED"
