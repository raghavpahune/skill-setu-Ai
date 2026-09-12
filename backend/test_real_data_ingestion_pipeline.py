from unittest.mock import patch, MagicMock
import httpx
import pytest
from app.ingestion.datagov_connector import (
    DataGovConnector,
    RESOURCE_SCHOLARSHIP_ALLOCATION,
)
from app.ingestion.adzuna_connector import AdzunaConnector
from app.ingestion.industry_intelligence import (
    SAMPLE_VERIFIED_FEEDS,
    IndustryIntelligenceIngestor,
)
from app.ingestion.sync_engine import SyncEngine
from app.services.district_service import get_all_districts


def test_datagov_live_success_mocked():
    connector = DataGovConnector(api_key="genuine_test_key_12345")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "records": [
            {
                "id": "101",
                "state": "Maharashtra",
                "scheme_name": "Post-Matric Scholarship",
                "amount": "50000",
            }
        ]
    }

    with patch("httpx.get", return_value=mock_response):
        result = connector.fetch_resource(RESOURCE_SCHOLARSHIP_ALLOCATION, is_demo=False)

    assert result["status"] in ("SUCCESS", "ok")
    assert result["source_available"] is True
    assert result["error"] is None
    assert len(result["records"]) == 1
    assert result["records"][0]["is_sandbox"] is False


def test_datagov_auth_failure_no_demo_fallback():
    connector = DataGovConnector(api_key="invalid_test_key")
    mock_response = MagicMock()
    mock_response.status_code = 403

    with patch("httpx.get", return_value=mock_response):
        result = connector.fetch_resource(RESOURCE_SCHOLARSHIP_ALLOCATION, is_demo=False)

    assert result["status"] == "FAILED"
    assert result["source_available"] is False
    assert "authentication failed" in result["error"]
    assert result["records"] == []


def test_datagov_missing_api_key_no_demo_fallback():
    connector = DataGovConnector(api_key="")
    result = connector.fetch_resource(RESOURCE_SCHOLARSHIP_ALLOCATION, is_demo=False)

    assert result["status"] == "NOT_CONFIGURED"
    assert result["source_available"] is False
    assert "DATA_GOV_API_KEY is not configured" in result["error"]
    assert result["records"] == []


def test_datagov_timeout_no_demo_fallback():
    connector = DataGovConnector(api_key="valid_key")

    with patch("httpx.get", side_effect=httpx.TimeoutException("Connection timed out")):
        result = connector.fetch_resource(RESOURCE_SCHOLARSHIP_ALLOCATION, is_demo=False)

    assert result["status"] == "FAILED"
    assert result["source_available"] is False
    assert "Network issue" in result["error"]
    assert result["records"] == []


def test_datagov_zero_records_no_demo_fallback():
    connector = DataGovConnector(api_key="valid_key")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"records": []}

    with patch("httpx.get", return_value=mock_response):
        result = connector.fetch_resource(RESOURCE_SCHOLARSHIP_ALLOCATION, is_demo=False)

    assert result["status"] == "NO_DATA"
    assert result["source_available"] is True
    assert result["records"] == []


def test_datagov_explicit_demo_mode_allows_sandbox():
    connector = DataGovConnector(api_key="")
    result = connector.fetch_resource(RESOURCE_SCHOLARSHIP_ALLOCATION, is_demo=True)

    assert result["status"] in ("SUCCESS", "ok")
    assert result["source_available"] is True
    assert len(result["records"]) > 0
    assert result["records"][0].get("is_sandbox") is True


def test_adzuna_live_success_mocked():
    connector = AdzunaConnector(app_id="test_id", app_key="test_key")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {
                "id": "adz-12345",
                "title": "Robotics Engineer",
                "company": {"display_name": "Kirloskar Industries"},
                "location": {"display_name": "Pune, Maharashtra", "area": ["India", "Maharashtra", "Pune"]},
                "category": {"label": "Manufacturing"},
                "redirect_url": "https://www.adzuna.in/jobs/details/12345",
                "created": "2026-09-10T10:00:00Z",
            }
        ]
    }

    with patch("httpx.get", return_value=mock_response):
        results = connector.fetch_raw(is_demo=False)

    assert connector.last_status == "SUCCESS"
    assert connector.last_error is None
    assert len(results) == 1
    assert results[0]["is_snapshot"] is False


def test_adzuna_auth_failure_no_demo_fallback():
    connector = AdzunaConnector(app_id="invalid_id", app_key="invalid_key")
    mock_response = MagicMock()
    mock_response.status_code = 401

    with patch("httpx.get", return_value=mock_response):
        results = connector.fetch_raw(is_demo=False)

    assert connector.last_status == "FAILED"
    assert "authentication failed" in connector.last_error
    assert results == []


def test_adzuna_missing_credentials_no_demo_fallback():
    connector = AdzunaConnector(app_id="", app_key="")
    results = connector.fetch_raw(is_demo=False)

    assert connector.last_status == "NOT_CONFIGURED"
    assert "not configured" in connector.last_error
    assert results == []


def test_adzuna_timeout_no_demo_fallback():
    connector = AdzunaConnector(app_id="valid_id", app_key="valid_key")

    with patch("httpx.get", side_effect=httpx.TimeoutException("Adzuna timeout")):
        results = connector.fetch_raw(is_demo=False)

    assert connector.last_status == "FAILED"
    assert "Adzuna network issue" in connector.last_error
    assert results == []


def test_adzuna_explicit_demo_mode_allows_snapshot():
    connector = AdzunaConnector(app_id="", app_key="")
    results = connector.fetch_raw(is_demo=True)

    assert connector.last_status == "SUCCESS"
    assert len(results) > 0
    assert results[0].get("is_snapshot") is True


def test_industry_signals_synthetic_classified_as_demo():
    for item in SAMPLE_VERIFIED_FEEDS:
        assert item.get("is_demo") is True
        assert item.get("source_type") == "DEMO_SYNTHETIC"
        assert item.get("source_label") == "DEMO_SYNTHETIC"
        assert item.get("data_provenance") == "DEMO_SYNTHETIC"
        assert item.get("validation_status") in ("APPROVED", "DEMO")

    ingestor = IndustryIntelligenceIngestor()
    normalized, err = ingestor.validate_and_normalize(SAMPLE_VERIFIED_FEEDS[0])
    assert err is None
    assert normalized["is_demo"] is True
    assert normalized["data_provenance"] == "DEMO_SYNTHETIC"
    assert normalized["validation_status"] in ("APPROVED", "DEMO")


def test_signals_router_real_mode_no_synthetic_injection():
    import asyncio
    from app.routers.signals import legacy_list_signals

    with patch("app.routers.signals.list_industry_signals_repo", return_value=[]):
        signals = asyncio.run(legacy_list_signals(is_demo=False))

    assert signals == []


def test_district_service_real_mode_no_demo_fallback():
    with patch("app.repositories.supabase_repository.list_jobs", return_value=[]), \
         patch("app.repositories.supabase_repository.list_courses", return_value=[]):
        districts = get_all_districts(is_demo=False)

    assert districts == []


