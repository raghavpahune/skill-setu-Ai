import asyncio
import datetime
import json
import uuid
from unittest.mock import patch, MagicMock

import pytest
from starlette.testclient import TestClient

from app.config import settings
from app.core.data_mode import is_explicit_demo_mode
from app.db import load_demo_data, get_demo, save_sync_log
from app.ingestion.scheduler import IngestionScheduler, scheduler
from app.ingestion.sync_engine import SyncEngine
from app.mcp.server import MCPServer
from app.mcp.tools import (
    TOOLS,
    ALLOWED_MCP_SOURCES,
    tool_get_schemes,
    tool_get_opportunities,
    tool_get_skill_gaps,
    tool_get_sync_freshness,
    tool_refresh_data_source,
    tool_get_sync_logs,
)
from app.main import app


def test_mcp_tool_registration():
    server = MCPServer()
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {},
    }
    resp = server.handle_request(req)
    assert resp is not None
    assert "result" in resp
    tools = resp["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    expected = [
        "get_schemes",
        "get_opportunities",
        "get_skill_gaps",
        "get_sync_freshness",
        "refresh_data_source",
        "get_sync_logs",
    ]
    for exp in expected:
        assert exp in tool_names


def test_mcp_refresh_data_source_valid(monkeypatch):
    from app.config import settings
    from app.ingestion.scheduler import scheduler
    async def _mock_execute_sync(source="all"):
        return {
            "status": "success",
            "source": source,
            "records_fetched": 10,
            "records_added": 5,
            "records_updated": 5,
            "records_skipped": 0,
            "duration_ms": 120,
            "completed_at": "2026-09-06T12:00:00Z",
        }
    monkeypatch.setattr(scheduler, "execute_sync", _mock_execute_sync)
    monkeypatch.setattr(settings, "admin_api_key", "test-admin-secret-123")
    server = MCPServer()
    req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "refresh_data_source",
            "arguments": {"source": "data.gov.in", "admin_key": "test-admin-secret-123"},
        },
    }
    resp = server.handle_request(req)
    assert resp is not None
    assert "result" in resp
    content_raw = resp["result"]["content"][0]["text"]
    content = json.loads(content_raw)
    assert content["status"] in ("success", "skipped")
    assert content["source"] == "data.gov.in"
    assert "records_fetched" in content

    secret_keywords = ["api_key", "secret", "password", "token", "authorization"]
    for keyword in secret_keywords:
        assert keyword not in content_raw.lower()


def test_mcp_refresh_data_source_invalid(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "admin_api_key", "test-admin-secret-123")
    server = MCPServer()
    req = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "refresh_data_source",
            "arguments": {"source": "https://malicious.com/exploit", "admin_key": "test-admin-secret-123"},
        },
    }
    resp = server.handle_request(req)
    assert resp is not None
    assert "result" in resp
    content = json.loads(resp["result"]["content"][0]["text"])
    assert content["status"] == "error"
    assert "Invalid source" in content["error"]


def test_mcp_get_sync_logs():
    server = MCPServer()
    req = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "get_sync_logs",
            "arguments": {"limit": 5},
        },
    }
    resp = server.handle_request(req)
    assert resp is not None
    assert "result" in resp
    content = json.loads(resp["result"]["content"][0]["text"])
    assert "logs" in content
    assert isinstance(content["logs"], list)
    for log in content["logs"]:
        assert "id" in log
        assert "status" in log
        for secret_field in ("api_key", "key", "token", "secret", "authorization"):
            assert secret_field not in log


def test_mcp_get_sync_freshness():
    res = tool_get_sync_freshness({"source": "data.gov.in"})
    assert "status" in res
    assert "active_sources" in res
    assert "last_records_fetched" in res
    assert isinstance(res["active_sources"], list)
    assert "data.gov.in" in res["active_sources"]


def test_scheduler_configurable_interval():
    assert hasattr(settings, "refresh_interval_minutes")
    assert isinstance(settings.refresh_interval_minutes, int)
    assert settings.refresh_interval_minutes > 0
    assert hasattr(settings, "sync_sources")
    sched = IngestionScheduler()
    status = sched.get_status()
    assert "refresh_interval_minutes" in status
    assert status["refresh_interval_minutes"] == settings.effective_refresh_interval_minutes


