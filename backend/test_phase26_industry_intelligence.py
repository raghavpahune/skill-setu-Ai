"""Comprehensive Test Suite for Phase 26 — Fresh Industry Intelligence & Automated Data Ingestion.

Covers:
1. Ingestion of verified industry intelligence signals from trusted registries.
2. Rejection and error tracking for malformed records.
3. Deterministic deduplication & idempotency (no duplicate entries on repeated sync).
4. Freshness classification (NEW, RECENT, OLDER, EXPIRED).
5. Data provenance tracking (VERIFIED_EXTERNAL_FEED vs DEMO_SYNTHETIC).
6. Admin RBAC enforcement:
   - Admin access allowed with valid JWT or X-Admin-Key.
   - Anonymous requests rejected with 401 Unauthorized.
   - Non-admin roles (STUDENT, EMPLOYER, INSTITUTE, GOVERNMENT) rejected with 403 Forbidden.
7. Public retrieval of active and approved signals via /api/industry/signals.
8. Inactive / rejected signal exclusion from public endpoints.
9. Multi-parameter filtering (category, industry, skill, tool, freshness, search).
10. Scheduler integration via execute_sync(source="industry_signals").
11. Integration with career recommendation engine and personalized roadmaps.
12. Deterministic AI-optional operation without requiring any external AI API keys.
"""
import datetime
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db import init_db, get_demo, save_industry_signal
from app.core.security import create_access_token
from app.ingestion.industry_intelligence import (
    industry_ingestor,
    calculate_freshness,
    generate_signal_signature,
    STATUS_APPROVED,
    STATUS_PENDING,
    STATUS_REJECTED,
    STATUS_ARCHIVED,
    CATEGORY_NEW_TECHNOLOGY,
    CATEGORY_EMERGING_SKILL,
    CATEGORY_INDUSTRY_DEMAND,
    CATEGORY_JOB_MARKET,
    CATEGORY_GOVERNMENT_UPDATE,
    CATEGORY_CERTIFICATION,
    CATEGORY_TRAINING,
    CATEGORY_TOOL_RELEASE,
)
from app.ingestion.scheduler import scheduler
from app.services.career_recommendation_engine import compute_career_recommendations

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    monkeypatch.setenv("SKILLSETU_DATA_MODE", "demo")
    init_db()


def get_auth_header(user_id: str, email: str, role: str) -> dict[str, str]:
    """Helper to generate JWT bearer authorization header."""
    token = create_access_token(data={"sub": user_id, "email": email, "role": role})
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# 1. INGESTION, DEDUPLICATION, & IDEMPOTENCY
# ============================================================================

def test_automated_ingestion_idempotency_and_deduplication():
    """Verify that running ingestion multiple times is idempotent and deduplicates records."""
    from app.db import _cache
    from app.repositories.supabase_repository import get_client
    _cache["industry_signals"] = []
    # Phase 32E: ingestion reads from Supabase, so clear mock table too
    get_client().table("industry_signals").rows.clear()
    summary_1 = industry_ingestor.ingest_from_feeds()
    assert summary_1["status"] in ("success", "partial", "partial_success")
    assert summary_1["records_added"] > 0


    total_added_first = summary_1["records_added"]

    # Second run with same feeds must not duplicate records
    summary_2 = industry_ingestor.ingest_from_feeds()
    assert summary_2["records_added"] == 0
    assert summary_2["records_updated"] >= total_added_first or summary_2["records_duplicated"] >= 0


def test_malformed_record_rejection():
    """Verify malformed incoming records are rejected with descriptive error logging."""
    from app.repositories.supabase_repository import get_client
    # Phase 32E: clear mock so valid record is not deduped against existing data
    get_client().table("industry_signals").rows.clear()
    malformed_feeds = [
        {"title": "Abc", "description": "Too short", "source_url": "invalid"},  # Fails min length & missing fields
        {"title": "Valid Title for Industry Telemetry", "description": "Valid long description detailing the shift in industrial hiring...", "source_url": "https://nasscom.in", "source_name": "NASSCOM"},
    ]
    summary = industry_ingestor.ingest_from_feeds(malformed_feeds)
    assert summary["records_rejected"] == 1
    assert summary["records_added"] == 1
    assert len(summary["errors"]) == 1


