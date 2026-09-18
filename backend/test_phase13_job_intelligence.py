from __future__ import annotations

import datetime
import uuid
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ingestion.job_intelligence import (
    validate_and_normalize,
    JobIntelligenceIngestor,
    job_ingestor,
)
from app.services.job_matching import match_student_to_jobs
from app.repositories.supabase_repository import (
    SupabaseRepositoryError,
    upsert_student_profile,
)
from app.core.security import create_access_token


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def employer_headers():
    token = create_access_token(data={"sub": "usr-employer-001", "email": "employer@skillsetu.gov.in", "role": "EMPLOYER"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers():
    token = create_access_token(data={"sub": "73e35d08-a564-4cd2-b503-a641a8a0a5aa", "email": "admin@skillsetu.gov.in", "role": "ADMIN"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def student_headers():
    token = create_access_token(data={"sub": "usr-student-001", "email": "student@skillsetu.gov.in", "role": "STUDENT"})
    return {"Authorization": f"Bearer {token}"}


def test_valid_job_normalization():
    future_deadline = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)).isoformat()
    raw = {
        "title": "Senior Python Backend Developer",
        "company": "Tata Consultancy Services",
        "district": "pune",
        "industry": "Information Technology",
        "apply_url": "https://tcs.com/careers/job123",
        "description": "Develop high-scale APIs with Python, FastAPI, and PostgreSQL.",
        "skills": ["Python", "FastAPI"],
        "deadline": future_deadline,
        "posted_date": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    norm, err = validate_and_normalize(raw, is_demo=False, is_trusted_feed=True)
    assert err is None
    assert norm is not None
    assert norm["title"] == "Senior Python Backend Developer"
    assert norm["company"] == "Tata Consultancy Services"
    assert norm["district"] == "Pune"
    assert norm["verification_status"] == "VERIFIED"
    assert norm["status"] == "active"
    assert norm["is_active"] is True
    assert norm["data_provenance"] == "VERIFIED_EXTERNAL_FEED"
    assert norm["deadline"] == future_deadline


def test_required_field_validation():
    norm, err = validate_and_normalize({}, is_demo=False, is_trusted_feed=True)
    assert norm is None
    assert "title is required" in err.lower()

    norm, err = validate_and_normalize({"title": "A"}, is_demo=False, is_trusted_feed=True)
    assert norm is None
    assert "title is required" in err.lower()

    norm, err = validate_and_normalize({"title": "Valid Title", "company": ""}, is_demo=False, is_trusted_feed=True)
    assert norm is None
    assert "company name is required" in err.lower()

    norm, err = validate_and_normalize({"title": "Valid Title", "company": "Valid Company", "apply_url": ""}, is_demo=False, is_trusted_feed=True)
    assert norm is None
    assert "apply url" in err.lower()

    norm, err = validate_and_normalize({"title": "Valid Title", "company": "Valid Company", "apply_url": "ftp://invalid"}, is_demo=False, is_trusted_feed=True)
    assert norm is None
    assert "valid http" in err.lower()


def test_malformed_deadline_rejection():
    raw = {
        "title": "Python Developer",
        "company": "Infosys",
        "district": "Pune",
        "apply_url": "https://infosys.com/job",
        "deadline": "not-a-real-date",
    }
    norm, err = validate_and_normalize(raw, is_demo=False, is_trusted_feed=True)
    assert norm is None
    assert "invalid deadline format" in err.lower()


def test_expired_deadline_handling():
    past_deadline = "2020-01-01T00:00:00Z"
    raw = {
        "title": "Python Developer",
        "company": "Infosys",
        "district": "Pune",
        "apply_url": "https://infosys.com/job",
        "deadline": past_deadline,
    }
    norm, err = validate_and_normalize(raw, is_demo=False, is_trusted_feed=True)
    assert err is None
    assert norm is not None
    assert norm["status"] == "expired"
    assert norm["is_active"] is False
    assert norm["freshness_status"] == "EXPIRED"


def test_freshness_calculation():
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    fresh_date = (now_dt - datetime.timedelta(days=2)).isoformat()
    raw_fresh = {
        "title": "Python Developer",
        "company": "Infosys",
        "district": "Pune",
        "apply_url": "https://infosys.com/job",
        "posted_date": fresh_date,
    }
    norm_fresh, _ = validate_and_normalize(raw_fresh, is_demo=False, is_trusted_feed=True)
    assert norm_fresh["freshness_status"] == "NEW"

    older_date = (now_dt - datetime.timedelta(days=20)).isoformat()
    raw_older = {
        "title": "Python Developer",
        "company": "Infosys",
        "district": "Pune",
        "apply_url": "https://infosys.com/job",
        "posted_date": older_date,
    }
    norm_older, _ = validate_and_normalize(raw_older, is_demo=False, is_trusted_feed=True)
    assert norm_older["freshness_status"] == "RECENT"


def test_deterministic_content_hash():
    raw1 = {
        "title": "Cloud Architect",
        "company": "Wipro",
        "district": "mumbai",
        "apply_url": "https://wipro.com/job1",
        "description": "Cloud deployment using AWS and Kubernetes.",
    }
    raw2 = {
        "title": "Cloud Architect",
        "company": "Wipro",
        "district": "Mumbai City",
        "apply_url": "https://wipro.com/job1",
        "description": "Cloud deployment using AWS and Kubernetes.",
    }
    norm1, _ = validate_and_normalize(raw1, is_demo=False, is_trusted_feed=True)
    norm2, _ = validate_and_normalize(raw2, is_demo=False, is_trusted_feed=True)
    assert norm1["content_hash"] == norm2["content_hash"]


def test_duplicate_job_prevention():
    ingestor = JobIntelligenceIngestor()
    job1 = {
        "id": "job-1",
        "source": "ADZUNA_API",
        "external_id": "ext-100",
        "content_hash": "hash-abc",
        "title": "Data Analyst",
        "last_seen_at": "2026-09-01T00:00:00Z",
    }
    job2 = {
        "id": "job-2",
        "source": "ADZUNA_API",
        "external_id": "ext-100",
        "content_hash": "hash-abc",
        "title": "Data Analyst",
        "last_seen_at": "2026-09-02T00:00:00Z",
    }
    deduped = ingestor.deduplicate_jobs([job1, job2])
    assert len(deduped) == 1
    assert deduped[0]["last_seen_at"] == "2026-09-02T00:00:00Z"


def test_source_external_id_deduplication():
    ingestor = JobIntelligenceIngestor()
    job1 = {"id": "j1", "source": "ADZUNA_API", "external_id": "ext-999", "title": "First"}
    job2 = {"id": "j2", "source": "ADZUNA_API", "external_id": "ext-999", "title": "Second"}
    deduped = ingestor.deduplicate_jobs([job1, job2])
    assert len(deduped) == 1
    assert deduped[0]["id"] == "j1"


def test_real_demo_isolation():
    raw_demo = {
        "title": "Synthetic Job",
        "company": "Demo Corp",
        "apply_url": "https://demo.com",
        "is_demo": True,
    }
    norm, err = validate_and_normalize(raw_demo, is_demo=False, is_trusted_feed=False)
    assert norm is None
    assert "real mode rejects synthetic/demo jobs" in err.lower()

    raw_synth = {
        "title": "Synthetic Job",
        "company": "Demo Corp",
        "apply_url": "https://demo.com",
        "source": "DEMO_SYNTHETIC",
    }
    norm2, err2 = validate_and_normalize(raw_synth, is_demo=False, is_trusted_feed=False)
    assert norm2 is None
    assert "real mode rejects synthetic/demo jobs" in err2.lower()


def test_caller_supplied_provenance_cannot_self_promote_to_verified():
    raw_caller = {
        "title": "Unverified Job",
        "company": "Third Party Corp",
        "apply_url": "https://thirdparty.com/job",
        "data_provenance": "GOVERNMENT_OFFICIAL",
        "verification_status": "VERIFIED",
        "status": "active",
        "is_active": True,
    }
    norm, err = validate_and_normalize(raw_caller, is_demo=False, is_trusted_feed=False)
    assert err is None
    assert norm is not None
    assert norm["data_provenance"] == "UNVERIFIED_EXTERNAL_SOURCE"
    assert norm["verification_status"] == "PENDING"
    assert norm["status"] == "pending"
    assert norm["is_active"] is False


def test_trusted_feed_verification_behavior():
    raw_trusted = {
        "title": "Verified Live Job",
        "company": "Mahindra",
        "apply_url": "https://mahindra.com/job",
        "source": "ADZUNA_API",
    }
    norm, err = validate_and_normalize(raw_trusted, is_demo=False, is_trusted_feed=True)
    assert err is None
    assert norm is not None
    assert norm["verification_status"] == "VERIFIED"
    assert norm["data_provenance"] == "VERIFIED_EXTERNAL_FEED"
    assert norm["status"] == "active"
    assert norm["is_active"] is True


def test_inactive_rejected_filtering(client):
    mock_jobs = [
        {
            "id": "job-active",
            "title": "Active Job",
            "company": "TCS",
            "district": "Pune",
            "industry": "IT",
            "status": "active",
            "is_active": True,
            "verification_status": "VERIFIED",
            "data_provenance": "VERIFIED_EXTERNAL_FEED",
            "is_demo": False,
        },
        {
            "id": "job-inactive",
            "title": "Inactive Job",
            "company": "TCS",
            "district": "Pune",
            "industry": "IT",
            "status": "inactive",
            "is_active": False,
            "verification_status": "VERIFIED",
            "data_provenance": "VERIFIED_EXTERNAL_FEED",
            "is_demo": False,
        },
        {
            "id": "job-rejected",
            "title": "Rejected Job",
            "company": "TCS",
            "district": "Pune",
            "industry": "IT",
            "status": "active",
            "is_active": True,
            "verification_status": "REJECTED",
            "data_provenance": "UNVERIFIED_EXTERNAL_SOURCE",
            "is_demo": False,
        },
        {
            "id": "job-demo",
            "title": "Demo Job",
            "company": "TCS",
            "district": "Pune",
            "industry": "IT",
            "status": "active",
            "is_active": True,
            "verification_status": "VERIFIED",
            "data_provenance": "DEMO_SYNTHETIC",
            "is_demo": True,
        },
    ]
    with patch("app.repositories.supabase_repository.list_jobs", return_value=mock_jobs):
        resp = client.get("/api/jobs?is_demo=false")
        assert resp.status_code == 200
        data = resp.json()
        ids = [j["id"] for j in data]
        assert "job-active" in ids
        assert "job-inactive" not in ids
        assert "job-rejected" not in ids
        assert "job-demo" not in ids


def test_real_repository_failure_propagation(client):
    with patch("app.repositories.supabase_repository.list_jobs", side_effect=SupabaseRepositoryError("DB down")):
        resp = client.get("/api/jobs?is_demo=false")
        assert resp.status_code == 503


def test_post_api_jobs_rbac(client, student_headers, employer_headers, admin_headers, tmp_path):
    with patch("app.db._find_real_data_dir", return_value=tmp_path):
        payload = {
            "title": "DevOps Engineer",
            "company": "Persistent Systems",
            "district": "Pune",
            "industry": "IT",
            "description": "Manage Kubernetes clusters and CI/CD pipelines.",
            "apply_url": "https://persistent.com/careers/devops",
        }

        resp_anon = client.post("/api/jobs", json=payload)
        assert resp_anon.status_code in (401, 403)

        resp_student = client.post("/api/jobs", json=payload, headers=student_headers)
        assert resp_student.status_code == 403

        resp_employer = client.post("/api/jobs", json=payload, headers=employer_headers)
        assert resp_employer.status_code == 201
        assert resp_employer.json()["status"] == "created"

        resp_admin = client.post("/api/jobs", json=payload, headers=admin_headers)
        assert resp_admin.status_code == 201


def test_employer_cannot_create_authoritative_government_provenance(client, employer_headers, tmp_path):
    with patch("app.db._find_real_data_dir", return_value=tmp_path):
        payload = {
            "title": "Senior Specialist",
            "company": "L&T",
            "district": "Mumbai",
            "industry": "Engineering",
            "description": "Industrial manufacturing and plant engineering.",
            "apply_url": "https://lnt.com/careers",
            "data_provenance": "GOVERNMENT_OFFICIAL",
            "status": "active",
            "is_active": True,
        }
        resp = client.post("/api/jobs", json=payload, headers=employer_headers)
        assert resp.status_code == 201
        saved_job = resp.json()["job"]
        assert saved_job["data_provenance"] == "EMPLOYER_SUBMITTED"
        assert saved_job["verification_status"] == "PENDING"
        assert saved_job["status"] == "pending"
        assert saved_job["is_active"] is False


def test_student_recommendation_idor_protection(client, student_headers, admin_headers):
    profile_target = {
        "id": "usr-student-001",
        "user_id": "usr-student-001",
        "full_name": "Student Alpha",
        "preferred_location": "Pune",
        "skills": [{"name": "Python", "proficiency": "advanced"}],
        "source": "USER_SUBMITTED",
        "is_demo": False,
    }
    upsert_student_profile(profile_target)

    resp_anon = client.get("/api/jobs/recommended/usr-student-001?is_demo=false")
    assert resp_anon.status_code == 401

    token_other = create_access_token(data={"sub": "usr-student-002", "email": "student2@skillsetu.gov.in", "role": "STUDENT"})
    headers_other = {"Authorization": f"Bearer {token_other}"}
    resp_forbidden = client.get("/api/jobs/recommended/usr-student-001?is_demo=false", headers=headers_other)
    assert resp_forbidden.status_code == 403

    resp_owner = client.get("/api/jobs/recommended/usr-student-001?is_demo=false", headers=student_headers)
    assert resp_owner.status_code == 200

    resp_admin = client.get("/api/jobs/recommended/usr-student-001?is_demo=false", headers=admin_headers)
    assert resp_admin.status_code == 200


def test_deterministic_job_to_student_skill_matching():
    profile = {
        "id": "std-1",
        "skills": [{"skill_name": "Python", "proficiency": "advanced"}, {"skill_name": "FastAPI", "proficiency": "intermediate"}],
    }
    jobs = [
        {
            "id": "job-1",
            "title": "FastAPI Backend Developer",
            "company": "Tech Corp",
            "district": "Pune",
            "status": "active",
            "is_active": True,
            "verification_status": "VERIFIED",
            "skills": ["Python", "FastAPI", "Docker"],
        },
        {
            "id": "job-2",
            "title": "Electrician",
            "company": "Auto Corp",
            "district": "Nagpur",
            "status": "active",
            "is_active": True,
            "verification_status": "VERIFIED",
            "skills": ["Electrical Wiring", "PLC Programming"],
        },
    ]
    matches = match_student_to_jobs(profile, jobs)
    assert len(matches) == 2
    assert matches[0]["job_id"] == "job-1"
    assert "Python" in matches[0]["matched_skills"]
    assert "FastAPI" in matches[0]["matched_skills"]
    assert "Docker" in matches[0]["missing_skills"]
    assert matches[0]["match_score"] > matches[1]["match_score"]


def test_missing_skill_gap_calculation():
    profile = {
        "id": "std-gap",
        "skills": ["Python"],
    }
    jobs = [
        {
            "id": "job-target",
            "title": "AI Engineer",
            "status": "active",
            "is_active": True,
            "verification_status": "VERIFIED",
            "skills": ["Python", "Generative AI", "Docker"],
        }
    ]
    matches = match_student_to_jobs(profile, jobs)
    assert len(matches) == 1
    assert "Generative AI" in matches[0]["skill_gap"]
    assert "Docker" in matches[0]["skill_gap"]
    assert "Python" not in matches[0]["skill_gap"]


def test_expired_jobs_excluded_from_recommendations(client, student_headers):
    past_dl = "2020-01-01T00:00:00Z"
    profile = {
        "id": "usr-student-001",
        "user_id": "usr-student-001",
        "full_name": "Student Alpha",
        "preferred_location": "Pune",
        "skills": [{"name": "Python", "proficiency": "advanced"}],
        "source": "USER_SUBMITTED",
        "is_demo": False,
    }
    upsert_student_profile(profile)

    mock_jobs = [
        {
            "id": "job-valid",
            "title": "Python Developer",
            "company": "Persistent",
            "district": "Pune",
            "status": "active",
            "is_active": True,
            "verification_status": "VERIFIED",
            "is_demo": False,
            "skills": ["Python"],
        },
        {
            "id": "job-expired",
            "title": "Python Developer",
            "company": "Persistent",
            "district": "Pune",
            "status": "active",
            "is_active": True,
            "verification_status": "VERIFIED",
            "deadline": past_dl,
            "is_demo": False,
            "skills": ["Python"],
        },
    ]
    with patch("app.repositories.supabase_repository.list_jobs", return_value=mock_jobs), \
         patch("app.repositories.supabase_repository.list_job_skills", return_value=[]), \
         patch("app.repositories.supabase_repository.list_skills", return_value=[]):
        resp = client.get("/api/jobs/recommended/usr-student-001?is_demo=false", headers=student_headers)
        assert resp.status_code == 200
        rec_ids = [m["job_id"] for m in resp.json()["recommended_jobs"]]
        assert "job-valid" in rec_ids
        assert "job-expired" not in rec_ids


def test_opportunities_api_real_mode_filtering(client):
    mock_jobs = [
        {
            "id": "opp-real-active",
            "title": "Software Apprentice",
            "company": "TCS",
            "district": "Pune",
            "industry": "IT",
            "opportunity_type": "apprenticeship",
            "status": "active",
            "is_active": True,
            "verification_status": "VERIFIED",
            "is_demo": False,
        },
        {
            "id": "opp-expired",
            "title": "Expired Apprentice",
            "company": "TCS",
            "district": "Pune",
            "industry": "IT",
            "opportunity_type": "apprenticeship",
            "status": "active",
            "is_active": True,
            "verification_status": "VERIFIED",
            "deadline": "2020-01-01T00:00:00Z",
            "is_demo": False,
        },
    ]
    with patch("app.repositories.supabase_repository.list_jobs", return_value=mock_jobs), \
         patch("app.repositories.supabase_repository.list_job_skills", return_value=[]), \
         patch("app.repositories.supabase_repository.list_skills", return_value=[]):
        resp = client.get("/api/opportunities?is_demo=false")
        assert resp.status_code == 200
        ids = [o["id"] for o in resp.json()]
        assert "opp-real-active" in ids
        assert "opp-expired" not in ids

    with patch("app.repositories.supabase_repository.list_jobs", side_effect=SupabaseRepositoryError("DB fail")):
        resp_fail = client.get("/api/opportunities?is_demo=false")
        assert resp_fail.status_code == 503


def test_canonical_skill_linking():
    raw = {
        "title": "FastAPI and Python Backend Specialist",
        "company": "Infosys",
        "apply_url": "https://infosys.com",
        "description": "Building microservices with Python, FastAPI, and PostgreSQL database.",
    }
    norm, err = validate_and_normalize(raw, is_demo=False, is_trusted_feed=True)
    assert err is None
    assert norm is not None
    assert any("python" in s.lower() for s in norm["skills"])


def test_unmapped_skill_preservation():
    raw = {
        "title": "LLM AI Engineer",
        "company": "AI Labs",
        "apply_url": "https://ailabs.com",
        "description": "Developing generative systems with langchain, pytorch, and kubernetes infrastructure.",
    }
    norm, err = validate_and_normalize(raw, is_demo=False, is_trusted_feed=True)
    assert err is None
    assert norm is not None
    unmapped_lower = [u.lower() for u in norm["unmapped_skills"]]
    assert any(token in unmapped_lower for token in ["langchain", "pytorch", "kubernetes"])


def test_existing_phase12_behavior_remains_intact(client):
    resp_gov = client.get("/api/gov/opportunities?is_demo=true")
    assert resp_gov.status_code == 200

    resp_schemes = client.get("/api/schemes?is_demo=true")
    assert resp_schemes.status_code == 200


def test_job_id_deterministic_uuid5_generation():
    raw = {
        "id": "provider-external-12345",
        "title": "Machine Learning Engineer",
        "company": "Persistent",
        "district": "Pune",
        "apply_url": "https://persistent.com/careers/ml",
        "source": "ADZUNA_API",
        "external_id": "adz-12345",
    }
    norm1, err1 = validate_and_normalize(raw, is_demo=False, is_trusted_feed=True)
    assert err1 is None
    assert norm1 is not None
    parsed_uuid = uuid.UUID(norm1["id"])
    assert str(parsed_uuid) == norm1["id"]
    assert norm1["external_id"] == "adz-12345"

    norm2, err2 = validate_and_normalize(raw, is_demo=False, is_trusted_feed=True)
    assert norm2["id"] == norm1["id"]

    demo_raw = {
        "id": "job-0001",
        "title": "DevOps Engineer",
        "company": "Persistent Systems",
        "district": "Pune",
        "apply_url": "https://example.com/demo",
        "is_demo": True,
    }
    demo_norm, demo_err = validate_and_normalize(demo_raw, is_demo=True, is_trusted_feed=False)
    assert demo_err is None
    assert demo_norm["id"] == "job-0001"


def test_sync_engine_skips_invalid_jobs_without_fallback():
    from app.ingestion.sync_engine import SyncEngine
    engine = SyncEngine()
    invalid_raw = {
        "title": "A",
        "company": "",
        "source": "ADZUNA_API",
        "external_id": "invalid-1",
    }
    with patch("app.ingestion.sync_engine.is_explicit_demo_mode", return_value=True):
        added, updated = engine._upsert_jobs([invalid_raw])
        assert added == 0
        assert updated == 0


def test_post_jobs_persists_job_skills_linkages(client, employer_headers):
    mock_saved = {
        "id": "3b6a9c18-9715-4673-89b0-137bfa5db2f4",
        "title": "Python Developer",
        "company": "Tata Consultancy",
        "district": "Pune",
        "industry": "IT",
        "description": "Building FastAPI applications with Python skills.",
        "opportunity_type": "job",
        "apply_url": "https://tcs.com/apply",
        "status": "pending",
        "is_active": False,
        "verification_status": "PENDING",
    }
    mock_master_skills = [
        {"id": "550e8400-e29b-41d4-a716-446655440000", "name": "Python", "synonyms": ["python3"]},
        {"id": "550e8400-e29b-41d4-a716-446655440001", "name": "FastAPI", "synonyms": []},
    ]
    captured_links = []
    with patch("app.routers.jobs.save_job", return_value=mock_saved), \
         patch("app.repositories.supabase_repository.list_skills", return_value=mock_master_skills), \
         patch("app.repositories.supabase_repository.batch_create_job_skills", side_effect=lambda links: captured_links.extend(links)):
        payload = {
            "title": "Python Developer",
            "company": "Tata Consultancy",
            "district": "Pune",
            "industry": "IT",
            "description": "Building FastAPI applications with Python skills.",
            "apply_url": "https://tcs.com/apply",
            "skills": ["Python", "FastAPI", "NonExistentSkill123"],
        }
        resp = client.post("/api/jobs", json=payload, headers=employer_headers)
        assert resp.status_code == 201
        assert len(captured_links) == 2
        linked_skill_ids = [link["skill_id"] for link in captured_links]
        assert "550e8400-e29b-41d4-a716-446655440000" in linked_skill_ids
        assert "550e8400-e29b-41d4-a716-446655440001" in linked_skill_ids
        for link in captured_links:
            assert link["job_id"] == "3b6a9c18-9715-4673-89b0-137bfa5db2f4"


def test_jobs_endpoints_demo_mode_consistency(client):
    mock_jobs = [
        {
            "id": "550e8400-e29b-41d4-a716-446655440010",
            "title": "Verified Real Software Engineer",
            "company": "Tech Corp",
            "district": "Pune",
            "industry": "IT",
            "status": "active",
            "is_active": True,
            "verification_status": "VERIFIED",
            "is_demo": False,
        },
        {
            "id": "job-demo-leak",
            "title": "Leaked Synthetic Job",
            "company": "Fake Corp",
            "district": "Pune",
            "industry": "IT",
            "status": "active",
            "is_active": True,
            "verification_status": "VERIFIED",
            "source": "DEMO_SYNTHETIC",
            "is_demo": True,
        },
    ]
    called_kwargs = {}
    def mock_list_jobs(**kwargs):
        called_kwargs.update(kwargs)
        return mock_jobs

    with patch("app.repositories.supabase_repository.list_jobs", side_effect=mock_list_jobs):
        resp = client.get("/api/jobs")
        assert resp.status_code == 200
        assert called_kwargs.get("is_demo") is False
        assert called_kwargs.get("status") == "active"
        assert called_kwargs.get("is_active") is True
        data = resp.json()
        ids = [j["id"] for j in data]
        assert "550e8400-e29b-41d4-a716-446655440010" in ids
        assert "job-demo-leak" not in ids


def test_job_matching_strict_verified_only():
    profile = {
        "id": "usr-student-test",
        "skills": ["Python", "FastAPI"],
    }
    candidate_jobs = [
        {
            "id": "550e8400-e29b-41d4-a716-446655440020",
            "title": "Verified Developer",
            "company": "Corp A",
            "district": "Pune",
            "skills": ["Python"],
            "verification_status": "VERIFIED",
            "status": "active",
            "is_active": True,
        },
        {
            "id": "550e8400-e29b-41d4-a716-446655440021",
            "title": "Pending Developer",
            "company": "Corp B",
            "district": "Pune",
            "skills": ["Python"],
            "verification_status": "PENDING",
            "status": "active",
            "is_active": True,
        },
        {
            "id": "550e8400-e29b-41d4-a716-446655440022",
            "title": "Rejected Developer",
            "company": "Corp C",
            "district": "Pune",
            "skills": ["Python"],
            "verification_status": "REJECTED",
            "status": "active",
            "is_active": True,
        },
        {
            "id": "550e8400-e29b-41d4-a716-446655440023",
            "title": "Unverified Developer",
            "company": "Corp D",
            "district": "Pune",
            "skills": ["Python"],
            "verification_status": "UNVERIFIED",
            "status": "active",
            "is_active": True,
        },
        {
            "id": "550e8400-e29b-41d4-a716-446655440024",
            "title": "Missing Verification Developer",
            "company": "Corp E",
            "district": "Pune",
            "skills": ["Python"],
            "status": "active",
            "is_active": True,
        },
        {
            "id": "550e8400-e29b-41d4-a716-446655440025",
            "title": "Malformed Developer",
            "company": "Corp F",
            "district": "Pune",
            "skills": ["Python"],
            "verification_status": "MALFORMED_STATUS",
            "status": "active",
            "is_active": True,
        },
    ]
    matches = match_student_to_jobs(profile, candidate_jobs)
    matched_ids = [m["job_id"] for m in matches]
    assert "550e8400-e29b-41d4-a716-446655440020" in matched_ids
    assert "550e8400-e29b-41d4-a716-446655440021" not in matched_ids
    assert "550e8400-e29b-41d4-a716-446655440022" not in matched_ids
    assert "550e8400-e29b-41d4-a716-446655440023" not in matched_ids
    assert "550e8400-e29b-41d4-a716-446655440024" not in matched_ids
    assert "550e8400-e29b-41d4-a716-446655440025" not in matched_ids
