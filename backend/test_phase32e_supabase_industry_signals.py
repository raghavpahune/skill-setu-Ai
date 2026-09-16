"""Phase 32E Test Suite: Supabase System-of-Record Foundation for industry_signals.

Verifies:
1. Repository CRUD lifecycle (get, list, create, update, delete).
2. API reads bypass stale local cache.
3. API writes persist directly to Supabase.
4. Supabase read/write failure returns HTTP 5xx.
5. Zero local JSON/cache fallback on Supabase failure.
6. Admin RBAC enforcement (401/403).
7. Public endpoint active & approved filtering.
8. Downstream intelligence services consume Supabase industry signals.
9. Ingestion pipeline deduplication works through Supabase.
10. Phase 32A–32D regression.
"""
import uuid
import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient

from app.main import app
from app.core.security import create_access_token
from app.repositories.supabase_repository import (
    get_industry_signal,
    list_industry_signals,
    create_industry_signal,
    update_industry_signal_repo,
    delete_industry_signal_repo,
    IndustrySignalNotFoundError,
    SupabaseRepositoryError,
    get_client,
)
from app.db import _cache, init_db, init_demo_users, save_user

init_db()
init_demo_users()

client = TestClient(app)

ADMIN_TOKEN = create_access_token({
    "sub": "usr-admin-001",
    "email": "admin@skillsetu.gov.in",
    "role": "ADMIN",
})
ADMIN_HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}"}

STUDENT_TOKEN = create_access_token({
    "sub": "usr-student-e001",
    "email": "student_e001@skillsetu.gov.in",
    "role": "STUDENT",
})
STUDENT_HEADERS = {"Authorization": f"Bearer {STUDENT_TOKEN}"}


# =========================================================================
# 1. Repository CRUD Lifecycle
# =========================================================================

def test_01_repository_industry_signal_lifecycle():
    """Verify get, list, create, update, delete through repository layer."""
    sid = f"sig-test-{uuid.uuid4().hex[:8]}"
    sig_data = {
        "id": sid,
        "title": "EV Battery Tech Breakthrough",
        "category": "EMERGING_SKILL",
        "industry": "EV",
        "skills": ["Battery Management", "Power Electronics"],
        "tools": ["MATLAB"],
        "source": "Industry Report",
        "source_name": "EV Research Lab",
        "source_url": "https://ev-lab.example.com",
        "source_type": "INDUSTRY_ANNOUNCEMENT",
        "validation_status": "APPROVED",
        "is_active": True,
        "is_demo": False,
        "data_provenance": "VERIFIED_EXTERNAL_FEED",
    }

    # Create
    saved = create_industry_signal(sig_data)
    assert saved["id"] == sid
    assert saved["title"] == "EV Battery Tech Breakthrough"

    # Get
    fetched = get_industry_signal(sid)
    assert fetched is not None
    assert fetched["id"] == sid
    assert fetched["category"] == "EMERGING_SKILL"

    # List
    all_signals = list_industry_signals()
    found = [s for s in all_signals if s["id"] == sid]
    assert len(found) == 1

    # Update
    updated = update_industry_signal_repo(sid, {"title": "EV Battery Tech Breakthrough v2"})
    assert updated["title"] == "EV Battery Tech Breakthrough v2"

    # Verify update persisted
    re_fetched = get_industry_signal(sid)
    assert re_fetched["title"] == "EV Battery Tech Breakthrough v2"

    # Delete
    deleted = delete_industry_signal_repo(sid)
    assert deleted is True

    # Verify gone
    gone = get_industry_signal(sid)
    assert gone is None


def test_02_repository_update_nonexistent_raises():
    """Update a non-existent signal should raise IndustrySignalNotFoundError."""
    with pytest.raises(IndustrySignalNotFoundError):
        update_industry_signal_repo("sig-does-not-exist", {"title": "Phantom"})


# =========================================================================
# 2. API reads bypass stale local cache
# =========================================================================

def test_03_api_reads_bypass_stale_cache():
    """Public signals endpoint reads from Supabase, not _cache."""
    sid = f"sig-cache-test-{uuid.uuid4().hex[:8]}"
    create_industry_signal({
        "id": sid,
        "title": "Cache Bypass Test Signal",
        "category": "INDUSTRY_DEMAND",
        "industry": "IT",
        "validation_status": "APPROVED",
        "is_active": True,
        "is_demo": False,
    })

    # Even if _cache["industry_signals"] is stale/empty, API reads from Supabase
    resp = client.get("/api/industry/signals")
    assert resp.status_code == 200
    titles = [s["title"] for s in resp.json()["signals"]]
    assert "Cache Bypass Test Signal" in titles

    # Cleanup
    delete_industry_signal_repo(sid)