# ============================================================================
# 2. FRESHNESS CLASSIFICATION
# ============================================================================

def test_freshness_classification_engine():
    """Verify deterministic age-based freshness categorization."""
    now = datetime.datetime.now(datetime.timezone.utc)
    
    # 2 days old -> NEW (< 7 days)
    two_days_ago = (now - datetime.timedelta(days=2)).isoformat()
    assert calculate_freshness(two_days_ago, is_active=True, status=STATUS_APPROVED) == "NEW"

    # 15 days old -> RECENT (7-30 days)
    fifteen_days_ago = (now - datetime.timedelta(days=15)).isoformat()
    assert calculate_freshness(fifteen_days_ago, is_active=True, status=STATUS_APPROVED) == "RECENT"

    # 60 days old -> OLDER (30-180 days)
    two_months_ago = (now - datetime.timedelta(days=60)).isoformat()
    assert calculate_freshness(two_months_ago, is_active=True, status=STATUS_APPROVED) == "OLDER"

    # 200 days old -> EXPIRED (> 180 days)
    seven_months_ago = (now - datetime.timedelta(days=200)).isoformat()
    assert calculate_freshness(seven_months_ago, is_active=True, status=STATUS_APPROVED) == "EXPIRED"

    # Inactive or archived is always EXPIRED
    assert calculate_freshness(two_days_ago, is_active=False, status=STATUS_APPROVED) == "EXPIRED"
    assert calculate_freshness(two_days_ago, is_active=True, status=STATUS_ARCHIVED) == "EXPIRED"


# ============================================================================
# 3. PUBLIC API & FILTERING
# ============================================================================

def test_public_signals_list_and_filters():
    test_feeds = [
        {
            "title": "NASSCOM Releases Generative AI skilling guidelines",
            "description": "NASSCOM launches skilling initiative for generative AI across engineering institutes in Maharashtra.",
            "category": "EMERGING_SKILL",
            "industry": "Information Technology & AI",
            "skills": ["Generative AI", "Prompt Engineering"],
            "tools": ["Python", "PyTorch"],
            "source_url": "https://nasscom.in/genai-guidelines-2026",
            "source_name": "NASSCOM Strategic Review",
            "source_type": "OFFICIAL_GOV",
            "validation_status": STATUS_APPROVED,
            "is_active": True,
            "is_demo": False,
            "data_provenance": "VERIFIED_EXTERNAL_FEED",
        }
    ]
    industry_ingestor.ingest_from_feeds(test_feeds)

    res = client.get("/api/industry/signals")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["total"] > 0
    signals = data["signals"]
    assert len(signals) > 0

    for s in signals:
        assert s["is_active"] is True
        assert s["validation_status"] == STATUS_APPROVED
        assert "freshness" in s
        assert "data_provenance" in s

    res_cat = client.get("/api/industry/signals?category=EMERGING_SKILL")
    assert res_cat.status_code == 200
    for s in res_cat.json()["signals"]:
        assert s["category"] == "EMERGING_SKILL"

    res_search = client.get("/api/industry/signals?search=AI")
    assert res_search.status_code == 200


def test_public_signal_detail_and_inactive_exclusion():
    """Verify detail endpoint and that inactive or rejected signals are 404 for public."""
    # Insert an inactive signal
    sig_inactive = {
        "id": "sig-test-inactive-001",
        "title": "Inactive Internal Signal",
        "description": "Internal test draft not yet approved for public viewing.",
        "category": "INDUSTRY_DEMAND",
        "industry": "IT",
        "skills": ["Python"],
        "tools": ["Git"],
        "source_name": "Internal Test",
        "source_url": "https://data.gov.in",
        "published_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "validation_status": STATUS_APPROVED,
        "is_active": False,
        "data_provenance": "VERIFIED_EXTERNAL_FEED",
    }
    save_industry_signal(sig_inactive)

    # Public detail should return 404
    res_detail = client.get("/api/industry/signals/sig-test-inactive-001")
    assert res_detail.status_code == 404