def test_scheduler_startup_and_shutdown():
    async def _test():
        sched = IngestionScheduler()
        assert not sched.is_active
        sched.start()
        assert sched.is_active
        await sched.stop()
        assert not sched.is_active

    asyncio.run(_test())


def test_scheduler_in_process_overlap_protection():
    async def _test():
        sched = IngestionScheduler()
        async with sched._get_lock():
            sched._is_sync_running = True
            res = await sched.execute_sync(source="data.gov.in")
            assert res.get("status") == "skipped"
            assert "already in progress" in res.get("message", "")
            sched._is_sync_running = False

    asyncio.run(_test())


def test_scheduler_distributed_stale_vs_active_lock():
    sched = IngestionScheduler()
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    stale_dt = (now_dt - datetime.timedelta(minutes=30)).isoformat()
    active_dt = (now_dt - datetime.timedelta(minutes=2)).isoformat()

    with patch("app.repositories.supabase_repository.list_sync_logs", return_value=[
        {"id": "stale-1", "status": "running", "started_at": stale_dt}
    ]):
        assert not sched._check_active_distributed_sync(lease_seconds=900)

    with patch("app.repositories.supabase_repository.list_sync_logs", return_value=[
        {"id": "active-1", "status": "running", "started_at": active_dt}
    ]):
        assert sched._check_active_distributed_sync(lease_seconds=900)


def test_scheduler_failure_resilience():
    async def _test():
        sched = IngestionScheduler()
        mock_engine = MagicMock()
        mock_engine.run_sync.side_effect = RuntimeError("External connector connection timeout")
        sched.engine = mock_engine

        res = await sched.execute_sync(source="adzuna")
        assert res.get("status") == "failed"
        assert "connection timeout" in res.get("error_message", "")
        status = sched.get_status()
        assert status["last_error"] is not None

        mock_engine.run_sync.side_effect = None
        mock_engine.run_sync.return_value = {"status": "success", "duration_ms": 12, "records_fetched": 1}
        res2 = await sched.execute_sync(source="adzuna")
        assert res2.get("status") == "success"
        status2 = sched.get_status()
        assert status2["last_error"] is None
        assert status2["last_successful_run_timestamp"] is not None

    asyncio.run(_test())


def test_sync_engine_supabase_authority_real_mode():
    engine = SyncEngine()
    mock_existing_schemes = [
        {
            "id": "sch-auth-01",
            "source": "OGD_DATAGOV_IN",
            "external_id": "EXT_SCH_01",
            "content_hash": "hash_existing_01",
            "title": "Scholarship for Technical Students",
            "is_demo": False,
        }
    ]

    incoming = [
        {
            "id": "incoming-uuid-01",
            "source": "OGD_DATAGOV_IN",
            "external_id": "EXT_SCH_01",
            "content_hash": "hash_existing_01",
            "title": "Scholarship for Technical Students",
            "is_demo": False,
        },
        {
            "id": "incoming-uuid-02",
            "source": "OGD_DATAGOV_IN",
            "external_id": "EXT_SCH_02",
            "content_hash": "hash_new_02",
            "title": "Apprentice Tool Grant",
            "is_demo": False,
        },
    ]

    with patch("app.repositories.supabase_repository.list_schemes", return_value=mock_existing_schemes) as mock_list, \
         patch("app.repositories.supabase_repository.upsert_schemes", return_value=incoming) as mock_upsert, \
         patch("app.ingestion.sync_engine.is_supabase_connected", return_value=True), \
         patch("app.ingestion.sync_engine.is_explicit_demo_mode", return_value=False):

        added, updated = engine._upsert_schemes(incoming)
        assert updated == 1
        assert added == 1
        assert incoming[0]["id"] == "sch-auth-01"
        assert incoming[0]["last_seen_at"] is not None
        assert mock_upsert.called


