import pytest
from starlette.testclient import TestClient
from app.main import app
from app.core.security import create_access_token
from app.core.providers_config import (
    get_safe_integration_diagnostics,
    is_gemini_configured,
    is_adzuna_configured,
    is_datagov_configured,
)
from ai.router import (
    ai_router,
    SUPPORTED_AI_TASKS,
    TASK_CAREER_COPILOT,
    TASK_SKILL_GAP_ANALYSIS,
    TASK_LEARNING_ROADMAP,
    TASK_EMPLOYEE_TRANSITION,
    TASK_EMPLOYER_CANDIDATE_ANALYSIS,
    TASK_INSTITUTE_CURRICULUM_ANALYSIS,
    TASK_GOVERNMENT_POLICY_ANALYSIS,
    TASK_DATA_INSIGHT_GENERATION,
)
from app.ingestion.connector_router import connector_registry


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_providers_config_diagnostics_structure():
    diag = get_safe_integration_diagnostics()
    assert diag["status"] == "success"
    assert "ai" in diag
    assert "external_data" in diag
    ai = diag["ai"]
    assert ai["provider"] == "gemini"
    assert ai["fallback_available"] is True
    assert len(ai["supported_tasks"]) == 8


def test_no_secrets_in_diagnostics():
    diag = get_safe_integration_diagnostics()
    serialized = str(diag).lower()
    assert "api_key" not in diag["ai"]
    assert "secret" not in serialized
    assert "password" not in serialized
    assert "bearer" not in serialized


def test_supported_tasks_count():
    assert len(SUPPORTED_AI_TASKS) == 8
    assert TASK_CAREER_COPILOT in SUPPORTED_AI_TASKS
    assert TASK_SKILL_GAP_ANALYSIS in SUPPORTED_AI_TASKS
    assert TASK_LEARNING_ROADMAP in SUPPORTED_AI_TASKS
    assert TASK_EMPLOYEE_TRANSITION in SUPPORTED_AI_TASKS
    assert TASK_EMPLOYER_CANDIDATE_ANALYSIS in SUPPORTED_AI_TASKS
    assert TASK_INSTITUTE_CURRICULUM_ANALYSIS in SUPPORTED_AI_TASKS
    assert TASK_GOVERNMENT_POLICY_ANALYSIS in SUPPORTED_AI_TASKS
    assert TASK_DATA_INSIGHT_GENERATION in SUPPORTED_AI_TASKS


@pytest.mark.anyio
async def test_ai_router_deterministic_fallback():
    res = await ai_router.route_task(
        task_category=TASK_CAREER_COPILOT,
        prompt="Tell me about AI careers in Pune",
        context={"district": "Pune"},
        is_demo=True,
    )
    assert res["status"] == "success"
    assert len(res["answer"]) > 20
    assert res["fallback_used"] is True
    assert res["task_category"] == TASK_CAREER_COPILOT


@pytest.mark.anyio
async def test_ai_router_all_eight_categories():
    for task in SUPPORTED_AI_TASKS:
        res = await ai_router.route_task(
            task_category=task,
            prompt=f"Execute {task} query",
            context={"test_task": task},
            is_demo=True,
        )
        assert res["status"] == "success"
        assert res["task_category"] == task
        assert bool(res["answer"])


@pytest.mark.anyio
async def test_ai_router_simulated_gemini_failure(monkeypatch):
    class FailingGemini:
        api_key = "test-mock-key"
        model = "gemini-3.6-flash"

        async def generate(self, prompt, context=None):
            raise RuntimeError("429 ResourceExhausted: Quota exceeded for model")

    monkeypatch.setattr(ai_router, "_resolve_gemini", lambda: FailingGemini())
    res = await ai_router.route_task(
        task_category=TASK_CAREER_COPILOT,
        prompt="Explain cloud careers",
        context={},
        is_demo=False,
    )
    assert res["status"] == "success"
    assert res["fallback_used"] is True
    assert ai_router.get_last_error_category() == "QUOTA_EXCEEDED"
    assert "Failover triggered" in str(res["error"])


def test_connector_router_jobs_fallback():
    jobs = connector_registry.fetch_jobs_with_fallback(limit=5, is_demo=True)
    assert isinstance(jobs, list)
    assert len(jobs) > 0


def test_connector_router_schemes_fallback():
    schemes = connector_registry.fetch_schemes_with_fallback(limit=5, is_demo=True)
    assert isinstance(schemes, list)
    assert len(schemes) > 0


def test_connector_registry_diagnostics():
    diag = connector_registry.get_diagnostics()
    assert "connectors" in diag
    assert diag["total_connectors"] == 2
    for c in diag["connectors"]:
        assert "provider_name" in c
        assert "source_name" in c
        assert "configured" in c
        assert "fallback_available" in c
        assert c["fallback_available"] is True


def test_admin_integrations_health_unauthorized(client):
    res = client.get("/api/admin/integrations/health")
    assert res.status_code in (401, 403)


def test_admin_integrations_health_authorized(client):
    token = create_access_token({"sub": "usr-admin-001", "role": "ADMIN", "email": "admin@skillsetu.gov.in"})
    res = client.get("/api/admin/integrations/health", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "ai" in data
    assert "external_data" in data
    assert "router_metrics" in data["ai"]
    assert "connector_details" in data["external_data"]


def test_copilot_route_task_endpoint(client):
    payload = {
        "task_category": "career_copilot",
        "prompt": "What are the job prospects in Maharashtra?",
        "context": {"district": "Pune"},
        "is_demo": True,
    }
    res = client.post("/api/copilot/route-task", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["task_category"] == "career_copilot"
    assert len(data["answer"]) > 10