def test_sync_engine_status_matrix():
    dg_conn = DataGovConnector(api_key="")
    adz_conn = AdzunaConnector(app_id="", app_key="")
    engine = SyncEngine(datagov_connector=dg_conn, adzuna_connector=adz_conn)

    with patch("app.ingestion.sync_engine.is_explicit_demo_mode", return_value=False):
        log = engine.run_sync(source_name="all")

    assert log["status"] in ("failed", "partial")
    assert "data.gov.in" in log["sources_detail"]
    assert log["sources_detail"]["data.gov.in"]["status"] == "NOT_CONFIGURED"
    assert log["sources_detail"]["adzuna"]["status"] == "NOT_CONFIGURED"


def test_sync_status_endpoint_per_source():
    import asyncio
    from app.routers.sync import get_sync_status

    status_resp = asyncio.run(get_sync_status(is_demo=False))
    assert "sources" in status_resp
    assert "data.gov.in" in status_resp["sources"]
    assert "adzuna" in status_resp["sources"]
    assert "industry_signals" in status_resp["sources"]
    assert "skill_forecasts" in status_resp["sources"]


def test_sync_status_latest_failed_reports_failed():
    import asyncio
    from app.routers.sync import get_sync_status

    failed_log = {
        "id": "log-fail-1",
        "source_name": "data.gov.in",
        "job_type": "scheduled_sync",
        "status": "failed",
        "records_fetched": 0,
        "records_added": 0,
        "records_updated": 0,
        "records_skipped": 0,
        "error_message": "data.gov.in: FAILED - 403 Forbidden: authentication failed",
        "started_at": "2026-09-12T00:00:00Z",
        "completed_at": "2026-09-12T00:00:01Z",
        "sources_detail": {
            "data.gov.in": {
                "status": "FAILED",
                "error": "403 Forbidden: authentication failed",
                "records_fetched": 0,
                "records_added": 0,
                "records_updated": 0,
                "records_skipped": 0,
            }
        },
    }

    with patch("app.ingestion.datagov_connector.DataGovConnector.has_api_key", True), \
         patch("app.repositories.supabase_repository.list_sync_logs", return_value=[failed_log]), \
         patch("app.db._cache", {"sync_logs": [failed_log]}):
        res = asyncio.run(get_sync_status(is_demo=False))

    assert res["status"] == "failed"
    assert res["sources"]["data.gov.in"]["status"] == "FAILED"
    assert res["sources"]["data.gov.in"]["configured"] is True
    assert "403 Forbidden" in res["sources"]["data.gov.in"]["error"]
    assert res["sources"]["data.gov.in"]["records_fetched"] == 0
    assert res["last_sync"]["id"] == "log-fail-1"


def test_sync_status_configured_credentials_zero_records_no_data():
    import asyncio
    from app.routers.sync import get_sync_status

    nodata_log = {
        "id": "log-nodata-1",
        "source_name": "data.gov.in",
        "job_type": "scheduled_sync",
        "status": "success",
        "records_fetched": 0,
        "records_added": 0,
        "records_updated": 0,
        "records_skipped": 0,
        "error_message": None,
        "started_at": "2026-09-12T00:00:00Z",
        "completed_at": "2026-09-12T00:00:01Z",
        "sources_detail": {
            "data.gov.in": {
                "status": "NO_DATA",
                "error": None,
                "records_fetched": 0,
                "records_added": 0,
                "records_updated": 0,
                "records_skipped": 0,
            }
        },
    }

    with patch("app.ingestion.datagov_connector.DataGovConnector.has_api_key", True), \
         patch("app.repositories.supabase_repository.list_sync_logs", return_value=[nodata_log]), \
         patch("app.db._cache", {"sync_logs": [nodata_log]}):
        res = asyncio.run(get_sync_status(is_demo=False))

    assert res["sources"]["data.gov.in"]["status"] == "NO_DATA"
    assert res["sources"]["data.gov.in"]["error"] is None
    assert res["sources"]["data.gov.in"]["records_fetched"] == 0
    assert res["status"] == "degraded"


def test_sync_status_historical_success_not_masking_current_failure():
    import asyncio
    from app.routers.sync import get_sync_status

    recent_fail = {
        "id": "log-recent-fail",
        "source_name": "data.gov.in",
        "status": "failed",
        "records_fetched": 0,
        "error_message": "data.gov.in: FAILED - Connection timed out",
        "started_at": "2026-09-12T02:00:00Z",
        "completed_at": "2026-09-12T02:00:02Z",
        "sources_detail": {
            "data.gov.in": {
                "status": "FAILED",
                "error": "Connection timed out",
                "records_fetched": 0,
            }
        },
    }
    old_success = {
        "id": "log-old-success",
        "source_name": "data.gov.in",
        "status": "success",
        "records_fetched": 50,
        "records_added": 50,
        "records_updated": 0,
        "records_skipped": 0,
        "error_message": None,
        "started_at": "2026-09-11T02:00:00Z",
        "completed_at": "2026-09-11T02:00:05Z",
        "sources_detail": {
            "data.gov.in": {
                "status": "SUCCESS",
                "error": None,
                "records_fetched": 50,
                "records_added": 50,
                "records_updated": 0,
                "records_skipped": 0,
            }
        },
    }

    with patch("app.ingestion.datagov_connector.DataGovConnector.has_api_key", True), \
         patch("app.repositories.supabase_repository.list_sync_logs", return_value=[recent_fail, old_success]), \
         patch("app.db._cache", {"sync_logs": [recent_fail, old_success]}):
        res = asyncio.run(get_sync_status(is_demo=False))

    assert res["sources"]["data.gov.in"]["status"] == "FAILED"
    assert res["status"] == "failed"
    assert "timed out" in res["sources"]["data.gov.in"]["error"]
    assert res["last_sync"]["id"] == "log-recent-fail"
    assert res["last_successful_sync"]["id"] == "log-old-success"


def test_sync_status_missing_credentials_reports_not_configured():
    import asyncio
    from app.routers.sync import get_sync_status

    with patch("app.ingestion.datagov_connector.DataGovConnector.has_api_key", False), \
         patch("app.ingestion.adzuna_connector.AdzunaConnector.has_credentials", False), \
         patch("app.repositories.supabase_repository.list_sync_logs", return_value=[]), \
         patch("app.db._cache", {"sync_logs": []}):
        res = asyncio.run(get_sync_status(is_demo=False))

    assert res["sources"]["data.gov.in"]["status"] == "NOT_CONFIGURED"
    assert res["sources"]["data.gov.in"]["configured"] is False
    assert "DATA_GOV_API_KEY is not configured" in res["sources"]["data.gov.in"]["error"]
    assert res["sources"]["adzuna"]["status"] == "NOT_CONFIGURED"
    assert res["sources"]["adzuna"]["configured"] is False
    assert "ADZUNA_APP_ID" in res["sources"]["adzuna"]["error"]
    assert res["status"] == "degraded"


