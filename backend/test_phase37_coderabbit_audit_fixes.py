import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import create_access_token, hash_password
from app.db import save_user, get_demo, set_demo
from app.ingestion.sync_engine import SyncEngine
from app.ingestion.source_orchestrator import (
    SourceOrchestrator,
    source_orchestrator as default_source_orchestrator,
    ExternalDataResponse,
    SOURCE_TYPE_LIVE_API,
    SOURCE_TYPE_DEMO_SYNTHETIC,
    WORKLOAD_JOBS,
    WORKLOAD_GOVERNMENT_SCHEMES,
    WORKLOAD_GOVERNMENT_DATASETS,
)
from app.services.career_recommendation_engine import _match_skills, _normalize_skill_text
from app.services.roadmap_service import _load_skills_map, compute_adaptive_roadmap
from app.repositories.supabase_repository import (
    list_skills,
    list_jobs,
    list_courses,
    list_job_skills,
    list_course_skills,
    SupabaseConnectionError,
)

client = TestClient(app)


def test_issue1_sync_trigger_unauthenticated_rejects_with_401():
    with patch("app.config.settings.admin_api_key", ""):
        res = client.post("/api/sync/trigger?source=data.gov.in")
        assert res.status_code == 401


def test_issue1_sync_trigger_student_bearer_rejects_with_403():
    save_user({
        "id": "usr-student-test-sync",
        "email": "student_sync@skillsetu.gov.in",
        "role": "STUDENT",
        "full_name": "Student Sync Tester",
        "hashed_password": hash_password("Password@123"),
    })
    token = create_access_token({"sub": "usr-student-test-sync", "email": "student_sync@skillsetu.gov.in", "role": "STUDENT"})
    res = client.post(
        "/api/sync/trigger?source=data.gov.in",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


def test_issue1_sync_trigger_admin_bearer_executes_scheduler():
    save_user({
        "id": "usr-admin-test-sync",
        "email": "admin_sync@skillsetu.gov.in",
        "role": "ADMIN",
        "full_name": "Admin Sync Tester",
        "hashed_password": hash_password("Password@123"),
    })
    token = create_access_token({"sub": "usr-admin-test-sync", "email": "admin_sync@skillsetu.gov.in", "role": "ADMIN"})
    mock_result = {"status": "success", "source": "data.gov.in"}
    with patch("app.ingestion.scheduler.scheduler.execute_sync", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = mock_result
        res = client.post(
            "/api/sync/trigger?source=data.gov.in",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        assert res.json() == mock_result
        mock_exec.assert_awaited_once_with(source="data.gov.in")


def test_issue1_sync_trigger_invalid_admin_key_rejects_with_401():
    with patch("app.config.settings.admin_api_key", "secret-admin-key-2026"):
        with patch("app.ingestion.scheduler.scheduler.execute_sync", new_callable=AsyncMock) as mock_exec:
            res = client.post(
                "/api/sync/trigger?source=data.gov.in",
                headers={"X-Admin-Key": "wrong-key"},
            )
            assert res.status_code == 401
            mock_exec.assert_not_called()


def test_issue1_sync_trigger_valid_admin_key_succeeds():
    mock_result = {"status": "success", "source": "adzuna"}
    with patch("app.config.settings.admin_api_key", "secret-admin-key-2026"):
        with patch("app.ingestion.scheduler.scheduler.execute_sync", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_result
            res = client.post(
                "/api/sync/trigger?source=adzuna",
                headers={"X-Admin-Key": "secret-admin-key-2026"},
            )
            assert res.status_code == 200
            assert res.json() == mock_result
            mock_exec.assert_awaited_once_with(source="adzuna")


def test_issue2_sync_engine_datagov_routes_through_source_orchestrator():
    mock_orch = MagicMock()
    mock_orch.fetch_data.return_value = ExternalDataResponse(
        source="data_gov_in",
        workload=WORKLOAD_GOVERNMENT_SCHEMES,
        status="NOT_CONFIGURED",
        provenance="NOT_CONFIGURED",
        records=[],
        records_count=0,
    )
    engine = SyncEngine(source_orchestrator=mock_orch)
    res = engine.run_sync("data.gov.in")
    assert mock_orch.fetch_data.call_count == 4
    assert res["status"] in ("failed", "running")


def test_issue2_sync_engine_all_orchestrates_both_adzuna_and_datagov():
    mock_orch = MagicMock()
    mock_orch.fetch_data.return_value = ExternalDataResponse(
        source="data_gov_in",
        workload=WORKLOAD_GOVERNMENT_SCHEMES,
        status="NOT_CONFIGURED",
        provenance="NOT_CONFIGURED",
        records=[],
        records_count=0,
    )
    engine = SyncEngine(source_orchestrator=mock_orch)
    res = engine.run_sync("all")
    assert mock_orch.fetch_data.call_count == 5


def test_issue2_datagov_success_persists_validated_live_records():
    mock_orch = MagicMock()

    def side_effect(**kwargs):
        wl = kwargs.get("workload")
        if wl == WORKLOAD_GOVERNMENT_SCHEMES:
            return ExternalDataResponse(
                source="data_gov_in",
                workload=wl,
                status="SUCCESS",
                provenance=SOURCE_TYPE_LIVE_API,
                records=[{
                    "id": "dg-sch-1",
                    "title": "National Scheme Live",
                    "source": "OGD_DATAGOV_IN",
                    "source_type": SOURCE_TYPE_LIVE_API,
                    "is_demo": False,
                }],
                records_count=1,
            )
        return ExternalDataResponse(
            source="data_gov_in",
            workload=wl,
            status="SUCCESS",
            provenance=SOURCE_TYPE_LIVE_API,
            records=[{
                "id": "dg-opp-1",
                "title": "NAPS Apprenticeship Live",
                "company": "Gov Agency",
                "district": "Pune",
                "vacancies_count": 5,
                "source": "OGD_DATAGOV_IN",
                "source_type": SOURCE_TYPE_LIVE_API,
                "is_demo": False,
            }],
            records_count=1,
        )

    mock_orch.fetch_data.side_effect = side_effect
    engine = SyncEngine(source_orchestrator=mock_orch)
    with patch.object(engine, "_upsert_schemes", return_value=(1, 0)) as mock_upsert_s:
        with patch.object(engine, "_upsert_jobs", return_value=(1, 0)) as mock_upsert_j:
            res = engine.run_sync("data.gov.in")
            assert mock_upsert_s.called
            assert mock_upsert_j.called


def test_issue3_real_mode_sync_fails_closed_when_supabase_unavailable():
    engine = SyncEngine()
    with patch("app.ingestion.sync_engine.is_explicit_demo_mode", return_value=False):
        with patch("app.ingestion.sync_engine.is_supabase_connected", return_value=False):
            with patch("app.config.settings.use_demo_data", True):
                with pytest.raises(SupabaseConnectionError):
                    engine._upsert_schemes([{"id": "s-1", "title": "Real Scheme"}])
                with pytest.raises(SupabaseConnectionError):
                    engine._upsert_jobs([{"id": "j-1", "title": "Real Job"}])
                with pytest.raises(SupabaseConnectionError):
                    engine._upsert_job_skills([{"id": "j-1", "skill_ids": ["sk-1"]}])


def test_issue3_explicit_demo_mode_writes_locally_and_never_calls_supabase():
    engine = SyncEngine()
    with patch("app.ingestion.sync_engine.is_explicit_demo_mode", return_value=True):
        with patch("app.repositories.supabase_repository.upsert_schemes") as mock_supa_s:
            with patch("app.repositories.supabase_repository.upsert_jobs") as mock_supa_j:
                with patch("app.repositories.supabase_repository.batch_create_job_skills") as mock_supa_js:
                    engine._upsert_schemes([{"id": "demo-s-1", "title": "Demo Scheme"}])
                    engine._upsert_jobs([{"id": "demo-j-1", "title": "Demo Job"}])
                    engine._upsert_job_skills([{"id": "demo-j-1", "skill_ids": ["sk-demo-1"]}])
                    mock_supa_s.assert_not_called()
                    mock_supa_j.assert_not_called()
                    mock_supa_js.assert_not_called()


def test_issue4_sync_engine_shares_singleton_orchestrator():
    engine = SyncEngine()
    assert engine.source_orchestrator is default_source_orchestrator


def test_issue4_custom_orchestrator_injection_preserved():
    custom_orch = SourceOrchestrator()
    engine = SyncEngine(source_orchestrator=custom_orch)
    assert engine.source_orchestrator is custom_orch
    assert engine.source_orchestrator is not default_source_orchestrator


def test_issue5_skill_matching_exact_and_substring_rejection():
    student_skills = [
        {"skill_name": "Java", "proficiency": "expert"},
        {"skill_name": "SQL", "proficiency": "intermediate"},
    ]
    required = ["JavaScript", "SQL"]
    matched, missing, pct = _match_skills(student_skills, required)
    assert "JavaScript" in missing
    assert "JavaScript" not in matched
    assert "SQL" in matched


def test_issue5_skill_matching_reverse_substring_rejection():
    student_skills = [
        {"skill_name": "JavaScript", "proficiency": "expert"},
    ]
    required = ["Java"]
    matched, missing, pct = _match_skills(student_skills, required)
    assert "Java" in missing
    assert "Java" not in matched


def test_issue5_skill_matching_whitespace_normalization():
    student_skills = [
        {"skill_name": "  Machine   Learning  ", "proficiency": "advanced"},
    ]
    required = ["Machine Learning"]
    matched, missing, pct = _match_skills(student_skills, required)
    assert "Machine Learning" in matched
    assert "Machine Learning" not in missing


def test_issue5_skill_matching_duplicate_uses_highest_proficiency():
    student_skills_order1 = [
        {"skill_name": "Python", "proficiency": "beginner"},
        {"skill_name": "Python", "proficiency": "expert"},
    ]
    student_skills_order2 = [
        {"skill_name": "Python", "proficiency": "expert"},
        {"skill_name": "Python", "proficiency": "beginner"},
    ]
    required = ["Python"]
    m1, _, pct1 = _match_skills(student_skills_order1, required)
    m2, _, pct2 = _match_skills(student_skills_order2, required)
    assert pct1 == 100
    assert pct2 == 100


def test_issue5_authoritative_aliases():
    student_skills = [
        {"skill_name": "Tableau", "proficiency": "intermediate"},
    ]
    required = ["Tableau / Power BI"]
    matched, missing, pct = _match_skills(student_skills, required)
    assert "Tableau / Power BI" in matched


def test_issue6_adaptive_roadmap_real_mode_never_calls_get_demo():
    with patch("app.repositories.supabase_repository.list_skills", return_value=[]):
        with patch("app.db.get_demo") as mock_get_demo:
            by_id, by_name = _load_skills_map(is_demo=False)
            assert by_id == {}
            assert by_name == {}
            mock_get_demo.assert_not_called()


def test_issue6_adaptive_roadmap_real_mode_fails_closed_on_missing_skills():
    mock_profile = {
        "user_id": "usr-real-no-skills",
        "target_role": "AI Engineer",
        "is_demo": False,
    }
    with patch("app.repositories.supabase_repository.get_student_profile", return_value=mock_profile):
        with patch("app.repositories.supabase_repository.get_student_assessment_by_user", return_value=None):
            with patch("app.repositories.supabase_repository.get_student_assessment", return_value=None):
                with patch("app.repositories.supabase_repository.list_skills", return_value=[]):
                    with pytest.raises(RuntimeError, match="Roadmap catalog skills unavailable"):
                        compute_adaptive_roadmap("usr-real-no-skills", is_demo=False, persist=False)


def test_issue6_demo_roadmap_does_not_query_supabase_catalog_or_upsert():
    with patch("app.repositories.supabase_repository.list_skill_forecasts") as mock_forecasts:
        with patch("app.repositories.supabase_repository.list_courses") as mock_courses:
            with patch("app.repositories.supabase_repository.list_industry_signals") as mock_signals:
                with patch("app.repositories.supabase_repository.upsert_student_roadmap") as mock_upsert:
                    res = compute_adaptive_roadmap("stu-001", is_demo=True, persist=True)
                    assert res["is_demo"] is True
                    assert res["source"] == "DEMO_SYNTHETIC"
                    mock_forecasts.assert_not_called()
                    mock_courses.assert_not_called()
                    mock_signals.assert_not_called()
                    mock_upsert.assert_not_called()


def test_issue7_list_skills_paginates_beyond_page_size():
    mock_client = MagicMock()
    page1 = [{"id": f"sk-{i}", "name": f"Skill {i}", "category": "Tech"} for i in range(1000)]
    page2 = [{"id": f"sk-{i}", "name": f"Skill {i}", "category": "Tech"} for i in range(1000, 1050)]

    call_index = {"idx": 0}

    def mock_execute():
        idx = call_index["idx"]
        call_index["idx"] += 1
        if idx == 0:
            return MagicMock(data=page1)
        return MagicMock(data=page2)

    mock_client.table.return_value.select.return_value.order.return_value.range.return_value.execute = mock_execute

    with patch("app.repositories.supabase_repository.get_client", return_value=mock_client):
        all_skills = list_skills(limit=None)
        assert len(all_skills) == 1050
        assert call_index["idx"] == 2


def test_issue7_list_jobs_paginates_beyond_page_size():
    mock_client = MagicMock()
    page1 = [{"id": f"job-{i}", "title": f"Job {i}"} for i in range(1000)]
    page2 = [{"id": f"job-{i}", "title": f"Job {i}"} for i in range(1000, 1020)]

    call_index = {"idx": 0}

    def mock_execute():
        idx = call_index["idx"]
        call_index["idx"] += 1
        if idx == 0:
            return MagicMock(data=page1)
        return MagicMock(data=page2)

    mock_client.table.return_value.select.return_value.order.return_value.range.return_value.execute = mock_execute

    with patch("app.repositories.supabase_repository.get_client", return_value=mock_client):
        all_jobs = list_jobs(limit=None)
        assert len(all_jobs) == 1020
        assert call_index["idx"] == 2
