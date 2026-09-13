"""Comprehensive Production-Readiness & Fail-Closed Tests for SkillSetu Real-Data Pipeline.

Validates all 22 required audit scenarios:
1. Missing Adzuna credentials -> VERIFIED_SNAPSHOT, historical capture date, STRUCTURAL_API_VALIDATION
2. Missing data.gov credentials -> SANDBOX_SIMULATION, is_demo=True, UNVERIFIED, confidence=35
3. API timeout -> Graceful timeout handling & fallback
4. HTTP 429 -> Rate limit backoff & retry
5. HTTP 500 -> Server error retry & fallback
6. Malformed JSON -> Handled gracefully without crash
7. Invalid required fields -> Pydantic rejection without crash
8. Invalid source URL -> Verification failure (INVALID_URL)
9. Duplicate content hash -> Increments records_updated, not records_added
10. Stale posting -> Freshness marks STALE (>90d) and EXPIRED (>180d)
11. Snapshot freshness -> Historical snapshot is OLDER, not falsely labeled NEW
12. Verification failure -> Invalid employer or title marked UNVERIFIED
13. Supabase unavailable -> Raises SupabaseConnectionError / controlled failure
14. Supabase schema missing columns -> VALID_JOB_COLUMNS and VALID_SCHEME_COLUMNS check
15. Explicit demo mode -> Explicit demo persona / is_demo=True allowed demo fixtures
16. Real user with Supabase unavailable -> Fails closed without injecting demo jobs
17. Real user with no authoritative jobs -> Receives empty jobs, not synthetic demo jobs
18. Downstream services receiving authoritative jobs -> Influences gaps and forecast
19. Sandbox data never labeled VERIFIED/LIVE -> Never receives LIVE_API or VERIFIED
20. Historical snapshots never labeled LIVE_API -> Classified VERIFIED_SNAPSHOT
21. No timestamp reset on snapshot -> Historical capture date preserved
22. Unmapped skill preservation -> Technical keywords captured in unmapped_skills
"""
import datetime
from unittest.mock import MagicMock, patch
import pydantic
import pytest
import httpx

from app.ingestion.base_adapter import (
    compute_content_hash,
    compute_freshness,
    extract_skills_and_unmapped,
    normalize_maharashtra_district,
    ProvenanceMetadata,
    SOURCE_TYPE_LIVE_API,
    SOURCE_TYPE_VERIFIED_SNAPSHOT,
    SOURCE_TYPE_SANDBOX_SIMULATION,
    SOURCE_TYPE_DEMO_SYNTHETIC,
)
from app.ingestion.adzuna_connector import (
    AdzunaConnector,
    RawAdzunaJob,
    ValidatedIngestedJob,
)
from app.ingestion.datagov_connector import (
    DataGovConnector,
    ValidatedIngestedScheme,
    ValidatedIngestedOpportunity,
    RESOURCE_SCHOLARSHIP_ALLOCATION,
    RESOURCE_NAPS_APPRENTICESHIP,
)
from app.ingestion.sync_engine import SyncEngine
from app.repositories.supabase_repository import (
    VALID_JOB_COLUMNS,
    VALID_SCHEME_COLUMNS,
    SupabaseConnectionError,
    SupabaseRepositoryError,
    set_supabase_client,
    reset_supabase_client,
    list_jobs,
)
from app.services.student_service import (
    get_personalized_industry_alerts,
    get_skill_explainability,
)
from app.services.gap_engine import compute_gaps
from app.services.forecast_engine import compute_multi_horizon_forecasts
from app.services.district_service import get_district_plan, get_all_districts


# ============================================================================
# 1. Missing Adzuna Credentials
# ============================================================================
def test_missing_adzuna_credentials_uses_verified_snapshot():
    connector = AdzunaConnector(app_id="", app_key="")
    assert not connector.has_credentials

    raw_jobs = connector.fetch_raw(is_demo=True)
    assert len(raw_jobs) >= 5
    for r in raw_jobs:
        assert r["is_snapshot"] is True
        assert r["snapshot_captured_at"] == "2026-08-31T12:00:00Z"

    transformed = connector.validate_and_transform(raw_jobs, master_skills=[])
    for job in transformed:
        assert job["source_type"] == SOURCE_TYPE_VERIFIED_SNAPSHOT
        assert job["is_snapshot"] is True
        assert job["is_demo"] is False
        assert "Historical" in job["source_label"]
        assert "Live" not in job["source_label"]
        assert job["verification_method"] == "STRUCTURAL_API_VALIDATION"
        assert job["fetched_at"] == "2026-08-31T12:00:00Z"


