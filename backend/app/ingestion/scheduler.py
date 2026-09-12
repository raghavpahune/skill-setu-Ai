import asyncio
import datetime
import logging
import time
import uuid
from typing import Any

from app.config import settings
from app.core.data_mode import is_explicit_demo_mode
from app.db import get_demo
from app.ingestion.sync_engine import SyncEngine

logger = logging.getLogger("skillsetu.ingestion.scheduler")


class IngestionScheduler:

    def __init__(self, engine: SyncEngine | None = None):
        self.engine = engine or SyncEngine()
        self._lock: asyncio.Lock | None = None
        self._task: asyncio.Task | None = None
        self._stop_event: asyncio.Event | None = None
        self._is_sync_running = False
        self._last_run_timestamp: str | None = None
        self._last_attempted_run_timestamp: str | None = None
        self._last_successful_run_timestamp: str | None = None
        self._last_run_duration_ms: int = 0
        self._last_error: str | None = None

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def _get_stop_event(self) -> asyncio.Event:
        if self._stop_event is None:
            self._stop_event = asyncio.Event()
        return self._stop_event

    @property
    def is_active(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def is_sync_running(self) -> bool:
        return self._is_sync_running

    def start(self):
        if not settings.auto_sync_enabled:
            logger.info("Auto-sync is disabled via configuration (AUTO_SYNC_ENABLED=False).")
            return

        if self.is_active:
            logger.warning("IngestionScheduler is already running.")
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            self._stop_event = asyncio.Event()
            self._lock = asyncio.Lock()
            self._task = loop.create_task(self._worker_loop(), name="SkillSetu-SyncScheduler")
            logger.info(
                "IngestionScheduler started (interval=%d minutes, sync_on_startup=%s).",
                settings.effective_refresh_interval_minutes,
                settings.sync_on_startup,
            )
        else:
            logger.info("No active event loop found during scheduler.start(); skipping task creation.")

    async def stop(self):
        if not self.is_active:
            return

        logger.info("Stopping IngestionScheduler...")
        stop_event = self._get_stop_event()
        stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("IngestionScheduler stopped.")

    def _check_active_distributed_sync(self, lease_seconds: int = 900) -> bool:
        try:
            if is_explicit_demo_mode():
                logs = [l for l in get_demo("sync_logs") if l.get("is_demo") is True]
            else:
                from app.repositories.supabase_repository import list_sync_logs
                logs = list_sync_logs(limit=10, is_demo=False)
                logs = [l for l in logs if not l.get("is_demo")]
            now_dt = datetime.datetime.now(datetime.timezone.utc)
            for log in logs:
                if log.get("status") == "running":
                    started_str = log.get("started_at")
                    if started_str:
                        started_dt = datetime.datetime.fromisoformat(started_str)
                        if (now_dt - started_dt).total_seconds() < lease_seconds:
                            return True
        except Exception as exc:
            logger.warning("Error checking active distributed sync: %s", exc)
            return False
        return False

    async def execute_sync(self, source: str = "data.gov.in") -> dict[str, Any]:
        lock = self._get_lock()
        if lock.locked() or self._is_sync_running:
            logger.warning("Synchronization requested while another sync is actively running. Skipping.")
            return {
                "status": "skipped",
                "message": "Synchronization is already in progress. Overlapping run prevented.",
            }

        async with lock:
            if self._is_sync_running:
                logger.warning("Synchronization requested while another sync is actively running. Skipping.")
                return {
                    "status": "skipped",
                    "message": "Synchronization is already in progress. Overlapping run prevented.",
                }

            loop = asyncio.get_running_loop()
            is_distributed_running = await loop.run_in_executor(None, self._check_active_distributed_sync)
            if is_distributed_running:
                logger.warning("Synchronization requested while another sync is actively running. Skipping.")
                return {
                    "status": "skipped",
                    "message": "Synchronization is already in progress. Overlapping run prevented.",
                }

            self._is_sync_running = True
            attempt_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
            start_perf = time.perf_counter()
            self._last_attempted_run_timestamp = attempt_time
            self._last_run_timestamp = attempt_time
            try:
                loop = asyncio.get_running_loop()

                if source in ("industry_signals", "industry"):
                    from app.ingestion.industry_intelligence import industry_ingestor
                    from app.db import save_sync_log
                    ind_res = await loop.run_in_executor(
                        None,
                        lambda: industry_ingestor.ingest_from_feeds(is_demo=is_explicit_demo_mode()),
                    )
                    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    fetched_cnt = ind_res.get("records_fetched", ind_res.get("fetched", 0))
                    added_cnt = ind_res.get("records_added", ind_res.get("added", 0))
                    updated_cnt = ind_res.get("records_updated", ind_res.get("updated", 0))
                    skipped_cnt = ind_res.get("records_duplicated", ind_res.get("skipped", 0))
                    ind_status_raw = (ind_res.get("status") or ("success" if fetched_cnt > 0 else "NO_DATA")).lower()
                    errors_list = ind_res.get("errors", [])
                    ind_err = "; ".join(errors_list) if errors_list else ind_res.get("error_message")
                    self._last_run_timestamp = now_str
                    self._last_run_duration_ms = int((time.perf_counter() - start_perf) * 1000)
                    if ind_status_raw in ("success", "no_data"):
                        self._last_successful_run_timestamp = now_str
                        self._last_error = None
                        persisted_status = "success" if fetched_cnt > 0 else "NO_DATA"
                        detail_status = "SUCCESS" if fetched_cnt > 0 else "NO_DATA"
                        return_status = "success" if fetched_cnt > 0 else "no_data"
                    elif ind_status_raw == "partial":
                        self._last_error = ind_err
                        persisted_status = "partial"
                        detail_status = "PARTIAL"
                        return_status = "partial"
                    else:
                        self._last_error = ind_err or "Industry sync run failed"
                        persisted_status = "failed"
                        detail_status = "FAILED"
                        return_status = "failed"

                    save_sync_log({
                        "id": str(uuid.uuid4()),
                        "source_name": source,
                        "job_type": "scheduled_sync",
                        "status": persisted_status,
                        "records_fetched": fetched_cnt,
                        "records_added": added_cnt,
                        "records_updated": updated_cnt,
                        "records_skipped": skipped_cnt,
                        "error_message": ind_err,
                        "started_at": attempt_time,
                        "completed_at": now_str,
                        "duration_ms": self._last_run_duration_ms,
                        "is_demo": is_explicit_demo_mode(),
                        "sources_detail": {
                            "industry_signals": {
                                "status": detail_status,
                                "error": ind_err,
                                "records_fetched": fetched_cnt,
                                "records_added": added_cnt,
                                "records_updated": updated_cnt,
                                "records_skipped": skipped_cnt,
                            }
                        },
                    })
                    return {
                        "status": return_status,
                        "source": source,
                        "industry_sync": ind_res,
                        "duration_ms": self._last_run_duration_ms,
                        "error_message": ind_err,
                    }

                if source in ("skill_forecasts", "forecasts", "forecast"):
                    from app.services.forecast_engine import persist_computed_forecasts
                    from app.db import save_sync_log
                    fc_res = await loop.run_in_executor(None, persist_computed_forecasts)
                    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    fc_cnt = len(fc_res)
                    self._last_run_timestamp = now_str
                    self._last_successful_run_timestamp = now_str
                    self._last_error = None
                    self._last_run_duration_ms = int((time.perf_counter() - start_perf) * 1000)
                    save_sync_log({
                        "id": str(uuid.uuid4()),
                        "source_name": source,
                        "job_type": "scheduled_sync",
                        "status": "success" if fc_cnt > 0 else "NO_DATA",
                        "records_fetched": fc_cnt,
                        "records_added": fc_cnt,
                        "records_updated": 0,
                        "records_skipped": 0,
                        "error_message": None,
                        "started_at": attempt_time,
                        "completed_at": now_str,
                        "duration_ms": self._last_run_duration_ms,
                        "is_demo": is_explicit_demo_mode(),
                        "sources_detail": {
                            "skill_forecasts": {
                                "status": "SUCCESS" if fc_cnt > 0 else "NO_DATA",
                                "error": None,
                                "records_fetched": fc_cnt,
                                "records_added": fc_cnt,
                                "records_updated": 0,
                                "records_skipped": 0,
                            }
                        },
                    })
                    return {"status": "success" if fc_cnt > 0 else "no_data", "source": source, "forecasts_persisted": len(fc_res), "duration_ms": self._last_run_duration_ms}

                result = await loop.run_in_executor(None, self.engine.run_sync, source)

                if "source" not in result:
                    result["source"] = source

                completed_ts = result.get("completed_at") or datetime.datetime.now(datetime.timezone.utc).isoformat()
                self._last_run_timestamp = completed_ts
                self._last_run_duration_ms = int(result.get("duration_ms") or ((time.perf_counter() - start_perf) * 1000))
                res_status = (result.get("status") or "").lower()
                if res_status in ("success", "no_data"):
                    self._last_successful_run_timestamp = completed_ts
                    self._last_error = None
                elif res_status == "partial":
                    err_text = result.get("error_message")
                    self._last_error = err_text
                else:
                    self._last_error = result.get("error_message") or "Sync run failed"
                return result
            except Exception as exc:
                now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
                self._last_run_timestamp = now_str
                self._last_run_duration_ms = int((time.perf_counter() - start_perf) * 1000)
                self._last_error = str(exc)
                logger.exception("Error executing sync: %s", exc)
                return {
                    "status": "failed",
                    "source": source,
                    "error_message": str(exc),
                    "started_at": attempt_time,
                    "completed_at": now_str,
                }
            finally:
                self._is_sync_running = False

    async def _worker_loop(self):
        try:
            loop = asyncio.get_running_loop()
            should_catchup = await loop.run_in_executor(None, self._should_catchup_sync)
            if settings.sync_on_startup or should_catchup:
                logger.info("Performing initial/catch-up data synchronization on startup...")
                await self.execute_sync(source=settings.sync_sources or "all")

            interval_seconds = max(settings.effective_refresh_interval_minutes * 60, 60)
            stop_event = self._get_stop_event()

            while not stop_event.is_set():
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
                    break
                except asyncio.TimeoutError:
                    logger.info("Scheduled sync interval elapsed. Triggering automated ingestion...")
                    try:
                        await self.execute_sync(source=settings.sync_sources or "all")
                    except Exception as exc:
                        logger.exception("Error during scheduled automated ingestion: %s", exc)

        except asyncio.CancelledError:
            logger.info("Scheduler worker loop cancelled.")
        except Exception as exc:
            logger.exception("Unexpected error in scheduler worker loop: %s", exc)

    def _fetch_persisted_telemetry_logs(self) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        if is_explicit_demo_mode():
            raw_logs = list(get_demo("sync_logs"))
            from app.db import decode_sync_log
            logs = [decode_sync_log(l) for l in raw_logs if l.get("is_demo") is True]
        else:
            try:
                from app.repositories.supabase_repository import list_sync_logs
                raw_logs = list_sync_logs(limit=20, is_demo=False)
            except Exception as exc:
                logger.warning("Error fetching sync logs for telemetry: %s", exc)
                raw_logs = []
            if not raw_logs:
                from app.db import _cache
                raw_logs = list(_cache.get("sync_logs", []))
            from app.db import decode_sync_log
            decoded_logs = [decode_sync_log(l) for l in raw_logs]
            logs = [l for l in decoded_logs if not l.get("is_demo")]

        if not logs:
            return None, None

        logs.sort(key=lambda x: x.get("started_at", ""), reverse=True)
        latest_log = logs[0]
        latest_success_log = next(
            (l for l in logs if (l.get("status") or "").lower() in ("success", "no_data")),
            None,
        )
        return latest_log, latest_success_log

    def _reconcile_telemetry(
        self,
        latest_log: dict[str, Any] | None,
        latest_success_log: dict[str, Any] | None,
    ) -> None:
        if latest_log:
            log_run_ts = latest_log.get("completed_at") or latest_log.get("started_at")
            if log_run_ts and (self._last_run_timestamp is None or log_run_ts >= self._last_run_timestamp):
                self._last_run_timestamp = log_run_ts
                if not self._is_sync_running:
                    self._last_attempted_run_timestamp = latest_log.get("started_at")
                self._last_run_duration_ms = int(latest_log.get("duration_ms") or 0)
                st = (latest_log.get("status") or "").lower()
                if st in ("success", "no_data"):
                    self._last_error = None
                elif st in ("failed", "partial"):
                    self._last_error = latest_log.get("error_message") or ("Sync run failed" if st == "failed" else None)
        if latest_success_log:
            success_ts = latest_success_log.get("completed_at") or latest_success_log.get("started_at")
            if success_ts and (self._last_successful_run_timestamp is None or success_ts >= self._last_successful_run_timestamp):
                self._last_successful_run_timestamp = success_ts

    def _should_catchup_sync(self) -> bool:
        latest_log, latest_success_log = self._fetch_persisted_telemetry_logs()
        if not latest_log:
            return True

        if self._last_run_timestamp is None:
            self._reconcile_telemetry(latest_log, latest_success_log)

        started_str = latest_log.get("started_at")
        if not started_str:
            return True

        try:
            last_dt = datetime.datetime.fromisoformat(started_str)
            now_dt = datetime.datetime.now(datetime.timezone.utc)
            minutes_elapsed = (now_dt - last_dt).total_seconds() / 60
            return minutes_elapsed >= settings.effective_refresh_interval_minutes
        except Exception as exc:
            logger.warning("Error parsing timestamp for catchup check: %s", exc)
            return True

    def get_status(
        self,
        latest_log: dict[str, Any] | None = None,
        latest_success_log: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if latest_log is None and self._last_run_timestamp is None:
            latest_log, latest_success_log = self._fetch_persisted_telemetry_logs()

        last_run = self._last_run_timestamp
        last_attempt = self._last_attempted_run_timestamp
        last_success = self._last_successful_run_timestamp
        duration_ms = self._last_run_duration_ms
        last_error = self._last_error

        if latest_log:
            log_run_ts = latest_log.get("completed_at") or latest_log.get("started_at")
            if log_run_ts and (last_run is None or log_run_ts >= last_run):
                last_run = log_run_ts
                if not self._is_sync_running:
                    last_attempt = latest_log.get("started_at")
                duration_ms = int(latest_log.get("duration_ms") or 0)
                st = (latest_log.get("status") or "").lower()
                if st in ("success", "no_data"):
                    last_error = None
                elif st in ("failed", "partial"):
                    last_error = latest_log.get("error_message") or ("Sync run failed" if st == "failed" else None)

        if latest_success_log:
            log_success_ts = latest_success_log.get("completed_at") or latest_success_log.get("started_at")
            if log_success_ts and (last_success is None or log_success_ts >= last_success):
                last_success = log_success_ts

        return {
            "auto_sync_enabled": settings.auto_sync_enabled,
            "scheduler_active": self.is_active,
            "is_sync_running": self._is_sync_running,
            "interval_hours": settings.sync_interval_hours,
            "refresh_interval_minutes": settings.effective_refresh_interval_minutes,
            "interval_minutes": settings.effective_refresh_interval_minutes,
            "last_run_timestamp": last_run,
            "last_attempted_run_timestamp": last_attempt,
            "last_successful_run_timestamp": last_success,
            "last_run_duration_ms": duration_ms,
            "last_error": last_error,
        }


scheduler = IngestionScheduler()