def test_stable_identity_preservation_different_ext_id_same_hash():
    engine = SyncEngine()
    mock_jobs = [
        {
            "id": "job-original-id",
            "source": "ADZUNA_API",
            "external_id": "ADZUNA_11111",
            "content_hash": "shared_identical_hash_123",
            "title": "CNC Machinist",
        }
    ]

    incoming_jobs = [
        {
            "id": "job-incoming-different",
            "source": "ADZUNA_API",
            "external_id": "ADZUNA_22222",
            "content_hash": "shared_identical_hash_123",
            "title": "CNC Machinist",
        }
    ]

    with patch("app.repositories.supabase_repository.list_jobs", return_value=mock_jobs), \
         patch("app.repositories.supabase_repository.upsert_jobs", return_value=incoming_jobs), \
         patch("app.ingestion.sync_engine.is_supabase_connected", return_value=True), \
         patch("app.ingestion.sync_engine.is_explicit_demo_mode", return_value=False):

        added, updated = engine._upsert_jobs(incoming_jobs)
        assert added == 1
        assert updated == 0
        assert incoming_jobs[0]["id"] != "job-original-id"
        assert incoming_jobs[0]["external_id"] == "ADZUNA_22222"


def test_repeated_sightings_update_timestamps():
    engine = SyncEngine()
    earlier_ts = "2026-08-01T10:00:00+00:00"
    mock_jobs = [
        {
            "id": "job-repeated-01",
            "source": "ADZUNA_API",
            "external_id": "ADZUNA_REPEATED",
            "content_hash": "rep_hash_999",
            "title": "Robotics Technician",
            "last_seen_at": earlier_ts,
            "last_synced_at": earlier_ts,
        }
    ]

    incoming = [
        {
            "source": "ADZUNA_API",
            "external_id": "ADZUNA_REPEATED",
            "content_hash": "rep_hash_999",
            "title": "Robotics Technician",
        }
    ]

    with patch("app.repositories.supabase_repository.list_jobs", return_value=mock_jobs), \
         patch("app.repositories.supabase_repository.upsert_jobs", return_value=incoming), \
         patch("app.ingestion.sync_engine.is_supabase_connected", return_value=True), \
         patch("app.ingestion.sync_engine.is_explicit_demo_mode", return_value=False):

        added, updated = engine._upsert_jobs(incoming)
        assert updated == 1
        assert added == 0
        assert incoming[0]["id"] == "job-repeated-01"
        assert incoming[0]["last_seen_at"] != earlier_ts
        assert incoming[0]["last_synced_at"] != earlier_ts


def test_provenance_labels_preserved():
    from app.ingestion.base_adapter import (
        SOURCE_TYPE_LIVE_API,
        SOURCE_TYPE_VERIFIED_SNAPSHOT,
        SOURCE_TYPE_SANDBOX_SIMULATION,
    )
    from app.ingestion.adzuna_connector import AdzunaConnector
    from app.ingestion.datagov_connector import DataGovConnector

    adzuna = AdzunaConnector(app_id="", app_key="")
    raw_snapshot = adzuna.fetch_raw(page=1)
    jobs = adzuna.validate_and_transform(raw_snapshot)
    for j in jobs:
        assert j["source_type"] == SOURCE_TYPE_VERIFIED_SNAPSHOT
        assert j["source_type"] != SOURCE_TYPE_LIVE_API

    datagov = DataGovConnector(api_key="")
    raw_sand = datagov.fetch_resource("645b9f3e-e082-47d4-8098-e1c2b1a9e7f0")
    opps = datagov.transform_naps_opportunities(raw_sand.get("records", []))
    for o in opps:
        assert o["source_type"] == SOURCE_TYPE_SANDBOX_SIMULATION
        assert o["source_type"] != SOURCE_TYPE_LIVE_API


def test_api_sync_endpoints():
    with TestClient(app) as client:
        status_res = client.get("/api/sync/status")
        assert status_res.status_code == 200
        data = status_res.json()
        assert data["status"] in ("healthy", "degraded")
        assert "scheduler" in data
        assert "refresh_interval_minutes" in data
        assert data["refresh_interval_minutes"] == settings.effective_refresh_interval_minutes

        bad_trigger = client.post("/api/sync/trigger?source=invalid_external_source")
        assert bad_trigger.status_code == 400
        assert "Invalid sync source selector" in bad_trigger.json()["detail"]

        good_trigger = client.post("/api/sync/trigger?source=data.gov.in")
        assert good_trigger.status_code == 200
        trig_data = good_trigger.json()
        assert trig_data["status"] in ("success", "skipped", "failed")