def test_missing_datagov_credentials_uses_sandbox_simulation():
    connector = DataGovConnector(api_key="")
    assert not connector.has_api_key

    raw_data = connector.fetch_resource(RESOURCE_SCHOLARSHIP_ALLOCATION, is_demo=True)
    records = raw_data.get("records", [])
    assert len(records) > 0

    schemes = connector.transform_scholarship_schemes(records)
    for s in schemes:
        assert s["source_type"] == SOURCE_TYPE_SANDBOX_SIMULATION
        assert s["is_demo"] is True
        assert s["is_snapshot"] is True
        assert s["verification_status"] == "UNVERIFIED"
        assert s["verification_method"] == "SANDBOX_SIMULATION"
        assert s["confidence"] == 35
        assert s["resource_id"] == RESOURCE_SCHOLARSHIP_ALLOCATION
        assert s["freshness_status"] == "UNKNOWN"


def test_api_timeout_handling():
    connector = AdzunaConnector(app_id="key", app_key="secret", timeout_seconds=0.1, max_retries=1)

    with patch("httpx.get", side_effect=httpx.TimeoutException("Connection timed out")):
        jobs = connector.fetch_raw(is_demo=True)
        assert len(jobs) >= 5
        assert jobs[0]["is_snapshot"] is True


def test_http_429_rate_limit_backoff():
    connector = AdzunaConnector(app_id="key", app_key="secret", max_retries=2)

    resp_429 = MagicMock(status_code=429, text="Too Many Requests")
    resp_200 = MagicMock(status_code=200)
    resp_200.json.return_value = {"results": [{"id": "live-429", "title": "Senior EV Engineer"}]}

    with patch("httpx.get", side_effect=[resp_429, resp_200]), patch("time.sleep") as mock_sleep:
        jobs = connector.fetch_raw()
        assert len(jobs) == 1
        assert jobs[0]["title"] == "Senior EV Engineer"
        assert mock_sleep.called


def test_http_500_server_error_fallback():
    connector = AdzunaConnector(app_id="key", app_key="secret", max_retries=1)

    resp_500 = MagicMock(status_code=500, text="Internal Server Error")
    with patch("httpx.get", return_value=resp_500):
        jobs = connector.fetch_raw(is_demo=True)
        assert len(jobs) >= 5
        assert jobs[0]["is_snapshot"] is True


# ============================================================================
# 6. Malformed JSON Handling
# ============================================================================
def test_malformed_json_handling():
    """Invalid/malformed response payload must be rejected gracefully without crash."""
    connector = AdzunaConnector()
    malformed_records = [
        {"id": "bad-json-1"},  # Missing title
        {"id": "bad-json-2", "title": "A"},  # Title too short
        {"not_even_an_id": 123},
    ]
    transformed = connector.validate_and_transform(malformed_records, master_skills=[])
    assert transformed == []


# ============================================================================
# 7. Invalid Required Fields
# ============================================================================
def test_invalid_required_fields_rejected():
    """Pydantic must reject models missing required fields."""
    with pytest.raises(pydantic.ValidationError):
        RawAdzunaJob(id="test-1")  # Missing title

    with pytest.raises(pydantic.ValidationError):
        ValidatedIngestedJob(
            id="job-1",
            title="Engineer",
            company="Tata Motors",
            district="Pune",
            industry="Manufacturing",
            # Missing apply_url, content_hash, etc.
        )