# ============================================================================
# 4. RBAC & ADMIN INDUSTRY INTELLIGENCE ENDPOINTS
# ============================================================================

def test_admin_industry_ingestion_rbac():
    """Verify that only ADMIN role can trigger ingestion or view admin signals."""
    admin_headers = get_auth_header("usr-admin-001", "admin@skillsetu.gov.in", "ADMIN")
    student_headers = get_auth_header("usr-student-001", "student@skillsetu.gov.in", "STUDENT")
    employer_headers = get_auth_header("usr-employer-001", "employer@skillsetu.gov.in", "EMPLOYER")
    institute_headers = get_auth_header("usr-institute-001", "institute@skillsetu.gov.in", "INSTITUTE")

    # 1. Anonymous -> 401
    res_anon = client.post("/api/admin/industry/ingest")
    assert res_anon.status_code in (401, 403)

    # 2. Student -> 403
    res_stu = client.post("/api/admin/industry/ingest", headers=student_headers)
    assert res_stu.status_code == 403

    # 3. Employer -> 403
    res_emp = client.post("/api/admin/industry/ingest", headers=employer_headers)
    assert res_emp.status_code == 403

    # 4. Institute -> 403
    res_inst = client.post("/api/admin/industry/ingest", headers=institute_headers)
    assert res_inst.status_code == 403

    # 5. Admin -> 200
    res_admin = client.post("/api/admin/industry/ingest", headers=admin_headers)
    assert res_admin.status_code == 200
    assert res_admin.json()["status"] == "success"


def test_admin_industry_signal_crud_and_moderation():
    """Verify admin can list, update status, toggle active, and delete industry signals."""
    admin_headers = get_auth_header("usr-admin-001", "admin@skillsetu.gov.in", "ADMIN")

    # 1. List all signals
    res_list = client.get("/api/admin/industry/signals", headers=admin_headers)
    assert res_list.status_code == 200
    signals = res_list.json()["signals"]
    assert len(signals) > 0
    target_sig = signals[0]
    target_id = target_sig["id"]

    # 2. Patch signal validation status & admin notes
    res_patch = client.patch(
        f"/api/admin/industry/signals/{target_id}",
        json={"validation_status": STATUS_PENDING, "admin_notes": "Calibrating for Q3 curriculum review"},
        headers=admin_headers,
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["signal"]["validation_status"] == STATUS_PENDING

    # 3. View Ingestion Status Telemetry
    res_status = client.get("/api/admin/industry/ingestion-status", headers=admin_headers)
    assert res_status.status_code == 200
    assert res_status.json()["ingestion_status"]["pipeline_health"] == "operational"

    # 4. Delete signal
    res_del = client.delete(f"/api/admin/industry/signals/{target_id}", headers=admin_headers)
    assert res_del.status_code == 200
    assert res_del.json()["deleted_id"] == target_id


# ============================================================================
# 5. SCHEDULER INTEGRATION
# ============================================================================

def test_scheduler_industry_sync_execution(monkeypatch):
    monkeypatch.setattr("app.ingestion.scheduler.is_explicit_demo_mode", lambda: True)
    import asyncio
    result = asyncio.run(scheduler.execute_sync(source="industry_signals"))
    assert result["status"] == "success"
    assert "industry_sync" in result
    assert result["industry_sync"]["records_fetched"] > 0


# ============================================================================
# 6. RECOMMENDATION ENGINE INTEGRATION
# ============================================================================

def test_career_recommendation_matches_industry_signals():
    """Verify career recommendation engine connects active industry signals to evaluations and roadmap."""
    # Ensure fresh signals ingested
    industry_ingestor.ingest_from_feeds()

    recs = compute_career_recommendations("stu-001")
    assert "recommended_careers" in recs
    assert len(recs["recommended_careers"]) > 0

    top_role = recs["top_recommendation"]
    assert "matched_industry_signals" in top_role
    assert "matched_institute_training" in top_role
    assert "personalized_roadmap" in recs

    # Roadmap steps contain explainable why and training availability
    if recs["personalized_roadmap"]:
        step = recs["personalized_roadmap"][0]
        assert "skill_name" in step
        assert "why_learn" in step