def test_sync_status_successful_real_ingestion():
    import asyncio
    from app.routers.sync import get_sync_status

    success_log = {
        "id": "log-success-1",
        "source_name": "data.gov.in",
        "status": "success",
        "records_fetched": 30,
        "records_added": 30,
        "records_updated": 0,
        "records_skipped": 0,
        "error_message": None,
        "started_at": "2026-09-12T03:00:00Z",
        "completed_at": "2026-09-12T03:00:03Z",
        "sources_detail": {
            "data.gov.in": {
                "status": "SUCCESS",
                "error": None,
                "records_fetched": 30,
                "records_added": 30,
                "records_updated": 0,
                "records_skipped": 0,
            }
        },
    }

    with patch("app.ingestion.datagov_connector.DataGovConnector.has_api_key", True), \
         patch("app.repositories.supabase_repository.list_sync_logs", return_value=[success_log]), \
         patch("app.db._cache", {"sync_logs": [success_log]}):
        res = asyncio.run(get_sync_status(is_demo=False))

    assert res["sources"]["data.gov.in"]["status"] == "SUCCESS"
    assert res["sources"]["data.gov.in"]["records_fetched"] == 30
    assert res["sources"]["data.gov.in"]["error"] is None
    assert res["status"] == "healthy"


def test_sync_status_demo_mode_isolated():
    import asyncio
    from app.routers.sync import get_sync_status

    res = asyncio.run(get_sync_status(is_demo=True))
    assert res["status"] == "healthy"
    assert res["sources"]["data.gov.in"]["status"] == "SUCCESS"
    assert res["sources"]["adzuna"]["status"] == "SUCCESS"
    assert res["sources"]["data.gov.in"]["configured"] is True
    assert res["sources"]["adzuna"]["configured"] is True


def test_sync_log_persistence_encoding_and_decoding():
    from app.db import save_sync_log, decode_sync_log

    entry = {
        "id": "test-encode-id-1",
        "source_name": "data.gov.in",
        "job_type": "scheduled_sync",
        "status": "failed",
        "records_fetched": 0,
        "records_added": 0,
        "records_updated": 0,
        "records_skipped": 0,
        "error_message": "data.gov.in: FAILED - 500 server error",
        "started_at": "2026-09-12T04:00:00Z",
        "completed_at": "2026-09-12T04:00:01Z",
        "duration_ms": 150,
        "sources_detail": {
            "data.gov.in": {
                "status": "FAILED",
                "error": "500 server error",
                "records_fetched": 0,
                "records_added": 0,
                "records_updated": 0,
                "records_skipped": 0,
            }
        },
    }

    mock_client = MagicMock()
    with patch("app.db.get_supabase_client", return_value=mock_client):
        save_sync_log(entry)
        assert mock_client.table.called
        upsert_call = mock_client.table("sync_logs").upsert.call_args[0][0]
        assert "||SOURCES_DETAIL:" in upsert_call["error_message"]

    decoded = decode_sync_log(upsert_call)
    assert decoded["error_message"] == "data.gov.in: FAILED - 500 server error"
    assert decoded["sources_detail"]["data.gov.in"]["status"] == "FAILED"
    assert decoded["sources_detail"]["data.gov.in"]["error"] == "500 server error"


def test_sync_routes_filter_mixed_persisted_demo_and_real_logs():
    import asyncio
    import json
    from app.routers.sync import get_sync_logs, get_sync_status

    raw_demo_log = {
        "id": "persisted-demo-1",
        "source_name": "data.gov.in",
        "job_type": "scheduled_sync",
        "status": "success",
        "records_fetched": 100,
        "error_message": "||SOURCES_DETAIL:" + json.dumps({"_meta": {"is_demo": True}, "data.gov.in": {"status": "SUCCESS", "records_fetched": 100}}),
        "started_at": "2026-09-12T05:00:00Z",
        "completed_at": "2026-09-12T05:00:01Z",
    }
    raw_real_log = {
        "id": "persisted-real-1",
        "source_name": "data.gov.in",
        "job_type": "scheduled_sync",
        "status": "failed",
        "records_fetched": 0,
        "error_message": "data.gov.in: FAILED - 403 Forbidden||SOURCES_DETAIL:" + json.dumps({"_meta": {"is_demo": False}, "data.gov.in": {"status": "FAILED", "error": "403 Forbidden", "records_fetched": 0}}),
        "started_at": "2026-09-12T05:01:00Z",
        "completed_at": "2026-09-12T05:01:02Z",
    }

    with patch("app.ingestion.datagov_connector.DataGovConnector.has_api_key", True), \
         patch("app.repositories.supabase_repository.list_sync_logs", return_value=[raw_real_log, raw_demo_log]), \
         patch("app.db._cache", {"sync_logs": [raw_real_log, raw_demo_log]}):
        logs = asyncio.run(get_sync_logs(limit=20, offset=0, is_demo=False))
        status = asyncio.run(get_sync_status(is_demo=False))

    assert len(logs) == 1
    assert logs[0]["id"] == "persisted-real-1"
    assert status["status"] == "failed"
    assert status["sources"]["data.gov.in"]["status"] == "FAILED"
    assert status["last_sync"]["id"] == "persisted-real-1"


def test_list_sync_logs_overfetches_and_filters_demo_logs_before_limit():
    import json
    from app.repositories.supabase_repository import list_sync_logs
    demo_rows = [
        {
            "id": f"demo-{i}",
            "source_name": "data.gov.in",
            "job_type": "scheduled_sync",
            "status": "success",
            "records_fetched": 100,
            "error_message": "||SOURCES_DETAIL:" + json.dumps({"_meta": {"is_demo": True}}),
            "started_at": f"2026-09-12T10:{i:02d}:00Z",
            "completed_at": f"2026-09-12T10:{i:02d}:01Z",
        }
        for i in range(12)
    ]
    real_rows = [
        {
            "id": "real-running-1",
            "source_name": "data.gov.in",
            "job_type": "scheduled_sync",
            "status": "running",
            "records_fetched": 0,
            "error_message": "||SOURCES_DETAIL:" + json.dumps({"_meta": {"is_demo": False}}),
            "started_at": "2026-09-12T09:59:00Z",
        },
        {
            "id": "real-success-2",
            "source_name": "data.gov.in",
            "job_type": "scheduled_sync",
            "status": "success",
            "records_fetched": 50,
            "error_message": "||SOURCES_DETAIL:" + json.dumps({"_meta": {"is_demo": False}}),
            "started_at": "2026-09-12T09:00:00Z",
            "completed_at": "2026-09-12T09:00:05Z",
        },
    ]
    all_rows = demo_rows + real_rows

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

    with patch("app.repositories.supabase_repository.get_client", return_value=mock_client):
        single_real = list_sync_logs(limit=1, is_demo=False)
        assert len(single_real) == 1
        assert single_real[0]["id"] == "real-running-1"
        assert single_real[0]["is_demo"] is False

        all_real = list_sync_logs(limit=10, is_demo=False)
        assert len(all_real) == 2
        assert [r["id"] for r in all_real] == ["real-running-1", "real-success-2"]

        top_demo = list_sync_logs(limit=5, is_demo=True)
        assert len(top_demo) == 5
        assert all(r["is_demo"] is True for r in top_demo)