# ============================================================================
# 8. Invalid Source URL Verification
# ============================================================================
def test_invalid_source_url_verification():
    """Verification must reject javascript: or non-http URLs."""
    connector = AdzunaConnector()
    ok, method, conf = connector.verify_record({
        "source": "ADZUNA_API",
        "apply_url": "javascript:alert('attack')",
        "company": "Tata Motors",
        "title": "Robotics Specialist",
    })
    assert ok is False
    assert method == "INVALID_URL"
    assert conf == 0

    ok2, method2, _ = connector.verify_record({
        "source": "ADZUNA_API",
        "apply_url": "not_a_valid_url",
        "company": "Tata Motors",
        "title": "Robotics Specialist",
    })
    assert ok2 is False
    assert method2 == "INVALID_URL"


# ============================================================================
# 9. Duplicate Content Hash
# ============================================================================
def test_duplicate_content_hash_deduplication():
    """Identical jobs must produce matching hash and increment updated counter, not added."""
    h1 = compute_content_hash("Robotics Engineer", "Tata Motors", "Pune", "Manufacturing")
    h2 = compute_content_hash("  robotics engineer  ", "Tata Motors ", "pune", "manufacturing")
    assert h1 == h2

    engine = SyncEngine()
    test_job = {
        "id": "job-dedup-test-99",
        "title": "Robotics Engineer",
        "company": "Tata Motors",
        "district": "Pune",
        "industry": "Manufacturing",
        "source": "ADZUNA_API",
        "external_id": "adz-dup-99",
        "content_hash": h1,
        "is_demo": False,
    }

    added1, updated1 = engine._upsert_jobs([dict(test_job)])
    assert added1 == 1
    assert updated1 == 0

    added2, updated2 = engine._upsert_jobs([dict(test_job)])
    assert added2 == 0
    assert updated2 == 1


# ============================================================================
# 10. Stale Posting Freshness
# ============================================================================
def test_stale_posting_freshness():
    """compute_freshness must classify age ranges accurately."""
    now = datetime.datetime.now(datetime.timezone.utc)

    d_new = (now - datetime.timedelta(days=2)).isoformat()
    d_recent = (now - datetime.timedelta(days=20)).isoformat()
    d_older = (now - datetime.timedelta(days=60)).isoformat()
    d_stale = (now - datetime.timedelta(days=120)).isoformat()
    d_expired = (now - datetime.timedelta(days=250)).isoformat()

    assert compute_freshness(d_new) == "NEW"
    assert compute_freshness(d_recent) == "RECENT"
    assert compute_freshness(d_older) == "OLDER"
    assert compute_freshness(d_stale) == "STALE"
    assert compute_freshness(d_expired) == "EXPIRED"


# ============================================================================
# 11. Snapshot Freshness (No Reset to NEW)
# ============================================================================
def test_snapshot_freshness_preservation():
    """A snapshot captured in the past must NEVER be classified as NEW merely because it was ingested today."""
    # Historical snapshot date relative to now (e.g. 10 days ago -> RECENT)
    ten_days_ago = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=10)).isoformat()
    freshness = compute_freshness(snapshot_captured_at=ten_days_ago)
    assert freshness == "RECENT"
    # When no timestamp is present, must be UNKNOWN, NEVER NEW
    assert compute_freshness(None) == "UNKNOWN"
    assert compute_freshness("") == "UNKNOWN"


# ============================================================================
# 12. Verification Failure on Generic Employer or Title
# ============================================================================
def test_verification_failure_generic_employer():
    """Generic employers like N/A, Unknown, Test must fail verification."""
    connector = AdzunaConnector()
    ok, method, conf = connector.verify_record({
        "source": "ADZUNA_API",
        "apply_url": "https://example.com/job/1",
        "company": "N/A",
        "title": "Software Engineer",
    })
    assert ok is False
    assert method == "INVALID_EMPLOYER"
    assert conf == 20

    ok_title, method_title, _ = connector.verify_record({
        "source": "ADZUNA_API",
        "apply_url": "https://example.com/job/1",
        "company": "Valid Company Ltd",
        "title": "IT",
    })
    assert ok_title is False
    assert method_title == "INVALID_TITLE"


# ============================================================================
# 13. Supabase Unavailable Fail-Closed
# ============================================================================
def test_supabase_unavailable_handling():
    """When Supabase client is None / unconfigured, repository raises SupabaseConnectionError."""
    try:
        set_supabase_client(None)
        with patch("app.db.get_supabase_client", return_value=None):
            with pytest.raises(SupabaseConnectionError):
                list_jobs()
    finally:
        reset_supabase_client()


