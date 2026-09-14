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


def test_ai_router_timeout_handling():
    from ai.router import ai_router
    import asyncio
    mock_prov = MagicMock()

    async def slow_generate(p, c):
        await asyncio.sleep(0.5)
        return "slow"

    mock_prov.generate.side_effect = slow_generate
    with patch.object(ai_router, "_resolve_gemini_for_task", return_value=mock_prov):
        with patch("app.core.providers_config.get_workload_provider", return_value="gemini"):
            res = asyncio.run(
                ai_router.route_task(
                    task_category="career_copilot",
                    prompt="test prompt",
                    timeout_seconds=0.01,
                )
            )
            assert res["status"] == "success"
            assert res["fallback_used"] is True
            assert res["error"] == "Failover triggered: TIMEOUT"
            assert ai_router.get_last_error_category() == "TIMEOUT"


def test_get_workload_provider_rejects_unsupported():
    from app.core.providers_config import get_workload_provider
    with patch.dict("os.environ", {"AI_PROVIDER_CAREER_COPILOT": "gemni_typo"}):
        assert get_workload_provider("career_copilot") == "unsupported"
    with patch.dict("os.environ", {"AI_PROVIDER_CAREER_COPILOT": "GEMINI"}):
        assert get_workload_provider("career_copilot") == "gemini"
    with patch.dict("os.environ", {"AI_PROVIDER_CAREER_COPILOT": "deterministic_fallback"}):
        assert get_workload_provider("career_copilot") == "deterministic_fallback"


def test_get_safe_integration_diagnostics_effective_ai_configured():
    from app.core.providers_config import get_safe_integration_diagnostics
    with patch("app.core.providers_config.is_gemini_configured", return_value=False):
        with patch("app.core.providers_config.is_workload_ai_configured", return_value=True):
            diag = get_safe_integration_diagnostics()
            assert diag["ai"]["configured"] is True
            assert diag["ai"]["available"] is True


def test_cached_employee_role_restoration():
    from app.db import _cache, get_user_by_email, get_user_by_id
    _cache["users"] = [{
        "id": "usr-employee-test-99",
        "email": "employee99@skillsetu.gov.in",
        "role": "STUDENT",
        "full_name": "Test Employee",
    }]
    u_by_email = get_user_by_email("employee99@skillsetu.gov.in")
    assert u_by_email is not None
    assert u_by_email["role"] == "EMPLOYEE"

    u_by_id = get_user_by_id("usr-employee-test-99")
    assert u_by_id is not None
    assert u_by_id["role"] == "EMPLOYEE"


def test_source_orchestrator_demo_datagov_exception_returns_unavailable():
    mock_connector = MagicMock()
    mock_connector.fetch_raw.side_effect = RuntimeError("Simulated connector boom")
    orch = SourceOrchestrator(datagov_connector=mock_connector)
    resp = orch.fetch_data(
        workload=WORKLOAD_GOVERNMENT_SCHEMES,
        is_demo=True,
        resource_id="any-resource",
    )
    assert resp.status == "UNAVAILABLE"
    assert resp.records == []
    assert resp.is_demo is True
    assert "Simulated connector boom" in resp.error


def test_job_skills_and_course_skills_total_ordering():
    mock_client = MagicMock()
    mock_exec = MagicMock()
    mock_exec.execute.return_value = MagicMock(data=[])
    mock_client.table.return_value.select.return_value.order.return_value.order.return_value.range.return_value = mock_exec

    with patch("app.repositories.supabase_repository.get_client", return_value=mock_client):
        list_job_skills()
        assert mock_client.table.call_args[0][0] == "job_skills"

        list_course_skills()
        assert mock_client.table.call_args[0][0] == "course_skills"


def test_adaptive_roadmap_real_mode_forecast_failure_fails_closed():
    mock_profile = {
        "user_id": "usr-real-fail-forecast",
        "target_role": "AI Engineer",
        "is_demo": False,
    }
    with patch("app.repositories.supabase_repository.get_student_profile", return_value=mock_profile):
        with patch("app.repositories.supabase_repository.get_student_assessment_by_user", return_value=None):
            with patch("app.repositories.supabase_repository.get_student_assessment", return_value=None):
                with patch("app.repositories.supabase_repository.list_skills", return_value=[{"id": "sk-1", "name": "Python"}]):
                    with patch("app.repositories.supabase_repository.list_skill_forecasts", side_effect=RuntimeError("DB outage")):
                        with pytest.raises(RuntimeError, match="Roadmap skill forecasts unavailable"):
                            compute_adaptive_roadmap("usr-real-fail-forecast", is_demo=False, persist=False)