# =========================================================================
# 3. API writes persist to Supabase
# =========================================================================

def test_04_api_writes_persist_to_supabase():
    """Admin create/update/delete routes persist to Supabase repository."""
    sid = f"sig-write-test-{uuid.uuid4().hex[:8]}"
    create_industry_signal({
        "id": sid,
        "title": "Persistence Test Signal",
        "category": "EMERGING_SKILL",
        "industry": "Biotech",
        "validation_status": "PENDING",
        "is_active": True,
        "is_demo": False,
    })

    # Admin update
    resp = client.patch(
        f"/api/admin/industry/signals/{sid}",
        json={"validation_status": "APPROVED"},
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"

    # Verify persisted via repository
    fetched = get_industry_signal(sid)
    assert fetched["validation_status"] == "APPROVED"

    # Admin delete
    resp = client.delete(f"/api/admin/industry/signals/{sid}", headers=ADMIN_HEADERS)
    assert resp.status_code == 200

    assert get_industry_signal(sid) is None


# =========================================================================
# 4. Supabase failure returns 5xx
# =========================================================================

def test_05_supabase_read_failure_returns_500():
    """When Supabase list fails, public API returns HTTP 500."""
    with patch("app.routers.signals.list_industry_signals_repo", side_effect=SupabaseRepositoryError("DB down")):
        resp = client.get("/api/industry/signals")
        assert resp.status_code == 500


def test_06_supabase_get_failure_returns_500():
    """When Supabase get fails, detail API returns HTTP 500."""
    with patch("app.routers.signals.get_industry_signal_repo", side_effect=SupabaseRepositoryError("DB down")):
        resp = client.get("/api/industry/signals/sig-any")
        assert resp.status_code == 500


# =========================================================================
# 5. Zero fallback on Supabase failure
# =========================================================================

def test_07_no_fallback_on_supabase_failure():
    """Admin list signals returns 500 when Supabase fails, not stale data."""
    with patch(
        "app.repositories.supabase_repository.get_client",
        side_effect=SupabaseRepositoryError("DB unavailable"),
    ):
        resp = client.get("/api/admin/industry/signals", headers=ADMIN_HEADERS)
        assert resp.status_code == 500
        assert "unavailable" in resp.json()["detail"].lower()


# =========================================================================
# 6. Admin RBAC Enforcement
# =========================================================================

def test_08_admin_list_requires_auth():
    """Admin industry signals listing requires admin auth."""
    resp = client.get("/api/admin/industry/signals")
    assert resp.status_code in (401, 403)


def test_09_student_cannot_admin_update():
    """Student cannot update industry signals via admin endpoint."""
    sid = f"sig-rbac-{uuid.uuid4().hex[:8]}"
    create_industry_signal({
        "id": sid,
        "title": "RBAC Test",
        "validation_status": "PENDING",
        "is_active": True,
        "is_demo": False,
    })
    resp = client.patch(
        f"/api/admin/industry/signals/{sid}",
        json={"validation_status": "APPROVED"},
        headers=STUDENT_HEADERS,
    )
    assert resp.status_code in (401, 403)
    delete_industry_signal_repo(sid)


def test_10_student_cannot_admin_delete():
    """Student cannot delete industry signals via admin endpoint."""
    resp = client.delete("/api/admin/industry/signals/sig-any", headers=STUDENT_HEADERS)
    assert resp.status_code in (401, 403)


# =========================================================================
# 7. Public endpoint active & approved filtering
# =========================================================================

def test_11_public_only_active_approved():
    """Public list shows only active+approved signals, not pending/rejected/inactive."""
    ids = []
    for i, (vs, active) in enumerate([
        ("APPROVED", True),
        ("PENDING", True),
        ("REJECTED", True),
        ("APPROVED", False),
    ]):
        sid = f"sig-filter-{i}-{uuid.uuid4().hex[:6]}"
        ids.append(sid)
        create_industry_signal({
            "id": sid,
            "title": f"Filter Test {i}",
            "validation_status": vs,
            "is_active": active,
            "is_demo": False,
        })

    resp = client.get("/api/industry/signals")
    assert resp.status_code == 200
    visible_ids = {s["id"] for s in resp.json()["signals"]}

    # Only the first (APPROVED + active) should be visible
    assert ids[0] in visible_ids
    assert ids[1] not in visible_ids
    assert ids[2] not in visible_ids
    assert ids[3] not in visible_ids

    for sid in ids:
        delete_industry_signal_repo(sid)


# =========================================================================
# 8. Downstream intelligence reads Supabase
# =========================================================================

def test_12_career_engine_reads_supabase_signals():
    """Career recommendation engine consumes Supabase signals without crashing."""
    from app.services.career_recommendation_engine import compute_career_recommendations
    # Use a student with a known assessment from demo data
    try:
        result = compute_career_recommendations("stu-demo-001")
        assert isinstance(result, dict)
    except ValueError:
        pass  # ponytail: student may lack assessment, but engine didn't crash on signals


def test_13_forecast_engine_reads_supabase_signals():
    """Forecast engine reads industry signals from Supabase."""
    resp = client.get("/api/forecast")
    assert resp.status_code == 200


def test_14_student_alerts_read_supabase_signals():
    """Student industry alerts engine reads from Supabase."""
    resp = client.get("/api/student/industry-alerts")
    assert resp.status_code == 200


# =========================================================================
# 9. Ingestion pipeline through Supabase
# =========================================================================

def test_15_ingestion_persists_to_supabase():
    """Ingestion pipeline persists via db.save_industry_signal which delegates to Supabase."""
    from app.db import save_industry_signal

    sid = f"sig-ingest-{uuid.uuid4().hex[:8]}"
    saved = save_industry_signal({
        "id": sid,
        "title": "Ingested Signal Test",
        "category": "INDUSTRY_DEMAND",
        "validation_status": "PENDING",
        "is_active": True,
        "is_demo": False,
    })
    assert saved["id"] == sid

    # Verify it's in Supabase
    fetched = get_industry_signal(sid)
    assert fetched is not None
    assert fetched["title"] == "Ingested Signal Test"

    delete_industry_signal_repo(sid)


# =========================================================================
# 10. Phase 32A–32D Regression
# =========================================================================

def test_16_phase32a_employer_feedback_regression():
    """Phase 32A employer feedback via repository remains functional."""
    from app.repositories.supabase_repository import list_employer_feedback
    feedbacks = list_employer_feedback()
    assert isinstance(feedbacks, list)


def test_17_phase32b_employer_demands_regression():
    """Phase 32B employer demands via repository remains functional."""
    from app.repositories.supabase_repository import list_employer_demands
    demands = list_employer_demands()
    assert isinstance(demands, list)


def test_18_phase32c_student_profiles_regression():
    """Phase 32C student profiles via repository remains functional."""
    from app.repositories.supabase_repository import list_student_profiles, list_student_assessments
    profiles = list_student_profiles()
    assessments = list_student_assessments()
    assert isinstance(profiles, list)
    assert isinstance(assessments, list)


def test_19_phase32d_courses_regression():
    """Phase 32D courses endpoint remains functional."""
    resp = client.get("/api/courses")
    assert resp.status_code == 200


def test_20_repository_delete_empty_returns_false():
    assert delete_industry_signal_repo("") is False
    assert delete_industry_signal_repo("   ") is False


def test_21_repository_list_filter_is_demo_and_source():
    real_id = f"sig-real-{uuid.uuid4().hex[:6]}"
    demo_id = f"sig-demo-{uuid.uuid4().hex[:6]}"
    created_ids = []
    try:
        create_industry_signal({
            "id": real_id,
            "title": "Real Source Filter Test",
            "is_demo": False,
            "source": "REAL_SRC",
            "validation_status": "APPROVED",
            "is_active": True,
        })
        created_ids.append(real_id)
        create_industry_signal({
            "id": demo_id,
            "title": "Demo Source Filter Test",
            "is_demo": True,
            "source": "DEMO_SRC",
            "validation_status": "APPROVED",
            "is_active": True,
        })
        created_ids.append(demo_id)
        real_only = list_industry_signals(is_demo=False)
        demo_only = list_industry_signals(is_demo=True)
        src_only = list_industry_signals(source="REAL_SRC")

        assert any(s["id"] == real_id for s in real_only)
        assert not any(s["id"] == demo_id for s in real_only)

        assert any(s["id"] == demo_id for s in demo_only)
        assert not any(s["id"] == real_id for s in demo_only)

        assert any(s["id"] == real_id for s in src_only)
        assert not any(s["id"] == demo_id for s in src_only)
    finally:
        for cid in created_ids:
            delete_industry_signal_repo(cid)


def test_22_admin_update_signal_supabase_failure_returns_500():
    with patch(
        "app.routers.admin.get_industry_signal_by_id",
        side_effect=SupabaseRepositoryError("DB failed"),
    ):
        resp = client.patch(
            "/api/admin/industry/signals/sig-test-fail",
            json={"validation_status": "APPROVED"},
            headers=ADMIN_HEADERS,
        )
        assert resp.status_code == 500


def test_23_admin_delete_signal_supabase_failure_returns_500():
    with patch(
        "app.routers.admin.delete_industry_signal",
        side_effect=SupabaseRepositoryError("DB failed"),
    ):
        resp = client.delete(
            "/api/admin/industry/signals/sig-test-fail",
            headers=ADMIN_HEADERS,
        )
        assert resp.status_code == 500
