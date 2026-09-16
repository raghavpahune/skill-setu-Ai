import uuid
import pytest
from unittest.mock import patch
from starlette.testclient import TestClient

from app.main import app
from app.core.security import create_access_token
from app.repositories.supabase_repository import (
    get_skill_forecast,
    list_skill_forecasts,
    create_skill_forecast,
    update_skill_forecast_repo,
    delete_skill_forecast_repo,
    create_employer_demand,
    delete_employer_demand_repo,
    create_industry_signal,
    delete_industry_signal_repo,
    SkillForecastNotFoundError,
    SupabaseRepositoryError,
)
from app.db import init_db, init_demo_users
from app.services.forecast_engine import (
    compute_multi_horizon_forecasts,
    get_skill_forecast_trajectory,
    generate_future_skills_radar,
    persist_computed_forecasts,
)

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
    "sub": "usr-student-001",
    "email": "student@skillsetu.gov.in",
    "role": "STUDENT",
})
STUDENT_HEADERS = {"Authorization": f"Bearer {STUDENT_TOKEN}"}


def test_01_multi_horizon_projections_coverage():
    forecasts = compute_multi_horizon_forecasts(is_demo=True)
    assert len(forecasts) > 0
    for fc in forecasts:
        assert "skill_id" in fc
        assert "skill_name" in fc
        assert "current_demand_score" in fc
        assert "projected_6m" in fc
        assert "projected_12m" in fc
        assert "projected_24m" in fc
        assert "trend" in fc
        assert "confidence_score" in fc
        assert "horizon_breakdown" in fc
        assert "6_months" in fc["horizon_breakdown"]
        assert "12_months" in fc["horizon_breakdown"]
        assert "24_months" in fc["horizon_breakdown"]
        assert fc["projected_6m"] >= 5.0
        assert fc["projected_12m"] >= 5.0
        assert fc["projected_24m"] >= 5.0
        assert fc["confidence_score"] >= 65
        assert fc["confidence_score"] <= 98


def test_02_deterministic_calculation_stability():
    run_1 = compute_multi_horizon_forecasts(is_demo=True)
    run_2 = compute_multi_horizon_forecasts(is_demo=True)
    assert len(run_1) == len(run_2)
    for f1, f2 in zip(run_1, run_2):
        assert f1["skill_id"] == f2["skill_id"]
        assert f1["projected_6m"] == f2["projected_6m"]
        assert f1["projected_12m"] == f2["projected_12m"]
        assert f1["projected_24m"] == f2["projected_24m"]
        assert f1["trend"] == f2["trend"]
        assert f1["confidence_score"] == f2["confidence_score"]


def test_03_validated_employer_demand_influence():
    base_fc = get_skill_forecast_trajectory("sk-040", is_demo=False)
    assert base_fc is not None
    base_proj_24m = base_fc["projected_24m"]
    assert base_proj_24m < 100.0

    dem_id = f"dem-prod-{uuid.uuid4().hex[:8]}"
    create_employer_demand({
        "id": dem_id,
        "organization_id": "org-prod-001",
        "company_name": "Prod Tech Corp",
        "job_role": "Prompt Engineer",
        "required_skills": ["Prompt Engineering"],
        "hiring_demand": "CRITICAL",
        "status": "VALIDATED",
        "validation_status": "VALIDATED",
        "source": "EMPLOYER_SUBMITTED",
        "is_demo": False,
        "is_active": True,
    })
    try:
        boosted_fc = get_skill_forecast_trajectory("sk-040", is_demo=False)
        assert boosted_fc is not None
        assert boosted_fc["projected_24m"] > base_proj_24m
    finally:
        delete_employer_demand_repo(dem_id)