def test_list_sync_logs_paginates_past_500_demo_logs_for_older_real_log():
    import json
    from app.repositories.supabase_repository import list_sync_logs
    demo_rows = [
        {
            "id": f"demo-{i}",
            "source_name": "data.gov.in",
            "job_type": "scheduled_sync",
            "status": "success",
            "records_fetched": 10,
            "error_message": "||SOURCES_DETAIL:" + json.dumps({"_meta": {"is_demo": True}}),
            "started_at": f"2026-09-12T10:{i // 60:02d}:{i % 60:02d}Z",
            "completed_at": f"2026-09-12T10:{i // 60:02d}:{i % 60:02d}Z",
        }
        for i in range(520)
    ]
    real_row = {
        "id": "real-older-active",
        "source_name": "data.gov.in",
        "job_type": "scheduled_sync",
        "status": "running",
        "records_fetched": 0,
        "error_message": "||SOURCES_DETAIL:" + json.dumps({"_meta": {"is_demo": False}}),
        "started_at": "2026-09-12T08:00:00Z",
    }
    all_rows = demo_rows + [real_row]

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

    with patch("app.repositories.supabase_repository.get_client", return_value=mock_client):
        logs = list_sync_logs(limit=1, is_demo=False)
        assert len(logs) == 1
        assert logs[0]["id"] == "real-older-active"
        assert logs[0]["status"] == "running"
        assert logs[0]["is_demo"] is False


def test_list_sync_logs_paginates_past_50000_demo_logs_for_older_real_log():
    from app.repositories.supabase_repository import list_sync_logs

    mock_client = MagicMock()
    mock_query = MagicMock()
    mock_client.table.return_value.select.return_value = mock_query
    mock_query.order.return_value = mock_query

    def mock_range(start, end):
        res = MagicMock()
        if start < 50000:
            count = min(end - start + 1, 50000 - start)
            res.data = [
                {
                    "id": f"demo-{start + i}",
                    "source_name": "data.gov.in",
                    "job_type": "scheduled_sync",
                    "status": "success",
                    "records_fetched": 10,
                    "error_message": '||SOURCES_DETAIL:{"_meta": {"is_demo": true}}',
                    "started_at": "2026-09-12T10:00:00Z",
                }
                for i in range(count)
            ]
        elif start == 50000:
            res.data = [
                {
                    "id": "real-older-than-50k",
                    "source_name": "data.gov.in",
                    "job_type": "scheduled_sync",
                    "status": "running",
                    "records_fetched": 0,
                    "error_message": '||SOURCES_DETAIL:{"_meta": {"is_demo": false}}',
                    "started_at": "2026-09-12T05:00:00Z",
                }
            ]
        else:
            res.data = []
        mock_query.execute.return_value = res
        return mock_query

    mock_query.range.side_effect = mock_range

    with patch("app.repositories.supabase_repository.get_client", return_value=mock_client):
        logs = list_sync_logs(limit=1, is_demo=False)
        assert len(logs) == 1
        assert logs[0]["id"] == "real-older-than-50k"
        assert logs[0]["status"] == "running"
        assert logs[0]["is_demo"] is False


def test_create_skill_forecast_authoritative_uuid_resolution_and_rejection():
    import uuid
    from unittest.mock import patch, MagicMock
    from app.repositories.supabase_repository import (
        create_skill_forecast,
        SupabaseRepositoryError,
        _is_valid_uuid,
    )
    from app.services.forecast_engine import persist_computed_forecasts

    canonical_skill_uuid = str(uuid.uuid4())
    fake_taxonomy = [
        {
            "id": canonical_skill_uuid,
            "name": "Machine Learning",
            "synonyms": ["ml", "deep learning"],
        }
    ]

    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table

    def mock_upsert(record, *args, **kwargs):
        res = MagicMock()
        res.data = [record]
        mock_table.execute.return_value = res
        return mock_table

    mock_table.upsert.side_effect = mock_upsert
    mock_table.execute.return_value = MagicMock(data=[])

    with patch("app.repositories.supabase_repository.get_client", return_value=mock_client), \
         patch("app.repositories.supabase_repository.list_skills", return_value=fake_taxonomy), \
         patch("app.repositories.supabase_repository.list_skill_forecasts", return_value=[]):

        resolved_by_name = create_skill_forecast({
            "id": "sf-f7b4caca",
            "skill_id": "Machine Learning",
            "period": "6m",
            "current_demand": "high",
            "future_demand": "very_high",
            "trend": "rising",
            "confidence": 85,
        })
        assert _is_valid_uuid(resolved_by_name["id"])
        assert resolved_by_name["id"] != "sf-f7b4caca"
        assert resolved_by_name["skill_id"] == canonical_skill_uuid

        resolved_by_synonym = create_skill_forecast({
            "skill_id": "deep learning",
            "period": "12m",
            "current_demand": "high",
            "future_demand": "very_high",
            "trend": "rising",
            "confidence": 90,
        })
        assert _is_valid_uuid(resolved_by_synonym["id"])
        assert resolved_by_synonym["skill_id"] == canonical_skill_uuid

        already_uuid = str(uuid.uuid4())
        direct_uuid = create_skill_forecast({
            "skill_id": already_uuid,
            "period": "24m",
            "current_demand": "medium",
            "future_demand": "high",
            "trend": "rising",
            "confidence": 75,
        })
        assert _is_valid_uuid(direct_uuid["id"])
        assert direct_uuid["skill_id"] == already_uuid

        import pytest
        with pytest.raises(SupabaseRepositoryError) as exc_info:
            create_skill_forecast({
                "skill_id": "unresolvable-skill-xyz-9999",
                "period": "6m",
                "current_demand": "low",
                "future_demand": "low",
                "trend": "stable",
                "confidence": 50,
            })
        assert "unresolved non-UUID skill_id" in str(exc_info.value)

        batch_inputs = [
            {
                "skill_id": canonical_skill_uuid,
                "skill_name": "Machine Learning",
                "current_demand_score": 80.0,
                "projected_6m": 85.0,
                "projected_12m": 90.0,
                "projected_24m": 95.0,
                "trend": "rising",
                "confidence_score": 90,
            },
            {
                "skill_id": "unresolvable-nonexistent-skill-abc",
                "skill_name": "Ghost Skill",
                "current_demand_score": 20.0,
                "projected_6m": 20.0,
                "projected_12m": 20.0,
                "projected_24m": 20.0,
                "trend": "stable",
                "confidence_score": 50,
            }
        ]
        persisted = persist_computed_forecasts(batch_inputs)
        assert len(persisted) == 3
        for item in persisted:
            assert _is_valid_uuid(item["id"])
            assert item["skill_id"] == canonical_skill_uuid


