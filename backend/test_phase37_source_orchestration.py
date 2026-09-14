import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.db import _cache, init_db
from app.core.security import create_access_token
from app.ingestion.source_orchestrator import (
    source_orchestrator,
    resolve_source_for_workload,
    validate_job_item,
    validate_scheme_item,
    create_industry_signal_contract,
    SOURCE_ADZUNA,
    SOURCE_DATAGOV,
    SOURCE_SUPABASE,
    SOURCE_LOCAL_DEMO,
    WORKLOAD_JOBS,
    WORKLOAD_LABOUR_MARKET_DEMAND,
    WORKLOAD_GOVERNMENT_SCHEMES,
    WORKLOAD_GOVERNMENT_DATASETS,
    WORKLOAD_STUDENT_PROFILES,
    WORKLOAD_EMPLOYER_DEMANDS,
    SIGNAL_TYPE_JOB_VOLUME,
    SIGNAL_TYPE_DEMAND_TRENDS,
    SOURCE_TYPE_LIVE_API,
    SOURCE_TYPE_DEMO_SYNTHETIC,
)


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


def test_source_registry_discovery():
    sources = source_orchestrator.list_sources()
    assert len(sources) >= 4
    source_ids = {s.source_id for s in sources}
    assert SOURCE_ADZUNA in source_ids
    assert SOURCE_DATAGOV in source_ids
    assert SOURCE_SUPABASE in source_ids
    assert SOURCE_LOCAL_DEMO in source_ids

    adzuna_spec = source_orchestrator.get_source_spec(SOURCE_ADZUNA)
    assert adzuna_spec.authoritative is False
    assert adzuna_spec.expected_provenance == SOURCE_TYPE_LIVE_API
    assert "ADZUNA_APP_ID" in adzuna_spec.required_credentials

    supabase_spec = source_orchestrator.get_source_spec(SOURCE_SUPABASE)
    assert supabase_spec.authoritative is True
    assert "SUPABASE_URL" in supabase_spec.required_credentials


def test_deterministic_source_routing():
    assert resolve_source_for_workload(WORKLOAD_JOBS, requires_live=True, is_demo=False) == SOURCE_ADZUNA
    assert resolve_source_for_workload(WORKLOAD_LABOUR_MARKET_DEMAND, requires_live=True, is_demo=False) == SOURCE_ADZUNA
    assert resolve_source_for_workload(SIGNAL_TYPE_JOB_VOLUME, requires_live=True, is_demo=False) == SOURCE_ADZUNA

    assert resolve_source_for_workload(WORKLOAD_GOVERNMENT_SCHEMES, requires_live=True, is_demo=False) == SOURCE_DATAGOV
    assert resolve_source_for_workload(WORKLOAD_GOVERNMENT_DATASETS, requires_live=True, is_demo=False) == SOURCE_DATAGOV

    assert resolve_source_for_workload(WORKLOAD_STUDENT_PROFILES, requires_live=False, is_demo=False) == SOURCE_SUPABASE
    assert resolve_source_for_workload(WORKLOAD_EMPLOYER_DEMANDS, requires_live=False, is_demo=False) == SOURCE_SUPABASE

    assert resolve_source_for_workload(WORKLOAD_JOBS, requires_live=True, is_demo=True) == SOURCE_LOCAL_DEMO
    assert resolve_source_for_workload(WORKLOAD_GOVERNMENT_SCHEMES, requires_live=True, is_demo=True) == SOURCE_LOCAL_DEMO


def test_credential_detection_and_separation():
    with patch.dict(os.environ, {"ADZUNA_APP_ID": "test_id", "ADZUNA_APP_KEY": "test_key"}, clear=False):
        assert source_orchestrator.is_source_configured(SOURCE_ADZUNA) is True

    with patch.dict(os.environ, {"ADZUNA_APP_ID": "", "ADZUNA_APP_KEY": ""}, clear=False):
        with patch("app.config.settings.adzuna_app_id", ""):
            with patch("app.config.settings.adzuna_app_key", ""):
                assert source_orchestrator.is_source_configured(SOURCE_ADZUNA) is False

    with patch.dict(os.environ, {"DATA_GOV_API_KEY": "gov_test_key"}, clear=False):
        assert source_orchestrator.is_source_configured(SOURCE_DATAGOV) is True

    with patch.dict(os.environ, {"DATA_GOV_API_KEY": ""}, clear=False):
        with patch("app.config.settings.data_gov_api_key", ""):
            assert source_orchestrator.is_source_configured(SOURCE_DATAGOV) is False


def test_production_fail_closed_missing_credentials():
    with patch.object(source_orchestrator, "is_source_configured", return_value=False):
        res = source_orchestrator.fetch_data(workload=WORKLOAD_JOBS, limit=10, is_demo=False)
        assert res.status == "NOT_CONFIGURED"
        assert res.provenance == "NOT_CONFIGURED"
        assert res.records == []
        assert res.records_count == 0
        assert res.is_demo is False
        assert "not configured" in str(res.error).lower()


