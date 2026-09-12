"""Test suite for Task 2 Step 4D: IngestionScheduler, Overlap Protection, and Scheduled Ingestion."""
import asyncio
import sys
import time
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from starlette.testclient import TestClient
from app.config import settings
from app.db import load_demo_data, get_demo
from app.ingestion.scheduler import IngestionScheduler, scheduler
from app.main import app

import pytest
from copy import deepcopy
from app.db import _cache

@pytest.fixture(scope="module", autouse=True)
def isolate_scheduler_step4d_cache():
    import os
    snapshot = deepcopy(_cache)
    old_mode = os.environ.get("SKILLSETU_DATA_MODE")
    os.environ["SKILLSETU_DATA_MODE"] = "demo"
    yield
    _cache.clear()
    _cache.update(snapshot)
    if old_mode is None:
        os.environ.pop("SKILLSETU_DATA_MODE", None)
    else:
        os.environ["SKILLSETU_DATA_MODE"] = old_mode

load_demo_data()


def test_scheduler_configuration():
    print("Testing Scheduler Configuration...")
    assert hasattr(settings, "auto_sync_enabled")
    assert isinstance(settings.auto_sync_enabled, bool)
    assert hasattr(settings, "sync_interval_hours")
    assert isinstance(settings.sync_interval_hours, int)
    assert hasattr(settings, "sync_on_startup")
    assert isinstance(settings.sync_on_startup, bool)
    print(f"  OK: Configuration loaded (enabled={settings.auto_sync_enabled}, interval={settings.sync_interval_hours}h).")


def test_scheduler_lifecycle():
    print("Testing IngestionScheduler Lifecycle...")

    async def _test():
        test_sched = IngestionScheduler()

        # Initial state
        assert not test_sched.is_active
        assert not test_sched.is_sync_running

        # Start inside running loop
        test_sched.start()
        assert test_sched.is_active, "Scheduler should be active after start()"

        # Status
        status = test_sched.get_status()
        assert status["scheduler_active"] is True
        assert "interval_hours" in status

        # Stop gracefully
        await test_sched.stop()
        assert not test_sched.is_active, "Scheduler should be inactive after stop()"

    asyncio.run(_test())
    print("  OK: Scheduler started and stopped gracefully.")


def test_overlap_protection():
    print("Testing Overlap / Concurrency Protection...")
    test_sched = IngestionScheduler()

    async def run_concurrent_tests():
        # Acquire the lock manually to simulate an active long-running sync
        async with test_sched._get_lock():
            test_sched._is_sync_running = True
            # Attempt to run another sync concurrently while lock is held
            res = await test_sched.execute_sync(source="data.gov.in")
            assert res.get("status") == "skipped"
            assert "already in progress" in res.get("message", "")
            test_sched._is_sync_running = False

    asyncio.run(run_concurrent_tests())
    print("  OK: Overlapping synchronization correctly blocked and skipped.")


def test_scheduler_execution_and_audit():
    print("Testing Scheduler Execution & Audit Logs...")
    test_sched = IngestionScheduler()

    # Execute sync through scheduler
    res = asyncio.run(test_sched.execute_sync(source="data.gov.in"))
    assert res.get("status") in ("success", "skipped")

    # Verify sync_logs has entries
    logs = list(get_demo("sync_logs"))
    assert len(logs) > 0
    latest = logs[-1]
    assert "status" in latest
    assert "duration_ms" in latest
    print(f"  OK: Sync completed via scheduler with status '{latest['status']}' in {latest['duration_ms']} ms.")


def test_api_lifespan_and_status():
    print("Testing API Lifespan & /api/sync/status endpoint...")
    with TestClient(app) as client:
        # Check /api/sync/status endpoint
        res = client.get("/api/sync/status")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert "scheduler" in data
        assert data["scheduler"]["auto_sync_enabled"] is True

        # Check /api/sync/trigger
        trigger_res = client.post("/api/sync/trigger?source=data.gov.in")
        assert trigger_res.status_code == 200
        trig_data = trigger_res.json()
        assert trig_data["status"] in ("success", "skipped")

        # Check non-blocking API access
        t0 = time.perf_counter()
        schemes_res = client.get("/api/schemes?limit=5")
        opps_res = client.get("/api/opportunities?limit=5")
        elapsed = time.perf_counter() - t0

        assert schemes_res.status_code == 200
        assert opps_res.status_code == 200
        assert elapsed < 1.0, f"API calls should be non-blocking, took {elapsed}s"
        print(f"  OK: API status healthy, trigger working, non-blocking requests served in {elapsed:.3f}s.")


def test_backward_compatibility():
    print("Testing Backward Compatibility...")
    with TestClient(app) as client:
        assert client.get("/api/jobs").status_code == 200
        assert client.get("/api/skills").status_code == 200
        assert client.get("/api/health").status_code == 200
    print("  OK: Core APIs intact.")


if __name__ == "__main__":
    test_scheduler_configuration()
    test_scheduler_lifecycle()
    test_overlap_protection()
    test_scheduler_execution_and_audit()
    test_api_lifespan_and_status()
    test_backward_compatibility()
    print("\nALL STEP 4D SCHEDULER TESTS PASSED SUCCESSFULLY!")