def test_sync_status_per_source_isolation_prevents_aggregate_bleeding():
    import asyncio
    import json
    from unittest.mock import patch
    from app.routers.sync import get_sync_status

    aggregate_error = 'skill_forecasts: FAILED - Database persistence failed for skill forecast: {\'message\': \'invalid input syntax for type uuid: "sf-f7b4caca"\', \'code\': \'22P02\'}'
    sources_detail_meta = {
        "_meta": {"is_demo": False},
        "data.gov.in": {
            "status": "SUCCESS",
            "error": None,
            "records_fetched": 110,
            "records_added": 44,
            "records_updated": 5,
            "records_skipped": 61,
        },
        "adzuna": {
            "status": "SUCCESS",
            "error": None,
            "records_fetched": 25,
            "records_added": 0,
            "records_updated": 0,
            "records_skipped": 25,
        },
        "industry_signals": {
            "status": "NO_DATA",
            "error": None,
            "records_fetched": 0,
            "records_added": 0,
            "records_updated": 0,
            "records_skipped": 0,
        },
        "skill_forecasts": {
            "status": "FAILED",
            "error": aggregate_error,
            "records_fetched": 0,
            "records_added": 0,
            "records_updated": 0,
            "records_skipped": 0,
        },
    }

    raw_aggregate_log = {
        "id": "real-aggregate-log-1",
        "source_name": "all",
        "job_type": "scheduled_sync",
        "status": "partial",
        "records_fetched": 135,
        "records_added": 44,
        "records_updated": 5,
        "records_skipped": 86,
        "error_message": f"{aggregate_error}||SOURCES_DETAIL:{json.dumps(sources_detail_meta)}",
        "started_at": "2026-09-12T07:00:00Z",
        "completed_at": "2026-09-12T07:00:05Z",
    }

    with patch("app.ingestion.datagov_connector.DataGovConnector.has_api_key", True), \
         patch("app.ingestion.adzuna_connector.AdzunaConnector.has_credentials", True), \
         patch("app.repositories.supabase_repository.list_sync_logs", return_value=[raw_aggregate_log]), \
         patch("app.db._cache", {"sync_logs": [raw_aggregate_log]}):

        status_result = asyncio.run(get_sync_status(is_demo=False))

    sources = status_result["sources"]
    assert status_result["status"] == "failed"

    dg = sources["data.gov.in"]
    assert dg["status"] == "SUCCESS"
    assert dg["records_fetched"] == 110
    assert dg["records_added"] == 44
    assert dg["records_updated"] == 5
    assert dg["records_skipped"] == 61
    assert dg["error"] is None

    adz = sources["adzuna"]
    assert adz["status"] == "SUCCESS"
    assert adz["records_fetched"] == 25
    assert adz["records_added"] == 0
    assert adz["records_updated"] == 0
    assert adz["records_skipped"] == 25
    assert adz["error"] is None

    ind = sources["industry_signals"]
    assert ind["status"] == "NO_DATA"
    assert ind["records_fetched"] == 0
    assert ind["records_added"] == 0
    assert ind["records_updated"] == 0
    assert ind["records_skipped"] == 0
    assert ind["error"] is None

    sf = sources["skill_forecasts"]
    assert sf["status"] == "FAILED"
    assert sf["records_fetched"] == 0
    assert sf["records_added"] == 0
    assert sf["records_updated"] == 0
    assert sf["records_skipped"] == 0
    assert "invalid input syntax for type uuid" in sf["error"]


def test_sync_status_idle_source_does_not_copy_unrelated_aggregate_log():
    import asyncio
    from unittest.mock import patch
    from app.routers.sync import get_sync_status

    legacy_aggregate_log = {
        "id": "legacy-all-run",
        "source_name": "all",
        "job_type": "scheduled_sync",
        "status": "partial",
        "records_fetched": 135,
        "records_added": 44,
        "records_updated": 5,
        "records_skipped": 86,
        "error_message": "skill_forecasts: FAILED - Database persistence failed",
        "started_at": "2026-09-12T07:00:00Z",
        "completed_at": "2026-09-12T07:00:05Z",
    }

    with patch("app.ingestion.datagov_connector.DataGovConnector.has_api_key", True), \
         patch("app.ingestion.adzuna_connector.AdzunaConnector.has_credentials", True), \
         patch("app.repositories.supabase_repository.list_sync_logs", return_value=[legacy_aggregate_log]), \
         patch("app.db._cache", {"sync_logs": [legacy_aggregate_log]}):

        status_result = asyncio.run(get_sync_status(is_demo=False))

    sources = status_result["sources"]
    for s_name in ("data.gov.in", "adzuna", "industry_signals", "skill_forecasts"):
        assert sources[s_name]["status"] == "IDLE"
        assert sources[s_name]["records_fetched"] == 0
        assert sources[s_name]["records_added"] == 0
        assert sources[s_name]["records_updated"] == 0
        assert sources[s_name]["records_skipped"] == 0
        assert sources[s_name]["error"] is None


def test_industry_signals_real_mode_no_sample_feeds_ingested():
    from unittest.mock import patch
    from app.ingestion.sync_engine import SyncEngine

    with patch("app.ingestion.sync_engine.is_explicit_demo_mode", return_value=False), \
         patch("app.ingestion.industry_intelligence.IndustryIntelligenceIngestor.validate_and_normalize") as mock_val, \
         patch("app.db.save_industry_signal") as mock_save:

        engine = SyncEngine()
        res = engine.run_sync("industry_signals")

    assert mock_val.call_count == 0
    assert mock_save.call_count == 0
    assert res["sources_detail"]["industry_signals"]["status"] == "NO_DATA"
    assert res["sources_detail"]["industry_signals"]["records_fetched"] == 0
    assert res["sources_detail"]["industry_signals"]["records_added"] == 0
    assert res["sources_detail"]["industry_signals"]["records_updated"] == 0
    assert res["sources_detail"]["industry_signals"]["records_skipped"] == 0


def test_industry_signals_ingest_from_feeds_real_mode_rejects_synthetic():
    from app.ingestion.industry_intelligence import industry_ingestor, SAMPLE_VERIFIED_FEEDS

    res_empty = industry_ingestor.ingest_from_feeds(is_demo=False)
    assert res_empty["status"] == "NO_DATA"
    assert res_empty["records_fetched"] == 0
    assert res_empty["records_added"] == 0

    res_synthetic = industry_ingestor.ingest_from_feeds(SAMPLE_VERIFIED_FEEDS, is_demo=False)
    assert res_synthetic["records_added"] == 0
    assert res_synthetic["records_rejected"] == len(SAMPLE_VERIFIED_FEEDS)


def test_adzuna_what_or_parameter_conversion():
    from unittest.mock import patch, MagicMock
    from app.ingestion.adzuna_connector import AdzunaConnector

    captured_params = {}

    def mock_get(url, params=None, **kwargs):
        nonlocal captured_params
        captured_params = params or {}
        return MagicMock(status_code=200, json=lambda: {"results": []})

    connector = AdzunaConnector(app_id="test_id", app_key="test_key")
    with patch("httpx.get", side_effect=mock_get):
        res = connector.fetch_raw(
            what="engineer OR technician OR developer OR analyst",
            is_demo=False,
        )

    assert res == []
    assert connector.last_status == "NO_DATA"
    assert connector.last_error is None
    assert "what_or" in captured_params
    assert captured_params["what_or"] == "engineer technician developer analyst"
    assert "what" not in captured_params


