"""Test suite for Task 2 Step 4B: data.gov.in Ingestion Connector, Deduplication, and Sync Logs."""
import os
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

import pytest
from starlette.testclient import TestClient
from app.main import app
from app.db import _cache, load_demo_data, get_demo
from app.ingestion.datagov_connector import DataGovConnector
from app.ingestion.sync_engine import SyncEngine


@pytest.fixture(scope="module", autouse=True)
def isolate_sync_step4b_cache():
    from copy import deepcopy
    snapshot = deepcopy(_cache)
    old_mode = os.environ.get("SKILLSETU_DATA_MODE")
    os.environ["SKILLSETU_DATA_MODE"] = "demo"
    _cache["schemes"] = [s for s in _cache.get("schemes", []) if s.get("source") != "OGD_DATAGOV_IN"]
    _cache["sync_logs"] = [l for l in _cache.get("sync_logs", []) if l.get("source_name") != "data.gov.in"]
    yield
    _cache.clear()
    _cache.update(snapshot)
    if old_mode is None:
        os.environ.pop("SKILLSETU_DATA_MODE", None)
    else:
        os.environ["SKILLSETU_DATA_MODE"] = old_mode


load_demo_data()
client = TestClient(app)


def test_connector_and_transformers():
    print("Testing DataGovConnector & Transformers...")
    connector = DataGovConnector()

    # Test fallback sandbox fetching
    raw_sch = connector.fetch_resource("bf44869a-519f-43cd-84f0-4914e32a37a8")
    assert raw_sch.get("status") == "ok"
    records = raw_sch.get("records", [])
    assert len(records) > 0, "Should have records"

    # Test scheme transformation
    schemes = connector.transform_scholarship_schemes(records)
    assert len(schemes) == len(records)
    first_sch = schemes[0]
    assert first_sch["source"] == "OGD_DATAGOV_IN"
    assert first_sch["external_id"].startswith("SCHOLARSHIP_ALLOC_")
    assert first_sch["scheme_type"] == "scholarship"

    # Test NAPS opportunities transformation
    raw_naps = connector.fetch_resource("645b9f3e-e082-47d4-8098-e1c2b1a9e7f0")
    naps_records = raw_naps.get("records", [])
    opps = connector.transform_naps_opportunities(naps_records)
    assert len(opps) == len(naps_records)
    first_opp = opps[0]
    assert first_opp["source"] == "OGD_DATAGOV_IN"
    assert first_opp["opportunity_type"] == "apprenticeship"
    assert first_opp["portal_source"] == "NAPS"
    assert first_opp["external_id"].startswith("NAPS_DIST_")

    print(f"  OK: Transformed {len(schemes)} schemes and {len(opps)} opportunities.")


def test_sync_engine_and_deduplication():
    print("Testing SyncEngine & Deduplication...")
    load_demo_data()
    engine = SyncEngine()

    # Initial Run: Should add new records
    run1 = engine.run_sync(source_name="data.gov.in")
    assert run1["status"] == "success"
    assert run1["records_fetched"] > 0
    added_run1 = run1["records_added"]
    assert added_run1 > 0, f"Expected records added, got {added_run1}"
    assert run1["duration_ms"] >= 0
    print(f"  OK Run 1: Ingested {added_run1} records in {run1['duration_ms']} ms.")

    # Second Run: Must deduplicate! All existing records should be updated, 0 added
    run2 = engine.run_sync(source_name="data.gov.in")
    assert run2["status"] == "success"
    assert run2["records_added"] == 0, f"Deduplication failed: records_added should be 0, got {run2['records_added']}"
    assert run2["records_updated"] == added_run1, f"Expected {added_run1} updated, got {run2['records_updated']}"
    print(f"  OK Run 2 (Deduplication): 0 duplicates added, {run2['records_updated']} records updated in {run2['duration_ms']} ms.")

    # Verify sync_logs table/cache has both entries
    sync_logs = get_demo("sync_logs")
    datagov_logs = [log for log in sync_logs if log.get("source_name") == "data.gov.in"]
    assert len(datagov_logs) >= 2
    for log in datagov_logs:
        assert log["source_name"] == "data.gov.in"
        assert log["status"] == "success"
        assert log["completed_at"] is not None
    print(f"  OK: Verified sync_logs has {len(datagov_logs)} valid audit records.")


def test_sync_api_endpoints():
    print("Testing Sync API Endpoints...")

    # GET /api/sync/status
    res_status = client.get("/api/sync/status")
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert status_data["status"] == "healthy"
    assert "approved_datasets" in status_data
    assert len(status_data["approved_datasets"]) == 5
    assert "total_sync_runs" in status_data
    print(f"  OK: /api/sync/status returned {len(status_data['approved_datasets'])} approved datasets.")

    # GET /api/sync/logs
    res_logs = client.get("/api/sync/logs")
    assert res_logs.status_code == 200
    logs = res_logs.json()
    assert isinstance(logs, list) and len(logs) >= 2
    print(f"  OK: /api/sync/logs returned {len(logs)} audit entries.")

    # POST /api/sync/trigger
    res_trigger = client.get("/api/sync/status")
    res_post = client.post(
        "/api/sync/trigger?source=data.gov.in",
        headers={"X-Admin-Key": "demo-admin-key-2026"},
    )
    assert res_post.status_code == 200
    trigger_res = res_post.json()
    assert trigger_res["status"] == "success"
    assert trigger_res["records_added"] == 0  # Since already deduplicated
    assert trigger_res["records_updated"] > 0
    print(f"  OK: POST /api/sync/trigger executed successfully.")


def test_reflection_in_schemes_and_opportunities():
    print("Testing data reflection in /api/schemes and /api/opportunities...")

    # Check that OGD schemes appear in /api/schemes
    res_schemes = client.get("/api/schemes")
    assert res_schemes.status_code == 200
    schemes = res_schemes.json()
    ogd_schemes = [s for s in schemes if s.get("source") == "OGD_DATAGOV_IN"]
    assert len(ogd_schemes) > 0, "Ingested schemes should be queryable via /api/schemes"
    print(f"  OK: Found {len(ogd_schemes)} OGD schemes in /api/schemes.")

    # Check that NAPS opportunities appear in /api/opportunities
    res_opps = client.get("/api/opportunities?opportunity_type=apprenticeship")
    assert res_opps.status_code == 200
    opps = res_opps.json()
    ogd_opps = [o for o in opps if o.get("source") == "OGD_DATAGOV_IN"]
    assert len(ogd_opps) > 0, "Ingested apprenticeships should be queryable via /api/opportunities"
    print(f"  OK: Found {len(ogd_opps)} OGD apprenticeships in /api/opportunities.")


def test_backward_compatibility():
    print("Testing backward compatibility of existing endpoints...")
    res_jobs = client.get("/api/jobs")
    assert res_jobs.status_code == 200
    assert len(res_jobs.json()) > 0

    res_skills = client.get("/api/skills")
    assert res_skills.status_code == 200

    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ok"
    print("  OK: Core APIs intact.")


if __name__ == "__main__":
    test_connector_and_transformers()
    test_sync_engine_and_deduplication()
    test_sync_api_endpoints()
    test_reflection_in_schemes_and_opportunities()
    test_backward_compatibility()
    print("\nALL STEP 4B INGESTION TESTS PASSED SUCCESSFULLY!")