def test_ai_router_diagnostics_requires_gemini_provider_selected():
    from ai.router import ai_router
    with patch("app.core.providers_config.is_gemini_configured", return_value=False):
        with patch("app.core.providers_config.get_workload_provider", return_value="deterministic_fallback"):
            with patch("app.core.providers_config.is_workload_ai_configured", return_value=True):
                diag = ai_router.get_diagnostics()
                assert diag["real_provider_configured"] is False

    with patch("app.core.providers_config.is_gemini_configured", return_value=False):
        with patch("app.core.providers_config.get_workload_provider", side_effect=lambda t: "gemini" if t == "career_copilot" else "deterministic_fallback"):
            with patch("app.core.providers_config.is_workload_ai_configured", side_effect=lambda t: t == "career_copilot"):
                diag = ai_router.get_diagnostics()
                assert diag["real_provider_configured"] is True


def test_student_with_employee_prefixed_email_retains_student_role():
    from app.db import get_user_by_email, get_user_by_id, _cache
    _cache["users"] = [{
        "id": "usr-std-employee-prefix-1",
        "email": "employee.jane@domain.com",
        "role": "STUDENT",
        "name": "Jane Doe",
    }]
    mock_client = MagicMock()
    mock_res = MagicMock()
    mock_res.data = [{
        "id": "usr-std-employee-prefix-1",
        "email": "employee.jane@domain.com",
        "role": "STUDENT",
        "name": "Jane Doe",
    }]
    mock_client.table.return_value.select.return_value.ilike.return_value.execute.return_value = mock_res
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_res

    with patch("app.db.get_supabase_client", return_value=mock_client):
        u_cache = get_user_by_email("employee.jane@domain.com")
        assert u_cache is not None
        assert u_cache["role"] == "STUDENT"

        _cache["users"] = []
        u_supa = get_user_by_email("employee.jane@domain.com")
        assert u_supa is not None
        assert u_supa["role"] == "STUDENT"

        _cache["users"] = [{
            "id": "usr-std-employee-prefix-1",
            "email": "employee.jane@domain.com",
            "role": "STUDENT",
            "name": "Jane Doe",
        }]
        u_id = get_user_by_id("usr-std-employee-prefix-1")
        assert u_id is not None
        assert u_id["role"] == "STUDENT"


def test_save_user_reraises_on_arbitrary_upsert_failure():
    from app.db import save_user
    from app.repositories.supabase_repository import SupabaseRepositoryError
    mock_client = MagicMock()
    mock_client.table.return_value.upsert.return_value.execute.side_effect = ConnectionError("Supabase connection timeout")

    with patch("app.db.get_supabase_client", return_value=mock_client):
        user_data = {
            "id": "usr-employee-fail-network",
            "email": "employee_fail@domain.com",
            "role": "EMPLOYEE",
            "name": "Fail Test",
        }
        with pytest.raises(SupabaseRepositoryError, match="Supabase connection timeout"):
            save_user(user_data)
        assert mock_client.table.return_value.upsert.call_count == 1


def test_list_schemes_chunked_pagination_and_none_limit():
    from app.repositories.supabase_repository import list_schemes
    mock_client = MagicMock()
    mock_query = MagicMock()
    mock_client.table.return_value = mock_query
    mock_query.select.return_value = mock_query
    mock_query.order.return_value = mock_query
    mock_query.range.return_value = mock_query

    with patch("app.repositories.supabase_repository.get_client", return_value=mock_client):
        mock_query.execute.side_effect = [
            MagicMock(data=[{"id": f"sch-{i}"} for i in range(1000)]),
            MagicMock(data=[{"id": f"sch-{i}"} for i in range(1000, 1350)]),
        ]
        res_none = list_schemes(limit=None)
        assert len(res_none) == 1350
        assert mock_query.range.call_args_list[0][0] == (0, 999)
        assert mock_query.range.call_args_list[1][0] == (1000, 1999)

        mock_query.range.reset_mock()
        mock_query.execute.side_effect = [
            MagicMock(data=[{"id": f"sch-{i}"} for i in range(1000)]),
            MagicMock(data=[{"id": f"sch-{i}"} for i in range(1000, 2000)]),
            MagicMock(data=[{"id": f"sch-{i}"} for i in range(2000, 2500)]),
        ]
        res_large = list_schemes(limit=2500, offset=100)
        assert len(res_large) == 2500
        assert mock_query.range.call_args_list[0][0] == (100, 1099)
        assert mock_query.range.call_args_list[1][0] == (1100, 2099)
        assert mock_query.range.call_args_list[2][0] == (2100, 2599)