def test_mcp_sync_tools_filter_persisted_demo_logs():
    raw_demo_log = {
        "id": "mcp-demo-1",
        "source_name": "data.gov.in",
        "status": "success",
        "is_demo": True,
        "records_fetched": 100,
        "records_added": 100,
        "records_updated": 0,
        "started_at": "2026-09-12T06:00:00Z",
        "completed_at": "2026-09-12T06:00:01Z",
    }
    raw_real_log = {
        "id": "mcp-real-1",
        "source_name": "data.gov.in",
        "status": "failed",
        "is_demo": False,
        "records_fetched": 0,
        "records_added": 0,
        "records_updated": 0,
        "started_at": "2026-09-12T06:01:00Z",
        "completed_at": "2026-09-12T06:01:02Z",
    }

    with patch("app.mcp.tools.is_explicit_demo_mode", return_value=False), \
         patch("app.repositories.supabase_repository.list_sync_logs", return_value=[raw_real_log, raw_demo_log]):
        logs_res = tool_get_sync_logs({"limit": 10})
        freshness_res = tool_get_sync_freshness({})

    assert len(logs_res["logs"]) == 1
    assert logs_res["logs"][0]["id"] == "mcp-real-1"
    assert freshness_res["status"] == "failed"


def test_scheduler_distributed_lock_ignores_demo_running_log():
    sched = IngestionScheduler()
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    active_dt = (now_dt - datetime.timedelta(minutes=2)).isoformat()

    demo_running_log = {
        "id": "demo-run-1",
        "status": "running",
        "is_demo": True,
        "started_at": active_dt,
    }

    with patch("app.ingestion.scheduler.is_explicit_demo_mode", return_value=False), \
         patch("app.repositories.supabase_repository.list_sync_logs", return_value=[demo_running_log]):
        assert not sched._check_active_distributed_sync(lease_seconds=900)


def test_scheduler_catchup_ignores_demo_log():
    sched = IngestionScheduler()
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    recent_dt = (now_dt - datetime.timedelta(minutes=5)).isoformat()

    recent_demo_log = {
        "id": "demo-log-recent",
        "status": "success",
        "is_demo": True,
        "started_at": recent_dt,
    }

    with patch("app.ingestion.scheduler.is_explicit_demo_mode", return_value=False), \
         patch("app.repositories.supabase_repository.list_sync_logs", return_value=[recent_demo_log]):
        assert sched._should_catchup_sync()


def test_scheduler_detects_older_real_running_log_despite_more_recent_demo_logs():
    sched = IngestionScheduler()
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    demo_rows = [
        {
            "id": f"demo-{i}",
            "source_name": "data.gov.in",
            "job_type": "scheduled_sync",
            "status": "success",
            "records_fetched": 100,
            "error_message": "||SOURCES_DETAIL:" + json.dumps({"_meta": {"is_demo": True}}),
            "started_at": (now_dt - datetime.timedelta(minutes=1, seconds=i)).isoformat(),
            "completed_at": (now_dt - datetime.timedelta(minutes=1, seconds=i - 1)).isoformat(),
        }
        for i in range(520)
    ]
    real_running_row = {
        "id": "real-running-active",
        "source_name": "data.gov.in",
        "job_type": "scheduled_sync",
        "status": "running",
        "records_fetched": 0,
        "error_message": "||SOURCES_DETAIL:" + json.dumps({"_meta": {"is_demo": False}}),
        "started_at": (now_dt - datetime.timedelta(minutes=2)).isoformat(),
    }
    all_rows = demo_rows + [real_running_row]

    mock_client = MagicMock()
    mock_query = MagicMock()
    mock_client.table.return_value.select.return_value = mock_query
    mock_query.order.return_value = mock_query

    def mock_range(start, end):
        res = MagicMock()
        res.data = all_rows[start : end + 1]
        mock_query.execute.return_value = res
        return mock_query

    mock_query.range.side_effect = mock_range

    with patch("app.ingestion.scheduler.is_explicit_demo_mode", return_value=False), \
         patch("app.repositories.supabase_repository.get_client", return_value=mock_client):
        assert sched._check_active_distributed_sync(lease_seconds=900) is True