def test_adzuna_live_empty_results_returns_no_data():
    from unittest.mock import patch, MagicMock
    from app.ingestion.adzuna_connector import AdzunaConnector

    connector = AdzunaConnector(app_id="test_id", app_key="test_key")
    with patch("httpx.get", return_value=MagicMock(status_code=200, json=lambda: {"results": []})):
        res = connector.fetch_raw(is_demo=False)

    assert res == []
    assert connector.last_status == "NO_DATA"
    assert connector.last_error is None


def test_admin_industry_ingestion_real_mode_no_feeds(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.config import settings

    monkeypatch.setenv("SKILLSETU_DATA_MODE", "real")
    monkeypatch.setattr(settings, "admin_api_key", "test-admin-secret-999")

    with TestClient(app) as client:
        res = client.post(
            "/api/admin/industry/ingest",
            headers={"X-Admin-Key": "test-admin-secret-999"},
            json=None,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        summary = data["summary"]
        assert summary["status"] == "NO_DATA"
        assert summary["records_fetched"] == 0
        assert summary["records_added"] == 0


def test_ingest_from_feeds_no_args_real_mode_rejects_sample(monkeypatch):
    from app.ingestion.industry_intelligence import industry_ingestor

    monkeypatch.setenv("SKILLSETU_DATA_MODE", "real")
    res = industry_ingestor.ingest_from_feeds()
    assert res["status"] == "NO_DATA"
    assert res["records_fetched"] == 0
    assert res["records_added"] == 0


def test_scheduler_sync_logs_include_is_demo_field(monkeypatch):
    import asyncio
    from app.ingestion.scheduler import IngestionScheduler

    saved_logs = []

    def mock_save_log(log_entry):
        saved_logs.append(dict(log_entry))

    monkeypatch.setattr("app.db.save_sync_log", mock_save_log)

    sched = IngestionScheduler()

    monkeypatch.setenv("SKILLSETU_DATA_MODE", "real")
    asyncio.run(sched.execute_sync(source="industry_signals"))
    assert len(saved_logs) >= 1
    assert saved_logs[-1]["source_name"] == "industry_signals"
    assert saved_logs[-1]["is_demo"] is False

    monkeypatch.setenv("SKILLSETU_DATA_MODE", "demo")
    asyncio.run(sched.execute_sync(source="industry_signals"))
    assert len(saved_logs) >= 2
    assert saved_logs[-1]["is_demo"] is True


def test_sync_log_persistence_statuses_cache_and_supabase():
    from app.db import save_sync_log, decode_sync_log, _cache

    _cache["sync_logs"] = []
    valid_cases = ["NO_DATA", "no_data", "success", "SUCCESS", "failed", "FAILED", "partial", "PARTIAL", "running", "RUNNING"]
    for idx, st in enumerate(valid_cases):
        entry = {
            "id": f"test-status-{idx}",
            "source_name": "industry_signals",
            "job_type": "scheduled_sync",
            "status": st,
            "records_fetched": 0,
            "records_added": 0,
            "records_updated": 0,
            "records_skipped": 0,
            "error_message": None,
            "started_at": "2026-09-12T04:00:00Z",
            "completed_at": "2026-09-12T04:00:01Z",
            "duration_ms": 100,
        }
        res = save_sync_log(entry)
        assert res is True
        assert any(l["id"] == f"test-status-{idx}" for l in _cache.get("sync_logs", []))

    mock_client = MagicMock()
    with patch("app.db.get_supabase_client", return_value=mock_client):
        entry = {
            "id": "test-supa-no-data",
            "source_name": "industry_signals",
            "job_type": "scheduled_sync",
            "status": "NO_DATA",
            "records_fetched": 0,
            "records_added": 0,
            "records_updated": 0,
            "records_skipped": 0,
            "error_message": None,
            "started_at": "2026-09-12T04:00:00Z",
            "completed_at": "2026-09-12T04:00:01Z",
            "duration_ms": 50,
            "sources_detail": {
                "industry_signals": {
                    "status": "NO_DATA",
                    "error": None,
                    "records_fetched": 0,
                    "records_added": 0,
                    "records_updated": 0,
                    "records_skipped": 0,
                }
            },
        }
        res = save_sync_log(entry)
        assert res is True
        assert mock_client.table.called
        upsert_call = mock_client.table("sync_logs").upsert.call_args[0][0]
        assert upsert_call["status"] == "NO_DATA"
        decoded = decode_sync_log(upsert_call)
        assert decoded["sources_detail"]["industry_signals"]["status"] == "NO_DATA"


def test_sync_log_persistence_rejects_arbitrary_invalid_status():
    from app.db import save_sync_log, _cache

    _cache["sync_logs"] = []
    invalid_cases = ["INVALID_STATUS", "UNKNOWN", "NOT_CONFIGURED", "IDLE", "", None]
    for idx, inv_st in enumerate(invalid_cases):
        entry = {
            "id": f"test-invalid-{idx}",
            "source_name": "industry_signals",
            "job_type": "scheduled_sync",
            "status": inv_st,
        }
        res = save_sync_log(entry)
        assert res is False
        assert not any(l.get("id") == f"test-invalid-{idx}" for l in _cache.get("sync_logs", []))


def test_scheduler_industry_signals_persists_no_data_when_zero_fetched(monkeypatch):
    import asyncio
    from app.ingestion.scheduler import IngestionScheduler
    from app.db import _cache

    _cache["sync_logs"] = []
    monkeypatch.setenv("SKILLSETU_DATA_MODE", "real")
    sched = IngestionScheduler()
    res = asyncio.run(sched.execute_sync(source="industry_signals"))
    assert res["status"] == "no_data"
    cached = _cache.get("sync_logs", [])
    assert len(cached) >= 1
    last_log = cached[-1]
    assert last_log["source_name"] == "industry_signals"
    assert last_log["status"] == "NO_DATA"
    assert last_log["records_fetched"] == 0
    assert last_log["sources_detail"]["industry_signals"]["status"] == "NO_DATA"


def test_scheduler_skill_forecasts_persists_no_data_when_zero_computed(monkeypatch):
    import asyncio
    from app.ingestion.scheduler import IngestionScheduler
    from app.db import _cache

    _cache["sync_logs"] = []
    monkeypatch.setattr("app.services.forecast_engine.persist_computed_forecasts", lambda: [])
    sched = IngestionScheduler()
    res = asyncio.run(sched.execute_sync(source="skill_forecasts"))
    assert res["status"] == "no_data"
    cached = _cache.get("sync_logs", [])
    assert len(cached) >= 1
    last_log = cached[-1]
    assert last_log["source_name"] == "skill_forecasts"
    assert last_log["status"] == "NO_DATA"
    assert last_log["records_fetched"] == 0
    assert last_log["sources_detail"]["skill_forecasts"]["status"] == "NO_DATA"


def test_sync_status_api_reflects_no_data_and_degraded_overall(monkeypatch):
    from starlette.testclient import TestClient
    from app.main import app
    from app.db import _cache, save_sync_log

    monkeypatch.setenv("SKILLSETU_DATA_MODE", "real")
    monkeypatch.setattr("app.ingestion.datagov_connector.DataGovConnector.has_api_key", True)
    monkeypatch.setattr("app.ingestion.adzuna_connector.AdzunaConnector.has_credentials", True)
    monkeypatch.setattr("app.routers.sync.is_supabase_connected", lambda: True)
    monkeypatch.setattr("app.repositories.supabase_repository.list_sync_logs", lambda **kwargs: [])

    _cache["sync_logs"] = []
    save_sync_log({
        "id": "log-dg-no-data",
        "source_name": "data.gov.in",
        "job_type": "scheduled_sync",
        "status": "NO_DATA",
        "records_fetched": 0,
        "records_added": 0,
        "records_updated": 0,
        "records_skipped": 0,
        "error_message": None,
        "started_at": "2026-09-12T04:00:00Z",
        "completed_at": "2026-09-12T04:00:01Z",
        "duration_ms": 100,
        "is_demo": False,
        "sources_detail": {
            "data.gov.in": {
                "status": "NO_DATA",
                "error": None,
                "records_fetched": 0,
                "records_added": 0,
                "records_updated": 0,
                "records_skipped": 0,
            }
        },
    })
    save_sync_log({
        "id": "log-ind-no-data",
        "source_name": "industry_signals",
        "job_type": "scheduled_sync",
        "status": "NO_DATA",
        "records_fetched": 0,
        "records_added": 0,
        "records_updated": 0,
        "records_skipped": 0,
        "error_message": None,
        "started_at": "2026-09-12T04:00:02Z",
        "completed_at": "2026-09-12T04:00:03Z",
        "duration_ms": 100,
        "is_demo": False,
        "sources_detail": {
            "industry_signals": {
                "status": "NO_DATA",
                "error": None,
                "records_fetched": 0,
                "records_added": 0,
                "records_updated": 0,
                "records_skipped": 0,
            }
        },
    })

    monkeypatch.setattr("app.config.settings.sync_on_startup", False)
    monkeypatch.setattr("app.config.settings.auto_sync_enabled", False)

    client = TestClient(app)
    res = client.get("/api/sync/status")
    assert res.status_code == 200
    data = res.json()
    assert data["sources"]["data.gov.in"]["status"] == "NO_DATA"
    assert data["sources"]["industry_signals"]["status"] == "NO_DATA"
    assert data["status"] == "degraded"


def test_sync_status_api_demo_log_isolation_from_real_status(monkeypatch):
    from starlette.testclient import TestClient
    from app.main import app
    from app.db import _cache, save_sync_log

    monkeypatch.setenv("SKILLSETU_DATA_MODE", "real")
    monkeypatch.setattr("app.ingestion.datagov_connector.DataGovConnector.has_api_key", True)
    monkeypatch.setattr("app.repositories.supabase_repository.list_sync_logs", lambda **kwargs: [])

    _cache["sync_logs"] = []
    save_sync_log({
        "id": "demo-log-success",
        "source_name": "data.gov.in",
        "job_type": "scheduled_sync",
        "status": "success",
        "records_fetched": 50,
        "records_added": 50,
        "records_updated": 0,
        "records_skipped": 0,
        "error_message": None,
        "started_at": "2026-09-12T04:00:10Z",
        "completed_at": "2026-09-12T04:00:11Z",
        "duration_ms": 100,
        "is_demo": True,
        "sources_detail": {
            "data.gov.in": {
                "status": "SUCCESS",
                "error": None,
                "records_fetched": 50,
                "records_added": 50,
                "records_updated": 0,
                "records_skipped": 0,
            }
        },
    })
    save_sync_log({
        "id": "real-log-no-data",
        "source_name": "data.gov.in",
        "job_type": "scheduled_sync",
        "status": "NO_DATA",
        "records_fetched": 0,
        "records_added": 0,
        "records_updated": 0,
        "records_skipped": 0,
        "error_message": None,
        "started_at": "2026-09-12T04:00:00Z",
        "completed_at": "2026-09-12T04:00:01Z",
        "duration_ms": 100,
        "is_demo": False,
        "sources_detail": {
            "data.gov.in": {
                "status": "NO_DATA",
                "error": None,
                "records_fetched": 0,
                "records_added": 0,
                "records_updated": 0,
                "records_skipped": 0,
            }
        },
    })

    monkeypatch.setattr("app.config.settings.sync_on_startup", False)
    monkeypatch.setattr("app.config.settings.auto_sync_enabled", False)

    client = TestClient(app)
    res = client.get("/api/sync/status")
    assert res.status_code == 200
    data = res.json()
    assert data["sources"]["data.gov.in"]["status"] == "NO_DATA"


def test_sync_status_scheduler_telemetry_reconciled_from_authoritative_sync_log(monkeypatch):
    import asyncio
    from app.db import _cache
    from app.ingestion.scheduler import scheduler
    from app.routers.sync import get_sync_status

    auth_log = {
        "id": "real-authoritative-all-sync",
        "source_name": "all",
        "job_type": "automated_external_ingestion",
        "status": "success",
        "records_fetched": 320,
        "records_added": 165,
        "records_updated": 49,
        "records_skipped": 86,
        "error_message": None,
        "started_at": "2026-09-12T12:18:00.000000+00:00",
        "completed_at": "2026-09-12T12:19:04.651402+00:00",
        "duration_ms": 64651,
        "is_demo": False,
        "sources_detail": {
            "data.gov.in": {"status": "SUCCESS", "records_fetched": 130, "error": None},
            "adzuna": {"status": "SUCCESS", "records_fetched": 25, "error": None},
            "industry_signals": {"status": "NO_DATA", "records_fetched": 0, "error": None},
            "skill_forecasts": {"status": "SUCCESS", "records_fetched": 165, "error": None},
        },
    }

    _cache["sync_logs"] = [auth_log]
    scheduler._last_run_timestamp = None
    scheduler._last_attempted_run_timestamp = None
    scheduler._last_successful_run_timestamp = None
    scheduler._last_run_duration_ms = 0
    scheduler._last_error = None

    with patch("app.repositories.supabase_repository.list_sync_logs", return_value=[auth_log]):
        res = asyncio.run(get_sync_status(is_demo=False))

    sched_telemetry = res["scheduler"]
    assert sched_telemetry["last_run_timestamp"] == "2026-09-12T12:19:04.651402+00:00"
    assert sched_telemetry["last_attempted_run_timestamp"] == "2026-09-12T12:18:00.000000+00:00"
    assert sched_telemetry["last_successful_run_timestamp"] == "2026-09-12T12:19:04.651402+00:00"
    assert sched_telemetry["last_run_duration_ms"] == 64651
    assert sched_telemetry["last_error"] is None


def test_scheduler_execute_sync_legitimate_no_data_populates_successful_telemetry():
    import asyncio
    from unittest.mock import MagicMock
    from app.ingestion.scheduler import IngestionScheduler

    sched = IngestionScheduler()
    mock_engine = MagicMock()
    mock_engine.run_sync.return_value = {
        "status": "no_data",
        "source": "data.gov.in",
        "duration_ms": 150,
        "records_fetched": 0,
        "error_message": None,
        "completed_at": "2026-09-12T13:00:00Z",
    }
    sched.engine = mock_engine

    res = asyncio.run(sched.execute_sync(source="data.gov.in"))
    assert res["status"] == "no_data"

    status = sched.get_status()
    assert status["last_run_timestamp"] == "2026-09-12T13:00:00Z"
    assert status["last_successful_run_timestamp"] == "2026-09-12T13:00:00Z"
    assert status["last_error"] is None
    assert status["last_run_duration_ms"] == 150


def test_scheduler_execute_sync_partial_records_error_and_preserves_prior_success():
    import asyncio
    from unittest.mock import MagicMock
    from app.ingestion.scheduler import IngestionScheduler

    sched = IngestionScheduler()
    sched._last_successful_run_timestamp = "2026-09-12T11:00:00Z"

    mock_engine = MagicMock()
    mock_engine.run_sync.return_value = {
        "status": "partial",
        "source": "all",
        "duration_ms": 320,
        "error_message": "adzuna: FAILED - rate limited",
        "completed_at": "2026-09-12T12:00:00Z",
    }
    sched.engine = mock_engine

    res = asyncio.run(sched.execute_sync(source="all"))
    assert res["status"] == "partial"

    status = sched.get_status()
    assert status["last_run_timestamp"] == "2026-09-12T12:00:00Z"
    assert status["last_successful_run_timestamp"] == "2026-09-12T11:00:00Z"
    assert status["last_error"] == "adzuna: FAILED - rate limited"
    assert status["last_run_duration_ms"] == 320


def test_scheduler_execute_sync_all_populates_full_telemetry():
    import asyncio
    from unittest.mock import MagicMock
    from app.ingestion.scheduler import IngestionScheduler

    sched = IngestionScheduler()
    mock_engine = MagicMock()
    mock_engine.run_sync.return_value = {
        "status": "success",
        "source": "all",
        "duration_ms": 1200,
        "records_fetched": 320,
        "error_message": None,
        "completed_at": "2026-09-12T14:00:00Z",
    }
    sched.engine = mock_engine

    res = asyncio.run(sched.execute_sync(source="all"))
    assert res["status"] == "success"

    status = sched.get_status()
    assert status["last_run_timestamp"] == "2026-09-12T14:00:00Z"
    assert status["last_attempted_run_timestamp"] is not None
    assert status["last_successful_run_timestamp"] == "2026-09-12T14:00:00Z"
    assert status["last_run_duration_ms"] == 1200
    assert status["last_error"] is None


def test_scheduler_execute_sync_industry_signals_partial_preserves_error_and_prior_success():
    import asyncio
    from unittest.mock import MagicMock
    from app.ingestion.scheduler import IngestionScheduler

    sched = IngestionScheduler()
    sched._last_successful_run_timestamp = "2026-09-12T10:00:00Z"

    partial_ind_res = {
        "status": "partial",
        "last_run": "2026-09-12T12:30:00Z",
        "records_fetched": 5,
        "records_added": 3,
        "records_updated": 0,
        "records_duplicated": 0,
        "records_rejected": 2,
        "errors": ["Rejected item 'Invalid Feed Item': Malformed URL"],
    }

    mock_ingestor = MagicMock()
    mock_ingestor.ingest_from_feeds.return_value = partial_ind_res

    with patch("app.ingestion.industry_intelligence.industry_ingestor", mock_ingestor), \
         patch("app.db.save_sync_log") as mock_save_log:
        res = asyncio.run(sched.execute_sync(source="industry_signals"))

    assert res["status"] == "partial"
    assert "Malformed URL" in res["error_message"]

    status = sched.get_status()
    assert status["last_run_timestamp"] is not None
    assert status["last_successful_run_timestamp"] == "2026-09-12T10:00:00Z"
    assert "Malformed URL" in status["last_error"]

    mock_save_log.assert_called_once()
    saved_log = mock_save_log.call_args[0][0]
    assert saved_log["status"] == "partial"
    assert saved_log["sources_detail"]["industry_signals"]["status"] == "PARTIAL"
    assert "Malformed URL" in saved_log["error_message"]


def test_user_submitted_signal_provenance_not_verified_external_feed():
    from unittest.mock import MagicMock, patch
    from app.repositories.supabase_repository import create_industry_signal

    mock_client = MagicMock()
    mock_res = MagicMock()
    mock_res.data = [{
        "id": "test-sig-uuid-1",
        "title": "Custom User Submitted Signal",
        "source": "USER_SUBMITTED",
        "data_provenance": "USER_SUBMITTED",
        "is_demo": False,
    }]
    mock_client.table.return_value.upsert.return_value.execute.return_value = mock_res

    with patch("app.repositories.supabase_repository.get_client", return_value=mock_client), \
         patch("app.db._flush_real_table"):
        sig = create_industry_signal({
            "title": "Custom User Submitted Signal",
            "source": "USER_SUBMITTED",
        })
        assert sig["data_provenance"] == "USER_SUBMITTED"
        assert sig["data_provenance"] != "VERIFIED_EXTERNAL_FEED"


def test_industry_intelligence_pipeline_status_distinguishes_user_and_verified():
    from unittest.mock import patch
    from app.ingestion.industry_intelligence import IndustryIntelligenceIngestor

    sample_signals = [
        {
            "id": "sig-1",
            "title": "Verified Signal",
            "source": "EXTERNAL_API",
            "data_provenance": "VERIFIED_EXTERNAL_FEED",
            "is_demo": False,
            "validation_status": "APPROVED",
            "is_active": True,
        },
        {
            "id": "sig-2",
            "title": "User Signal",
            "source": "USER_SUBMITTED",
            "data_provenance": "USER_SUBMITTED",
            "is_demo": False,
            "validation_status": "PENDING",
            "is_active": True,
        },
        {
            "id": "sig-3",
            "title": "Demo Signal",
            "source": "DEMO",
            "source_label": "DEMO_SYNTHETIC",
            "data_provenance": "DEMO_SYNTHETIC",
            "is_demo": True,
            "validation_status": "APPROVED",
            "is_active": True,
        },
    ]

    ingestor = IndustryIntelligenceIngestor()
    with patch("app.repositories.supabase_repository.list_industry_signals", return_value=sample_signals):
        status = ingestor.get_ingestion_status()
        assert status["total_signals"] == 3
        assert status["verified_ingested_count"] == 1
        assert status["user_submitted_count"] == 1
        assert status["demo_synthetic_count"] == 1