def test_04_pending_employer_demand_isolation():
    base_fc = get_skill_forecast_trajectory("sk-001", is_demo=False)
    base_proj_24m = base_fc["projected_24m"] if base_fc else 50.0

    dem_id = f"dem-pend-{uuid.uuid4().hex[:8]}"
    create_employer_demand({
        "id": dem_id,
        "organization_id": "org-prod-002",
        "company_name": "Pending Corp",
        "job_role": "Python Developer",
        "required_skills": ["sk-001"],
        "hiring_demand": "CRITICAL",
        "status": "PENDING",
        "validation_status": "PENDING",
        "source": "EMPLOYER_SUBMITTED",
        "is_demo": False,
        "is_active": True,
    })
    try:
        after_fc = get_skill_forecast_trajectory("sk-001", is_demo=False)
        assert after_fc is not None
        assert after_fc["projected_24m"] == base_proj_24m
    finally:
        delete_employer_demand_repo(dem_id)


def test_05_demo_synthetic_signal_isolation():
    base_fc = get_skill_forecast_trajectory("sk-001", is_demo=False)
    base_proj_24m = base_fc["projected_24m"] if base_fc else 50.0

    sig_id = f"sig-demo-iso-{uuid.uuid4().hex[:8]}"
    create_industry_signal({
        "id": sig_id,
        "title": "Synthetic AI Revolution",
        "skills": ["Python"],
        "impact_level": "CRITICAL",
        "validation_status": "APPROVED",
        "is_active": True,
        "is_demo": True,
        "source": "DEMO_SYNTHETIC",
        "source_label": "DEMO_SYNTHETIC",
        "data_provenance": "DEMO_SYNTHETIC",
    })
    try:
        after_fc = get_skill_forecast_trajectory("sk-001", is_demo=False)
        assert after_fc is not None
        assert after_fc["projected_24m"] == base_proj_24m
    finally:
        delete_industry_signal_repo(sig_id)


def test_06_pending_industry_signal_isolation():
    base_fc = get_skill_forecast_trajectory("sk-001", is_demo=False)
    base_proj_24m = base_fc["projected_24m"] if base_fc else 50.0

    sig_id = f"sig-pend-iso-{uuid.uuid4().hex[:8]}"
    create_industry_signal({
        "id": sig_id,
        "title": "Pending Python Surge",
        "skills": ["Python"],
        "impact_level": "CRITICAL",
        "validation_status": "PENDING",
        "is_active": True,
        "is_demo": False,
        "source": "EXTERNAL_REPORT",
    })
    try:
        after_fc = get_skill_forecast_trajectory("sk-001", is_demo=False)
        assert after_fc is not None
        assert after_fc["projected_24m"] == base_proj_24m
    finally:
        delete_industry_signal_repo(sig_id)


def test_07_approved_industry_signal_influence():
    base_fc = get_skill_forecast_trajectory("sk-040", is_demo=False)
    assert base_fc is not None
    base_proj_24m = base_fc["projected_24m"]
    assert base_proj_24m < 100.0

    sig_id = f"sig-appr-{uuid.uuid4().hex[:8]}"
    create_industry_signal({
        "id": sig_id,
        "title": "Approved Prompt Engineering Expansion",
        "skills": ["Prompt Engineering"],
        "impact_level": "CRITICAL",
        "validation_status": "APPROVED",
        "is_active": True,
        "is_demo": False,
        "source": "INDUSTRY_FEED",
        "data_provenance": "VERIFIED_EXTERNAL_FEED",
    })
    try:
        after_fc = get_skill_forecast_trajectory("sk-040", is_demo=False)
        assert after_fc is not None
        assert after_fc["projected_24m"] > base_proj_24m
    finally:
        delete_industry_signal_repo(sig_id)


def test_08_forecast_provenance_metadata():
    demo_fc = compute_multi_horizon_forecasts(is_demo=True)
    assert len(demo_fc) > 0
    assert demo_fc[0]["is_demo"] is True
    assert demo_fc[0]["data_provenance"] == "DEMO_SYNTHETIC"

    real_fc = compute_multi_horizon_forecasts(is_demo=False)
    assert len(real_fc) > 0
    assert real_fc[0]["is_demo"] is False
    assert real_fc[0]["data_provenance"] == "AUTHORITATIVE_PROJECTION"