# ============================================================================
# 14. Supabase Schema Columns Present
# ============================================================================
def test_supabase_schema_columns_present():
    """Repository column definitions must include all required provenance columns."""
    required_job_cols = {
        "source_type", "is_snapshot", "resource_id", "published_at",
        "snapshot_captured_at", "last_seen_at", "unmapped_skills",
        "content_hash", "verification_method", "verification_status"
    }
    assert required_job_cols.issubset(VALID_JOB_COLUMNS)

    required_scheme_cols = {
        "source_type", "is_snapshot", "resource_id", "published_at",
        "snapshot_captured_at", "last_seen_at", "content_hash",
        "verification_method", "verification_status"
    }
    assert required_scheme_cols.issubset(VALID_SCHEME_COLUMNS)


# ============================================================================
# 15. Explicit Demo Mode
# ============================================================================
def test_explicit_demo_mode_allowed():
    """Explicit demo student persona is served demo fixtures."""
    # 'ast-demo-001' and 'demo-001' are explicit demo IDs
    alerts = get_personalized_industry_alerts(student_id="ast-demo-001")
    assert isinstance(alerts, dict)
    assert "alerts" in alerts or "signals" in alerts or "technology_alerts" in alerts

    with patch("app.repositories.supabase_repository.list_jobs", return_value=[]):
        expl = get_skill_explainability("Python", student_id="ast-demo-001")
        assert isinstance(expl, dict)
        demand_surge = expl["explainability"]["dimension_1_demand_surge"]
        assert demand_surge["active_vacancies_count"] > 0


# ============================================================================
# 16. Real User with Supabase Unavailable Fails Closed
# ============================================================================
def test_real_user_supabase_unavailable_fails_closed():
    """Real student request with Supabase unavailable does NOT inject demo jobs."""
    real_user_id = "usr-student-prod-999"

    # Simulate Supabase repository error when listing jobs
    with patch("app.repositories.supabase_repository.list_jobs", side_effect=Exception("Database down")):
        expl = get_skill_explainability("Python", student_id=real_user_id)
        # Should not fabricate job demand from demo fixtures
        demand_surge = expl["explainability"]["dimension_1_demand_surge"]
        assert demand_surge["active_vacancies_count"] == 0


# ============================================================================
# 17. Real User with No Authoritative Jobs
# ============================================================================
def test_real_user_empty_authoritative_jobs():
    """When Supabase has zero jobs, real user receives 0 jobs without silent fallback."""
    real_user_id = "usr-student-prod-888"

    with patch("app.repositories.supabase_repository.list_jobs", return_value=[]):
        expl = get_skill_explainability("Python", student_id=real_user_id)
        demand_surge = expl["explainability"]["dimension_1_demand_surge"]
        assert demand_surge["active_vacancies_count"] == 0


# ============================================================================
# 18. Downstream Services Receiving Authoritative Jobs
# ============================================================================
def test_downstream_services_receive_authoritative_jobs():
    """Authoritative repository jobs influence compute_gaps and forecast engine."""
    mock_authoritative_jobs = [
        {"id": "job-auth-01", "title": "BMS Specialist", "district": "Pune", "industry": "EV", "source": "ADZUNA_API"}
    ]
    mock_job_skills = [
        {"job_id": "job-auth-01", "skill_id": "sk-019", "proficiency_required": "intermediate"}
    ]

    with patch("app.repositories.supabase_repository.list_jobs", return_value=mock_authoritative_jobs), \
         patch("app.repositories.supabase_repository.list_job_skills", return_value=mock_job_skills):

        # compute_gaps in real mode (is_demo=False)
        gaps = compute_gaps(is_demo=False)
        assert isinstance(gaps, list)
        # sk-019 should have demand
        bms_gap = next((g for g in gaps if g["skill_id"] == "sk-019"), None)
        assert bms_gap is not None
        assert bms_gap["demand_count"] >= 1

        # forecast engine in real mode (is_demo=False)
        forecasts = compute_multi_horizon_forecasts(is_demo=False)
        assert isinstance(forecasts, list)
        assert len(forecasts) > 0