def test_production_fail_closed_upstream_failure():
    with patch.object(source_orchestrator, "is_source_configured", return_value=True):
        with patch.object(source_orchestrator._adzuna_connector, "fetch_raw", return_value=[]):
            res = source_orchestrator.fetch_data(workload=WORKLOAD_JOBS, limit=10, is_demo=False)
            assert res.status == "UNAVAILABLE"
            assert res.provenance == "UNAVAILABLE"
            assert res.records == []
            assert res.records_count == 0
            assert res.is_demo is False

        with patch.object(source_orchestrator._adzuna_connector, "fetch_raw", side_effect=TimeoutError("Connection timed out")):
            res_timeout = source_orchestrator.fetch_data(workload=WORKLOAD_JOBS, limit=10, is_demo=False)
            assert res_timeout.status == "UNAVAILABLE"
            assert res_timeout.provenance == "UNAVAILABLE"
            assert res_timeout.records == []
            assert "timed out" in str(res_timeout.error).lower()


def test_explicit_demo_mode_isolation():
    res = source_orchestrator.fetch_data(workload=WORKLOAD_JOBS, limit=5, is_demo=True)
    assert res.status == "SUCCESS"
    assert res.provenance == SOURCE_TYPE_DEMO_SYNTHETIC
    assert res.is_demo is True
    assert len(res.records) > 0
    for r in res.records:
        assert r["source"] == "DEMO_SYNTHETIC"
        assert r["source_type"] == SOURCE_TYPE_DEMO_SYNTHETIC
        assert r["provenance"] == SOURCE_TYPE_DEMO_SYNTHETIC
        assert r["is_demo"] is True
        assert r["freshness_status"] == "STATIC_BASELINE"


def test_job_item_validation_and_provenance():
    valid_job = {
        "id": "job-101",
        "title": "Full Stack Engineer",
        "company": "Tech Corp Pune",
        "location": {"display_name": "Hinjawadi, Pune"},
        "vacancies_count": 2,
    }
    ok, err, cleaned = validate_job_item(valid_job)
    assert ok is True
    assert err is None
    assert cleaned["id"] == "job-101"
    assert cleaned["district"] == "Pune"
    assert cleaned["source_type"] == SOURCE_TYPE_LIVE_API
    assert cleaned["is_demo"] is False

    invalid_job = {
        "id": "",
        "title": "A",
        "company": "Tech",
    }
    ok_inv, err_inv, _ = validate_job_item(invalid_job)
    assert ok_inv is False
    assert err_inv is not None


def test_scheme_item_validation_and_provenance():
    valid_scheme = {
        "id": "sch-201",
        "title": "Maharashtra Skill Development Program",
        "department": "Skill Development Dept",
    }
    ok, err, cleaned = validate_scheme_item(valid_scheme)
    assert ok is True
    assert err is None
    assert cleaned["id"] == "sch-201"
    assert cleaned["source_type"] == SOURCE_TYPE_LIVE_API
    assert cleaned["is_demo"] is False

    invalid_scheme = {
        "id": "sch-202",
        "title": "No",
    }
    ok_inv, err_inv, _ = validate_scheme_item(invalid_scheme)
    assert ok_inv is False
    assert err_inv is not None


def test_industry_signal_source_contract():
    signal_data = {
        "title": "Solar Energy Technician Surging in Nashik District",
        "description": "Maharashtra renewable initiative expanded rooftop solar training targets for Q4 2026.",
        "category": "INDUSTRY_DEMAND",
        "industry": "Renewable Energy & Power",
        "skills": ["Solar PV Installation", "Grid Synchronization"],
        "source_url": "https://industry.maharashtra.gov.in/solar-announcement",
        "source_name": "Maharashtra Industry Directorate",
    }
    contract = create_industry_signal_contract(
        source="official_industry_bulletin",
        signal_type=SIGNAL_TYPE_DEMAND_TRENDS,
        raw_data=signal_data,
    )
    assert contract["signal_type"] == SIGNAL_TYPE_DEMAND_TRENDS
    assert contract["category"] == "INDUSTRY_DEMAND"
    assert contract["source_type"] == SOURCE_TYPE_LIVE_API
    assert contract["provenance"] == SOURCE_TYPE_LIVE_API
    assert contract["is_demo"] is False
    assert contract["content_hash"] is not None
    assert len(contract["content_hash"]) == 64

    with pytest.raises(ValueError):
        create_industry_signal_contract("source", "unsupported_type", signal_data)

    with pytest.raises(ValueError):
        bad_data = dict(signal_data)
        bad_data["title"] = "Tiny"
        create_industry_signal_contract("source", SIGNAL_TYPE_DEMAND_TRENDS, bad_data)


def test_source_diagnostics_no_secret_exposure():
    with patch.dict(os.environ, {"ADZUNA_APP_KEY": "super_secret_adzuna_token_xyz"}, clear=False):
        diag = source_orchestrator.get_source_diagnostics()
        assert "source_registry" in diag
        assert diag["total_registered_sources"] >= 4
        serialized = str(diag)
        assert "super_secret_adzuna_token_xyz" not in serialized
        assert "password" not in serialized.lower()

        supabase_entry = next(s for s in diag["source_registry"] if s["source_id"] == SOURCE_SUPABASE)
        assert supabase_entry["authoritative"] is True
        assert supabase_entry["fallback_available"] is False


def test_admin_integrations_health_includes_source_orchestration(client, admin_headers):
    res = client.get("/api/admin/integrations/health", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert "external_data" in data
    assert "source_registry" in data["external_data"]
    assert len(data["external_data"]["source_registry"]) >= 4

    registry_source_ids = {s["source_id"] for s in data["external_data"]["source_registry"]}
    assert SOURCE_ADZUNA in registry_source_ids
    assert SOURCE_DATAGOV in registry_source_ids
    assert SOURCE_SUPABASE in registry_source_ids