def test_09_empty_skills_returns_empty_list():
    with patch("app.repositories.supabase_repository.list_skills", return_value=[]):
        forecasts = compute_multi_horizon_forecasts(is_demo=False)
        assert forecasts == []


def test_10_missing_trajectory_returns_none():
    result = get_skill_forecast_trajectory("sk-non-existent-skill-99999", is_demo=True)
    assert result is None


def test_11_future_skills_radar_clusters():
    radar = generate_future_skills_radar(is_demo=True)
    assert radar["status"] == "success"
    assert "rising_skills" in radar
    assert "emerging_skills" in radar
    assert "stable_skills" in radar
    assert "declining_skills" in radar
    assert "domain_growth_matrix" in radar
    assert radar["total_skills_forecasted"] > 0


def test_12_public_forecast_endpoints():
    resp = client.get("/api/forecast")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

    resp_horizon = client.get("/api/forecast?horizon=12m")
    assert resp_horizon.status_code == 200

    resp_trend = client.get("/api/forecast?trend=RISING")
    assert resp_trend.status_code == 200

    resp_radar = client.get("/api/forecast/radar")
    assert resp_radar.status_code == 200
    assert "rising_skills" in resp_radar.json()

    resp_skill = client.get("/api/forecast/skill/sk-001")
    assert resp_skill.status_code == 200
    assert len(resp_skill.json()) == 1


def test_13_supabase_failure_returns_http_500():
    with patch(
        "app.repositories.supabase_repository.list_skills",
        side_effect=SupabaseRepositoryError("DB read failure"),
    ):
        resp = client.get("/api/forecast")
        assert resp.status_code == 500
        assert "Database query failed" in resp.json()["detail"]


def test_14_admin_forecast_crud_and_rbac():
    assert client.get("/api/admin/forecasts").status_code in (401, 403)
    assert client.post("/api/admin/forecasts", json={"skill_id": "sk-001", "period": "6m"}).status_code in (401, 403)
    assert client.patch("/api/admin/forecasts/sf-1", json={"confidence": 80}).status_code in (401, 403)
    assert client.delete("/api/admin/forecasts/sf-1").status_code in (401, 403)

    assert client.get("/api/admin/forecasts", headers=STUDENT_HEADERS).status_code in (401, 403)

    resp_list = client.get("/api/admin/forecasts?limit=5", headers=ADMIN_HEADERS)
    assert resp_list.status_code == 200
    assert resp_list.json()["status"] == "success"

    create_resp = client.post(
        "/api/admin/forecasts",
        json={"skill_id": "sk-019", "period": "6m", "current_demand": "high", "future_demand": "very_high", "trend": "rising", "confidence": 85},
        headers=ADMIN_HEADERS,
    )
    assert create_resp.status_code == 200
    sf_id = create_resp.json()["forecast"]["id"]

    patch_resp = client.patch(
        f"/api/admin/forecasts/{sf_id}",
        json={"confidence": 95},
        headers=ADMIN_HEADERS,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["forecast"]["confidence"] == 95

    del_resp = client.delete(f"/api/admin/forecasts/{sf_id}", headers=ADMIN_HEADERS)
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "success"


def test_15_repository_guards_and_edge_cases():
    assert get_skill_forecast("") is None
    assert get_skill_forecast("   ") is None
    assert delete_skill_forecast_repo("") is False
    assert delete_skill_forecast_repo("   ") is False
    with pytest.raises(SkillForecastNotFoundError):
        update_skill_forecast_repo("sf-not-exist-000", {"confidence": 90})


def test_16_downstream_consumers_read_authoritative_forecasts():
    from app.services.curriculum_engine import audit_all_courses
    audit = audit_all_courses(is_demo=False)
    assert isinstance(audit, list)
    assert len(audit) > 0

    from app.services.recommendation_service import get_curriculum_recommendations
    recs = get_curriculum_recommendations(is_demo=False)
    assert isinstance(recs, list)

    from app.services.student_service import get_personalized_industry_alerts
    alerts = get_personalized_industry_alerts(is_demo=False)
    assert isinstance(alerts, dict)
    assert "alerts" in alerts