# ============================================================================
# 19. Sandbox Data Never Labeled VERIFIED/LIVE
# ============================================================================
def test_sandbox_data_never_labeled_verified_or_live():
    """Sandbox simulation records must never be labeled LIVE_API or VERIFIED."""
    connector = DataGovConnector(api_key="")
    raw_res = connector.fetch_resource(RESOURCE_NAPS_APPRENTICESHIP)
    records = raw_res.get("records", [])

    opps = connector.transform_naps_opportunities(records)
    for o in opps:
        assert o["source_type"] == SOURCE_TYPE_SANDBOX_SIMULATION
        assert o["source_type"] != SOURCE_TYPE_LIVE_API
        assert o["verification_status"] == "UNVERIFIED"
        assert o["verification_status"] != "VERIFIED"
        assert o["is_demo"] is True
        assert o["confidence"] == 35


# ============================================================================
# 20. Historical Snapshots Never Labeled LIVE_API
# ============================================================================
def test_historical_snapshots_never_labeled_live_api():
    """Historical snapshots must be labeled VERIFIED_SNAPSHOT, never LIVE_API."""
    connector = AdzunaConnector(app_id="", app_key="")
    raw_jobs = connector.fetch_raw()
    transformed = connector.validate_and_transform(raw_jobs, master_skills=[])

    for job in transformed:
        assert job["source_type"] == SOURCE_TYPE_VERIFIED_SNAPSHOT
        assert job["source_type"] != SOURCE_TYPE_LIVE_API
        assert job["is_snapshot"] is True
        assert "Historical" in job["source_label"]
        assert "Live" not in job["source_label"]


# ============================================================================
# 21. No Timestamp Reset on Snapshot Load
# ============================================================================
def test_no_timestamp_reset_on_snapshot_load():
    """Ingesting a snapshot today must preserve its historical capture date."""
    connector = AdzunaConnector(app_id="", app_key="")
    raw_jobs = connector.fetch_raw()
    transformed = connector.validate_and_transform(raw_jobs, master_skills=[])

    now_year = datetime.datetime.now(datetime.timezone.utc).year
    for job in transformed:
        assert job["fetched_at"] == "2026-08-31T12:00:00Z"
        assert job["snapshot_captured_at"] == "2026-08-31T12:00:00Z"


# ============================================================================
# 22. Unmapped Skill Preservation & Acronym Guard
# ============================================================================
def test_unmapped_skill_preservation():
    """Technical keywords not in taxonomy are preserved in unmapped_skills; short acronyms guarded."""
    master_skills = [
        {"id": "sk-python", "name": "Python", "synonyms": []},
        {"id": "sk-c", "name": "C", "synonyms": ["C programming"]},
        {"id": "sk-go", "name": "Go", "synonyms": ["Golang"]},
    ]

    # Case A: English prose with "go to our site" and "c level" should NOT match C or Go
    text_prose = "Please go to our site and apply. Looking for candidate to report to C suite."
    matched_prose, unmapped_prose = extract_skills_and_unmapped(text_prose, master_skills)
    matched_names_prose = [m["name"] for m in matched_prose]
    assert "C" not in matched_names_prose
    assert "Go" not in matched_names_prose

    # Case B: Technical description with C++, Golang, Kubernetes, Docker, BMS
    tech_text = (
        "Requires hands-on experience in C++ and Golang backend development. "
        "Must be proficient with Kubernetes, Docker, and EV BMS systems."
    )
    matched_tech, unmapped_tech = extract_skills_and_unmapped(tech_text, master_skills)
    matched_names_tech = [m["name"] for m in matched_tech]

    # Go matched via 'golang' synonym/pattern
    assert "Go" in matched_names_tech

    # Unmapped technical keywords preserved
    assert "Kubernetes" in unmapped_tech or "kubernetes" in [u.lower() for u in unmapped_tech]
    assert "Docker" in unmapped_tech or "docker" in [u.lower() for u in unmapped_tech]
    assert "BMS" in unmapped_tech or "bms" in [u.lower() for u in unmapped_tech]
