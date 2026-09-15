import os
import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.db import _cache, init_db
from app.core.providers_config import (
    SUPPORTED_WORKLOADS,
    get_workload_ai_key,
    is_workload_ai_configured,
    get_workload_provider,
    get_safe_integration_diagnostics,
)
from ai.router import ai_router, SUPPORTED_AI_TASKS
from app.ingestion.connector_router import connector_registry
from app.core.security import create_access_token


@pytest.fixture(autouse=True)
def setup_test_users():
    init_db()
    users = _cache.setdefault("users", [])
    existing_ids = {u.get("id") for u in users}
    if "test-admin-uid" not in existing_ids:
        users.append({
            "id": "test-admin-uid",
            "email": "admin_test@skillsetu.gov.in",
            "role": "ADMIN",
            "is_active": True,
        })
    if "test-student-uid" not in existing_ids:
        users.append({
            "id": "test-student-uid",
            "email": "student_test@skillsetu.gov.in",
            "role": "STUDENT",
            "is_active": True,
        })


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin_headers():
    token = create_access_token({"sub": "test-admin-uid", "email": "admin_test@skillsetu.gov.in", "role": "ADMIN"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def student_headers():
    token = create_access_token({"sub": "test-student-uid", "email": "student_test@skillsetu.gov.in", "role": "STUDENT"})
    return {"Authorization": f"Bearer {token}"}


def test_provider_config_discovery():
    assert len(SUPPORTED_WORKLOADS) == 8
    assert "career_copilot" in SUPPORTED_WORKLOADS
    assert "data_insight_generation" in SUPPORTED_WORKLOADS
    assert get_workload_provider("career_copilot") == "gemini"


def test_workload_specific_ai_key_resolution(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY_SKILL_GAP_ANALYSIS", raising=False)
    with patch.dict(os.environ, {"GEMINI_API_KEY": "shared-default-key", "GEMINI_API_KEY_CAREER_COPILOT": "dedicated-copilot-key"}, clear=False):
        assert get_workload_ai_key("career_copilot") == "dedicated-copilot-key"
        assert get_workload_ai_key("skill_gap_analysis") == "shared-default-key"
        assert is_workload_ai_configured("career_copilot") is True


def test_no_secrets_in_diagnostics():
    with patch.dict(os.environ, {"GEMINI_API_KEY": "secret-gemini-test-key", "ADZUNA_APP_KEY": "secret-adzuna-key"}, clear=False):
        diag = get_safe_integration_diagnostics()
        assert diag["status"] == "success"
        serialized = str(diag)
        assert "secret-gemini-test-key" not in serialized
        assert "secret-adzuna-key" not in serialized
        assert "STANDALONE_CACHE" not in serialized


def test_ai_router_all_task_categories():
    assert set(SUPPORTED_AI_TASKS) == set(SUPPORTED_WORKLOADS)
    for task in SUPPORTED_AI_TASKS:
        res = asyncio.run(
            ai_router.route_task(
                task_category=task,
                prompt="Analyze relevant competencies for Pune district.",
                is_demo=True,
            )
        )
        assert res["status"] == "success"
        assert res["provider"] == "deterministic_fallback"
        assert res["task_category"] == task
        assert res["fallback_used"] is True
        assert res["advisory"] is True
        assert isinstance(res["answer"], str)
        assert len(res["answer"]) > 0


def test_ai_router_invalid_task_category_rejected():
    with pytest.raises(ValueError) as exc:
        asyncio.run(
            ai_router.route_task(
                task_category="invalid_unregistered_category",
                prompt="Test prompt",
            )
        )
    assert "Unsupported AI task category" in str(exc.value)


def test_ai_router_failover_scenarios():
    with patch("ai.router.ai_router._resolve_gemini_for_task") as mock_resolve:
        mock_prov = AsyncMock()
        mock_prov.generate.side_effect = Exception("429 Resource has been exhausted (e.g. check quota).")
        mock_resolve.return_value = mock_prov

        res = asyncio.run(
            ai_router.route_task(
                task_category="career_copilot",
                prompt="What skills do I need for React Developer?",
                is_demo=False,
            )
        )
        assert res["status"] == "success"
        assert res["provider"] == "deterministic_fallback"
        assert res["fallback_used"] is True
        assert res["advisory"] is True
        assert ai_router.get_last_error_category() == "QUOTA_EXCEEDED"

    with patch("ai.router.ai_router._resolve_gemini_for_task") as mock_resolve:
        mock_prov = AsyncMock()
        mock_prov.generate.side_effect = Exception("Request timed out after 30 seconds")
        mock_resolve.return_value = mock_prov

        res = asyncio.run(
            ai_router.route_task(
                task_category="skill_gap_analysis",
                prompt="Analyze missing prerequisites",
                is_demo=False,
            )
        )
        assert res["provider"] == "deterministic_fallback"
        assert ai_router.get_last_error_category() == "TIMEOUT"


def test_connector_router_no_silent_fallback_in_prod():
    with patch("app.ingestion.connector_router.is_adzuna_configured", return_value=False):
        jobs = connector_registry.fetch_jobs_with_fallback(limit=5, is_demo=False)
        assert jobs == []

    with patch("app.ingestion.connector_router.is_datagov_configured", return_value=False):
        schemes = connector_registry.fetch_schemes_with_fallback(limit=5, is_demo=False)
        assert schemes == []


def test_connector_router_explicit_demo_mode():
    jobs = connector_registry.fetch_jobs_with_fallback(limit=3, is_demo=True)
    assert len(jobs) > 0
    for j in jobs:
        assert j["source"] == "DEMO_SYNTHETIC"
        assert j["source_type"] == "DEMO_SYNTHETIC"
        assert j["is_demo"] is True

    schemes = connector_registry.fetch_schemes_with_fallback(limit=3, is_demo=True)
    assert len(schemes) > 0
    for s in schemes:
        assert s["source"] == "DEMO_SYNTHETIC"
        assert s["source_type"] == "DEMO_SYNTHETIC"
        assert s["is_demo"] is True


def test_connector_router_diagnostics():
    diag = connector_registry.get_diagnostics()
    assert "connectors" in diag
    assert diag["total_connectors"] == 2
    for conn in diag["connectors"]:
        assert "provider_name" in conn
        assert "status" in conn
        assert "availability" in conn
        assert "provenance" in conn
        assert conn["fallback_available"] is False


def test_supabase_configuration_no_cache_fallback():
    diag = get_safe_integration_diagnostics()
    sb_diag = diag["external_data"]["supabase_database"]
    assert sb_diag["provider"] == "Supabase Managed PostgreSQL"
    assert sb_diag["authoritative"] is True
    assert sb_diag["fallback_available"] is False
    assert "STANDALONE_CACHE" not in str(sb_diag)


def test_admin_integrations_health_security(client, admin_headers, student_headers):
    unauth_res = client.get("/api/admin/integrations/health")
    assert unauth_res.status_code == 401

    forbidden_res = client.get("/api/admin/integrations/health", headers=student_headers)
    assert forbidden_res.status_code == 403

    ok_res = client.get("/api/admin/integrations/health", headers=admin_headers)
    assert ok_res.status_code == 200
    data = ok_res.json()
    assert data["status"] == "success"
    assert "ai" in data
    assert "external_data" in data
    assert data["ai"]["real_provider"] == "gemini"
    assert data["ai"]["fallback_mechanism"] == "deterministic_fallback"


def test_copilot_route_task_endpoint_authenticated(client, student_headers):
    unauth_res = client.post(
        "/api/copilot/route-task",
        json={"task_category": "career_copilot", "prompt": "How do I become a Data Scientist?", "is_demo": True},
    )
    assert unauth_res.status_code == 401

    invalid_cat_res = client.post(
        "/api/copilot/route-task",
        json={"task_category": "arbitrary_unsupported_category", "prompt": "Hello", "is_demo": True},
        headers=student_headers,
    )
    assert invalid_cat_res.status_code == 422

    valid_res = client.post(
        "/api/copilot/route-task",
        json={"task_category": "career_copilot", "prompt": "How do I become a Data Scientist?", "is_demo": True},
        headers=student_headers,
    )
    assert valid_res.status_code == 200
    data = valid_res.json()
    assert data["status"] == "success"
    assert data["task_category"] == "career_copilot"
    assert data["provider"] == "deterministic_fallback"
    assert data["fallback_used"] is True
    assert data["advisory"] is True
    assert "secret" not in str(data)


def test_ai_provider_workload_configuration_respected():
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-all", "AI_PROVIDER_CAREER_COPILOT": "gemini"}, clear=False):
        with patch("ai.router.GeminiProvider") as mock_gemini_cls:
            mock_inst = AsyncMock()
            mock_inst.api_key = "test-key-all"
            mock_inst.model = "gemini-3.6-flash"
            mock_inst.generate.return_value = "Gemini copilot answer"
            mock_gemini_cls.return_value = mock_inst

            res = asyncio.run(
                ai_router.route_task(
                    task_category="career_copilot",
                    prompt="Explain career",
                    is_demo=False,
                )
            )
            assert res["provider"] == "gemini"
            assert res["fallback_used"] is False
            assert res["error"] is None
            mock_inst.generate.assert_awaited_once()

    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-all", "AI_PROVIDER_CAREER_COPILOT": "deterministic_fallback"}, clear=False):
        with patch("ai.router.GeminiProvider") as mock_gemini_cls:
            mock_inst = AsyncMock()
            mock_gemini_cls.return_value = mock_inst

            res = asyncio.run(
                ai_router.route_task(
                    task_category="career_copilot",
                    prompt="Explain career",
                    is_demo=False,
                )
            )
            assert res["provider"] == "deterministic_fallback"
            assert res["fallback_used"] is True
            assert res["error"] is None
            mock_inst.generate.assert_not_called()


def test_ai_router_isolated_error_states_no_leakage():
    with patch("ai.router.ai_router._resolve_gemini_for_task") as mock_resolve:
        mock_prov = AsyncMock()
        mock_prov.generate.side_effect = Exception("429 ResourceExhausted: Quota exceeded")
        mock_resolve.return_value = mock_prov

        res_a = asyncio.run(
            ai_router.route_task(
                task_category="career_copilot",
                prompt="Explain careers",
                is_demo=False,
            )
        )
        assert res_a["provider"] == "deterministic_fallback"
        assert res_a["error"] == "Failover triggered: QUOTA_EXCEEDED"
        assert ai_router.get_last_error_category() == "QUOTA_EXCEEDED"

    with patch("ai.router.ai_router._resolve_gemini_for_task", return_value=None):
        res_b = asyncio.run(
            ai_router.route_task(
                task_category="skill_gap_analysis",
                prompt="Gap analysis",
                is_demo=False,
            )
        )
        assert res_b["provider"] == "deterministic_fallback"
        assert res_b["error"] == "Failover triggered: NOT_CONFIGURED"
        assert ai_router.get_last_error_category() == "NOT_CONFIGURED"

    with patch("ai.router.ai_router._resolve_gemini_for_task") as mock_resolve:
        mock_prov = AsyncMock()
        mock_prov.generate.return_value = "Successful analysis"
        mock_prov.model = "gemini-3.6-flash"
        mock_resolve.return_value = mock_prov

        res_c = asyncio.run(
            ai_router.route_task(
                task_category="career_copilot",
                prompt="Explain careers",
                is_demo=False,
            )
        )
        assert res_c["provider"] == "gemini"
        assert res_c["error"] is None
        assert ai_router.get_last_error_category() == "NONE"


def test_ai_router_respects_skillsetu_data_mode():
    with patch.dict(os.environ, {"SKILLSETU_DATA_MODE": "demo", "GEMINI_API_KEY": "test-key"}, clear=False):
        with patch("ai.router.GeminiProvider") as mock_gemini_cls:
            mock_inst = AsyncMock()
            mock_gemini_cls.return_value = mock_inst

            res = asyncio.run(
                ai_router.route_task(
                    task_category="career_copilot",
                    prompt="Explain career",
                    is_demo=None,
                )
            )
            assert res["provider"] == "deterministic_fallback"
            assert res["fallback_used"] is True
            mock_inst.generate.assert_not_called()

    with patch.dict(os.environ, {"SKILLSETU_DATA_MODE": "synthetic", "GEMINI_API_KEY": "test-key"}, clear=False):
        with patch("ai.router.GeminiProvider") as mock_gemini_cls:
            mock_inst = AsyncMock()
            mock_gemini_cls.return_value = mock_inst

            res = asyncio.run(
                ai_router.route_task(
                    task_category="career_copilot",
                    prompt="Explain career",
                    is_demo=None,
                )
            )
            assert res["provider"] == "deterministic_fallback"
            assert res["fallback_used"] is True
            mock_inst.generate.assert_not_called()

    with patch.dict(os.environ, {"SKILLSETU_DATA_MODE": "demo", "GEMINI_API_KEY": "test-key"}, clear=False):
        with patch("ai.router.GeminiProvider") as mock_gemini_cls:
            mock_inst = AsyncMock()
            mock_inst.api_key = "test-key"
            mock_inst.model = "gemini-3.6-flash"
            mock_inst.generate.return_value = "Real answer"
            mock_gemini_cls.return_value = mock_inst

            res = asyncio.run(
                ai_router.route_task(
                    task_category="career_copilot",
                    prompt="Explain career",
                    is_demo=False,
                )
            )
            assert res["provider"] == "gemini"
            assert res["fallback_used"] is False
            mock_inst.generate.assert_awaited_once()


def test_copilot_workload_provider_and_key_resolution(client, student_headers):
    from ai.gemini_provider import GeminiProvider
    with patch.dict(
        os.environ,
        {
            "AI_PROVIDER_CAREER_COPILOT": "gemini",
            "GEMINI_API_KEY_CAREER_COPILOT": "copilot-specific-key",
            "GEMINI_API_KEY": "general-key",
        },
        clear=False,
    ):
        with patch("ai.router.GeminiProvider") as mock_gemini_cls:
            mock_inst = AsyncMock(spec=GeminiProvider)
            mock_inst.api_key = "copilot-specific-key"
            mock_inst.model = "gemini-3.6-flash"
            mock_inst.generate.return_value = "Workload specific career guidance"
            mock_gemini_cls.return_value = mock_inst

            sample_skills = [{"id": "sk-py", "name": "Python", "category": "IT", "nsqf_level": 5}]
            sample_jobs = [{"id": "jb-1", "title": "Dev", "district": "Pune"}]
            sample_job_skills = [{"job_id": "jb-1", "skill_id": "sk-py"}]
            sample_course_skills = [{"course_id": "c-1", "skill_id": "sk-py"}]

            with patch("app.repositories.supabase_repository.list_skills", return_value=sample_skills), \
                 patch("app.repositories.supabase_repository.list_jobs", return_value=sample_jobs), \
                 patch("app.repositories.supabase_repository.list_job_skills", return_value=sample_job_skills), \
                 patch("app.repositories.supabase_repository.list_course_skills", return_value=sample_course_skills), \
                 patch("app.services.district_service.compute_gaps", return_value=[]):

                res_ask = client.post(
                    "/api/copilot/ask",
                    json={"question": "What skills do I need for Python?", "role": "student"},
                    headers=student_headers,
                )
                assert res_ask.status_code == 200
                data_ask = res_ask.json()
                assert data_ask["answer"] == "Workload specific career guidance"
                assert data_ask["demo_mode"] is False
                assert "Gemini AI" in data_ask["provenance_label"]
                assert mock_gemini_cls.call_args[1]["api_key"] == "copilot-specific-key"

                res_exp = client.post(
                    "/api/copilot/explain-career",
                    json={"student_id": "test-student-uid", "question": "Explain my roadmap"},
                    headers=student_headers,
                )
                assert res_exp.status_code == 200
                data_exp = res_exp.json()
                assert data_exp["answer"] == "Workload specific career guidance"
                assert data_exp["demo_mode"] is False


def test_copilot_endpoints_fail_closed_in_real_mode_when_provider_unavailable_or_fails(client, student_headers):
    from ai.gemini_provider import GeminiProvider
    with patch.dict(
        os.environ,
        {
            "AI_PROVIDER_CAREER_COPILOT": "deterministic_fallback",
        },
        clear=False,
    ):
        res_ask = client.post(
            "/api/copilot/ask",
            json={"question": "Career path options", "role": "student"},
            headers=student_headers,
        )
        assert res_ask.status_code == 200
        data_ask = res_ask.json()
        assert data_ask["demo_mode"] is False
        assert data_ask["provenance_label"] == "⚠️ Service Offline"
        assert "temporarily unavailable" in data_ask["answer"]

        res_exp = client.post(
            "/api/copilot/explain-career",
            json={"student_id": "test-student-uid"},
            headers=student_headers,
        )
        assert res_exp.status_code == 200
        data_exp = res_exp.json()
        assert data_exp["demo_mode"] is False
        assert data_exp["provenance_label"] == "⚠️ Service Offline"

    with patch.dict(
        os.environ,
        {
            "AI_PROVIDER_CAREER_COPILOT": "gemini",
            "GEMINI_API_KEY_CAREER_COPILOT": "error-test-key",
        },
        clear=False,
    ):
        with patch("ai.router.GeminiProvider") as mock_gemini_cls:
            mock_inst = AsyncMock(spec=GeminiProvider)
            mock_inst.api_key = "error-test-key"
            mock_inst.model = "gemini-3.6-flash"
            mock_inst.generate.side_effect = RuntimeError("Upstream API quota exceeded")
            mock_gemini_cls.return_value = mock_inst

            sample_skills = [{"id": "sk-py", "name": "Python", "category": "IT", "nsqf_level": 5}]
            sample_jobs = [{"id": "jb-1", "title": "Dev", "district": "Pune"}]
            sample_job_skills = [{"job_id": "jb-1", "skill_id": "sk-py"}]
            sample_course_skills = [{"course_id": "c-1", "skill_id": "sk-py"}]

            with patch("app.repositories.supabase_repository.list_skills", return_value=sample_skills), \
                 patch("app.repositories.supabase_repository.list_jobs", return_value=sample_jobs), \
                 patch("app.repositories.supabase_repository.list_job_skills", return_value=sample_job_skills), \
                 patch("app.repositories.supabase_repository.list_course_skills", return_value=sample_course_skills), \
                 patch("app.services.district_service.compute_gaps", return_value=[]):

                res_err = client.post(
                    "/api/copilot/ask",
                    json={"question": "Career guidance for Python", "role": "student"},
                    headers=student_headers,
                )
                assert res_err.status_code == 200
                data_err = res_err.json()
                assert data_err["demo_mode"] is False
                assert data_err["provenance_label"] == "⚠️ Service Error"


def test_copilot_endpoints_explicit_demo_mode(client, student_headers):
    res_ask = client.post(
        "/api/copilot/ask",
        json={"question": "Tell me about data science", "role": "student", "is_demo": True},
        headers=student_headers,
    )
    assert res_ask.status_code == 200
    data_ask = res_ask.json()
    assert data_ask["demo_mode"] is True
    assert data_ask["model"] == "Rule-Based Offline Intelligence"
    assert "Offline Demo Mode" in data_ask["provenance_label"]

    res_exp = client.post(
        "/api/copilot/explain-career",
        json={"student_id": "test-student-uid", "is_demo": True},
        headers=student_headers,
    )
    assert res_exp.status_code == 200
    data_exp = res_exp.json()
    assert data_exp["demo_mode"] is True


def test_copilot_authorization_and_ownership_guards(client, student_headers, admin_headers):
    private_record = {
        "id": "other-student-456",
        "user_id": "other-student-456",
        "source": "USER_SUBMITTED",
        "is_demo": False,
        "career_goal": "AI Engineer",
        "skills": [{"skill_name": "Python", "proficiency": "advanced"}],
    }

    with patch("app.repositories.supabase_repository.get_student_assessment", return_value=private_record), \
         patch("app.repositories.supabase_repository.get_student_assessment_by_user", return_value=private_record):

        unauth_ask = client.post(
            "/api/copilot/ask",
            json={"question": "recommendations", "student_id": "other-student-456"},
        )
        assert unauth_ask.status_code == 401

        unauth_exp = client.post(
            "/api/copilot/explain-career",
            json={"student_id": "other-student-456"},
        )
        assert unauth_exp.status_code == 401

        forbidden_ask = client.post(
            "/api/copilot/ask",
            json={"question": "recommendations", "student_id": "other-student-456"},
            headers=student_headers,
        )
        assert forbidden_ask.status_code == 403

        forbidden_exp = client.post(
            "/api/copilot/explain-career",
            json={"student_id": "other-student-456"},
            headers=student_headers,
        )
        assert forbidden_exp.status_code == 403

    owner_record = {
        "id": "test-student-uid",
        "user_id": "test-student-uid",
        "source": "USER_SUBMITTED",
        "is_demo": False,
    }
    with patch("app.repositories.supabase_repository.get_student_assessment", return_value=owner_record), \
         patch("app.repositories.supabase_repository.get_student_assessment_by_user", return_value=owner_record):

        ok_owner_exp = client.post(
            "/api/copilot/explain-career",
            json={"student_id": "test-student-uid", "is_demo": True},
            headers=student_headers,
        )
        assert ok_owner_exp.status_code == 200

        ok_admin_exp = client.post(
            "/api/copilot/explain-career",
            json={"student_id": "test-student-uid", "is_demo": True},
            headers=admin_headers,
        )
        assert ok_admin_exp.status_code == 200
