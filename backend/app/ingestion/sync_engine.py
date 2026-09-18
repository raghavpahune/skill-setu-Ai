"""Synchronization Engine for SkillSetu.

Coordinates data ingestion from Tier-A external connectors:
1. data.gov.in (OGD Platform India: scholarships, CTS, NAPS, PMKVY)
2. Adzuna India Jobs API (live vacancies across Maharashtra districts)

Enforces SHA-256 deduplication, validates via Pydantic, stamps unforgeable provenance,
updates schemes and jobs in authoritative Supabase (and cache), and records audit trails.
"""
from __future__ import annotations

import datetime
import logging
import time
import uuid
from typing import Any

from app.config import settings
from app.core.data_mode import is_explicit_demo_mode
from app.db import (
    get_demo,
    set_demo,
    save_sync_log,
    is_supabase_connected,
    persist_schemes_to_supabase,
    persist_jobs_to_supabase,
)
from app.ingestion.base_adapter import SOURCE_TYPE_LIVE_API
from app.ingestion.adzuna_connector import AdzunaConnector
from app.ingestion.datagov_connector import (
    DataGovConnector,
    RESOURCE_SCHOLARSHIP_ALLOCATION,
    RESOURCE_ITI_CRAFTSMEN,
    RESOURCE_NAPS_APPRENTICESHIP,
    RESOURCE_PMKVY_SKILL,
)
from app.ingestion.source_orchestrator import (
    SourceOrchestrator,
    WORKLOAD_JOBS,
    WORKLOAD_GOVERNMENT_SCHEMES,
    WORKLOAD_GOVERNMENT_DATASETS,
    source_orchestrator as default_source_orchestrator,
)

logger = logging.getLogger("skillsetu.ingestion.sync_engine")


class SyncEngine:

    def __init__(
        self,
        datagov_connector: DataGovConnector | None = None,
        adzuna_connector: AdzunaConnector | None = None,
        source_orchestrator: SourceOrchestrator | None = None,
    ):
        if source_orchestrator is not None:
            self.source_orchestrator = source_orchestrator
            self.datagov_connector = datagov_connector or getattr(source_orchestrator, "_datagov_connector", None) or DataGovConnector()
            self.adzuna_connector = adzuna_connector or getattr(source_orchestrator, "_adzuna_connector", None) or AdzunaConnector()
        elif datagov_connector is None and adzuna_connector is None:
            self.source_orchestrator = default_source_orchestrator
            self.datagov_connector = default_source_orchestrator._datagov_connector
            self.adzuna_connector = default_source_orchestrator._adzuna_connector
        else:
            self.datagov_connector = datagov_connector or DataGovConnector()
            self.adzuna_connector = adzuna_connector or AdzunaConnector()
            self.source_orchestrator = SourceOrchestrator(
                adzuna_connector=self.adzuna_connector,
                datagov_connector=self.datagov_connector,
            )
        self.connector = self.datagov_connector

    def run_sync(self, source_name: str = "all") -> dict[str, Any]:
        sync_id = str(uuid.uuid4())
        started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        start_perf = time.perf_counter()

        log_entry: dict[str, Any] = {
            "id": sync_id,
            "source_name": source_name,
            "job_type": "automated_external_ingestion",
            "status": "running",
            "records_fetched": 0,
            "records_added": 0,
            "records_updated": 0,
            "records_skipped": 0,
            "error_message": None,
            "started_at": started_at,
            "completed_at": None,
            "duration_ms": 0,
            "is_demo": is_explicit_demo_mode(),
        }
        save_sync_log(log_entry)

        try:
            total_fetched = 0
            total_added = 0
            total_updated = 0
            total_skipped = 0
            src_norm = (source_name or "all").lower().strip()
            valid_sources = {
                "all",
                "data.gov.in",
                "schemes",
                "ogd",
                "adzuna",
                "jobs",
                "industry_signals",
                "industry",
                "skill_forecasts",
                "forecasts",
                "forecast",
            }
            if src_norm not in valid_sources:
                raise ValueError(f"Unsupported sync source selector '{source_name}'. Supported selectors: {sorted(valid_sources)}")

            source_errors = []
            source_successes = []
            sources_detail: dict[str, Any] = {}

            if src_norm in ("all", "data.gov.in", "schemes", "ogd"):
                try:
                    logger.info("[SyncEngine] Ingesting government datasets from data.gov.in...")
                    dg_fetched = 0
                    dg_added = 0
                    dg_updated = 0
                    dg_skipped = 0
                    dg_errors = []

                    res_list = [
                        (RESOURCE_SCHOLARSHIP_ALLOCATION, "scholarship", WORKLOAD_GOVERNMENT_SCHEMES),
                        (RESOURCE_ITI_CRAFTSMEN, "cts", WORKLOAD_GOVERNMENT_SCHEMES),
                        (RESOURCE_NAPS_APPRENTICESHIP, "naps", WORKLOAD_GOVERNMENT_DATASETS),
                        (RESOURCE_PMKVY_SKILL, "pmkvy", WORKLOAD_GOVERNMENT_DATASETS),
                    ]
                    all_transformed_schemes = []
                    all_transformed_opps = []

                    for r_id, r_type, workload in res_list:
                        orch_resp = self.source_orchestrator.fetch_data(
                            workload=workload,
                            limit=50,
                            resource_id=r_id,
                            resource_type=r_type,
                            is_demo=is_explicit_demo_mode(),
                        )
                        if orch_resp.status != "SUCCESS":
                            dg_errors.append(f"{r_id}: {orch_resp.error or orch_resp.status}")
                            continue

                        recs = orch_resp.records
                        dg_fetched += len(recs)
                        if orch_resp.is_demo:
                            if r_type in ("scholarship", "cts"):
                                all_transformed_schemes.extend(recs)
                            else:
                                all_transformed_opps.extend(recs)
                        elif orch_resp.provenance == SOURCE_TYPE_LIVE_API:
                            if r_type in ("scholarship", "cts"):
                                all_transformed_schemes.extend(recs)
                            else:
                                all_transformed_opps.extend(recs)

                    if all_transformed_schemes:
                        added_s, updated_s = self._upsert_schemes(all_transformed_schemes)
                        dg_added += added_s
                        dg_updated += updated_s

                    if all_transformed_opps:
                        added_o, updated_o = self._upsert_jobs(all_transformed_opps)
                        dg_added += added_o
                        dg_updated += updated_o

                    total_fetched += dg_fetched
                    total_added += dg_added
                    total_updated += dg_updated
                    total_skipped += dg_skipped

                    if not self.datagov_connector.has_api_key and not is_explicit_demo_mode():
                        dg_status = "NOT_CONFIGURED"
                        err_text = "DATA_GOV_API_KEY is not configured in production environment."
                        source_errors.append(f"data.gov.in: {dg_status} - {err_text}")
                    elif dg_errors:
                        dg_status = "FAILED" if dg_fetched == 0 else "PARTIAL"
                        err_text = "; ".join(dg_errors)
                        source_errors.append(f"data.gov.in: {dg_status} - {err_text}")
                    elif dg_fetched == 0:
                        dg_status = "NO_DATA"
                        source_successes.append("data.gov.in")
                        err_text = None
                    else:
                        dg_status = "SUCCESS"
                        source_successes.append("data.gov.in")
                        err_text = None

                    sources_detail["data.gov.in"] = {
                        "status": dg_status,
                        "error": err_text,
                        "records_fetched": dg_fetched,
                        "records_added": dg_added,
                        "records_updated": dg_updated,
                        "records_skipped": dg_skipped,
                    }
                except Exception as err:
                    logger.warning("[SyncEngine] Datagov ingestion failed: %s", err)
                    source_errors.append(f"data.gov.in: FAILED - {err}")
                    sources_detail["data.gov.in"] = {
                        "status": "FAILED",
                        "error": str(err),
                        "records_fetched": 0,
                        "records_added": 0,
                        "records_updated": 0,
                        "records_skipped": 0,
                    }

            if src_norm in ("all", "adzuna", "jobs"):
                try:
                    logger.info("[SyncEngine] Ingesting live job vacancies from Adzuna India via SourceOrchestrator...")
                    orch_resp = self.source_orchestrator.fetch_data(
                        workload=WORKLOAD_JOBS,
                        limit=25,
                        where="Maharashtra",
                        is_demo=is_explicit_demo_mode(),
                    )
                    adz_fetched = orch_resp.records_count
                    adz_added = 0
                    adz_updated = 0
                    adz_skipped = 0

                    if orch_resp.status == "SUCCESS":
                        if orch_resp.is_demo:
                            added_j, updated_j = self._upsert_jobs(orch_resp.records)
                            adz_added += added_j
                            adz_updated += updated_j
                            self._upsert_job_skills(orch_resp.records)
                        elif orch_resp.provenance == SOURCE_TYPE_LIVE_API:
                            added_j, updated_j = self._upsert_jobs(orch_resp.records)
                            adz_added += added_j
                            adz_updated += updated_j
                            self._upsert_job_skills(orch_resp.records)

                    total_fetched += adz_fetched
                    total_added += adz_added
                    total_updated += adz_updated
                    total_skipped += adz_skipped

                    adz_status = orch_resp.status
                    adz_err = orch_resp.error

                    if adz_status in ("NOT_CONFIGURED", "UNAVAILABLE", "VALIDATION_FAILED", "FAILED"):
                        source_errors.append(f"adzuna: {adz_status} - {adz_err}")
                    else:
                        source_successes.append("adzuna")

                    sources_detail["adzuna"] = {
                        "status": adz_status,
                        "error": adz_err,
                        "records_fetched": adz_fetched,
                        "records_added": adz_added,
                        "records_updated": adz_updated,
                        "records_skipped": adz_skipped,
                    }
                except Exception as err:
                    logger.warning("[SyncEngine] Adzuna ingestion failed: %s", err)
                    source_errors.append(f"adzuna: FAILED - {err}")
                    sources_detail["adzuna"] = {
                        "status": "FAILED",
                        "error": str(err),
                        "records_fetched": 0,
                        "records_added": 0,
                        "records_updated": 0,
                        "records_skipped": 0,
                    }

            if src_norm in ("all", "industry_signals", "industry"):
                try:
                    from app.ingestion.industry_intelligence import industry_ingestor
                    ind_res = industry_ingestor.ingest_from_feeds(is_demo=is_explicit_demo_mode())
                    ind_fetched = ind_res.get("records_fetched", ind_res.get("fetched", 0))
                    ind_added = ind_res.get("records_added", ind_res.get("added", 0))
                    ind_updated = ind_res.get("records_updated", ind_res.get("updated", 0))
                    ind_skipped = ind_res.get("records_duplicated", ind_res.get("skipped", 0))
                    total_fetched += ind_fetched
                    total_added += ind_added
                    total_updated += ind_updated
                    total_skipped += ind_skipped
                    source_successes.append("industry_signals")
                    sources_detail["industry_signals"] = {
                        "status": "SUCCESS" if ind_fetched else "NO_DATA",
                        "error": None,
                        "records_fetched": ind_fetched,
                        "records_added": ind_added,
                        "records_updated": ind_updated,
                        "records_skipped": ind_skipped,
                    }
                except Exception as err:
                    logger.warning("[SyncEngine] Industry signals ingestion failed: %s", err)
                    source_errors.append(f"industry_signals: FAILED - {err}")
                    sources_detail["industry_signals"] = {
                        "status": "FAILED",
                        "error": str(err),
                        "records_fetched": 0,
                        "records_added": 0,
                        "records_updated": 0,
                        "records_skipped": 0,
                    }

            if src_norm in ("all", "skill_forecasts", "forecasts", "forecast"):
                if not is_supabase_connected() and not is_explicit_demo_mode():
                    err_text = "Supabase client is not configured or unavailable in production environment."
                    source_errors.append(f"skill_forecasts: NOT_CONFIGURED - {err_text}")
                    sources_detail["skill_forecasts"] = {
                        "status": "NOT_CONFIGURED",
                        "error": err_text,
                        "records_fetched": 0,
                        "records_added": 0,
                        "records_updated": 0,
                        "records_skipped": 0,
                    }
                else:
                    try:
                        from app.services.forecast_engine import persist_computed_forecasts
                        fc_res = persist_computed_forecasts()
                        fc_count = len(fc_res)
                        total_added += fc_count
                        source_successes.append("skill_forecasts")
                        sources_detail["skill_forecasts"] = {
                            "status": "SUCCESS" if fc_count else "NO_DATA",
                            "error": None,
                            "records_fetched": fc_count,
                            "records_added": fc_count,
                            "records_updated": 0,
                            "records_skipped": 0,
                        }
                    except Exception as err:
                        logger.warning("[SyncEngine] Forecasts persistence failed: %s", err)
                        source_errors.append(f"skill_forecasts: FAILED - {err}")
                        sources_detail["skill_forecasts"] = {
                            "status": "FAILED",
                            "error": str(err),
                            "records_fetched": 0,
                            "records_added": 0,
                            "records_updated": 0,
                            "records_skipped": 0,
                        }

            duration_ms = int((time.perf_counter() - start_perf) * 1000)
            completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

            if source_errors:
                if not source_successes:
                    status_val = "failed"
                else:
                    status_val = "partial" if src_norm == "all" else "failed"
                err_msg = "; ".join(source_errors)
            else:
                status_val = "success"
                err_msg = None

            log_entry.update({
                "status": status_val,
                "records_fetched": total_fetched,
                "records_added": total_added,
                "records_updated": total_updated,
                "records_skipped": total_skipped,
                "error_message": err_msg,
                "completed_at": completed_at,
                "duration_ms": duration_ms,
                "sources_detail": sources_detail,
            })
            save_sync_log(log_entry)

            logger.info(
                "Sync completed successfully in %d ms: fetched=%d, added=%d, updated=%d",
                duration_ms, total_fetched, total_added, total_updated
            )
            return log_entry

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start_perf) * 1000)
            completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            error_msg = str(exc)
            logger.exception("Ingestion failed: %s", error_msg)

            log_entry.update({
                "status": "failed",
                "error_message": error_msg,
                "completed_at": completed_at,
                "duration_ms": duration_ms,
                "sources_detail": sources_detail,
            })
            save_sync_log(log_entry)
            return log_entry

    def _upsert_schemes(self, incoming_schemes: list[dict[str, Any]]) -> tuple[int, int]:
        is_demo = is_explicit_demo_mode()
        supabase_ready = is_supabase_connected()

        if is_demo:
            persisted_schemes = list(get_demo("schemes"))
        else:
            if not supabase_ready:
                from app.repositories.supabase_repository import SupabaseConnectionError
                raise SupabaseConnectionError("Supabase connection required for real-mode sync")
            from app.repositories.supabase_repository import list_schemes
            persisted_schemes = []
            page_size = 1000
            offset = 0
            while True:
                batch = list_schemes(limit=page_size, offset=offset) or []
                persisted_schemes.extend(batch)
                if len(batch) < page_size:
                    break
                offset += page_size

        source_id_index = {
            (s.get("source"), s.get("external_id")): s
            for s in persisted_schemes
            if s.get("source") and s.get("external_id")
        }
        hash_index = {
            s.get("content_hash"): s
            for s in persisted_schemes
            if s.get("content_hash")
        }

        added = 0
        updated = 0
        now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

        for s in incoming_schemes:
            source = s.get("source")
            ext_id = s.get("external_id")
            c_hash = s.get("content_hash")

            target_record = None
            if source and ext_id:
                target_record = source_id_index.get((source, ext_id))
            elif c_hash:
                target_record = hash_index.get(c_hash)

            if target_record is not None:
                s["id"] = target_record.get("id") or s.get("id") or str(uuid.uuid4())
                s["last_synced_at"] = now_ts
                s["last_seen_at"] = now_ts
                target_record.update(s)
                updated += 1
            else:
                s["id"] = s.get("id") or str(uuid.uuid4())
                s["last_synced_at"] = now_ts
                s["last_seen_at"] = now_ts
                persisted_schemes.append(s)
                if source and ext_id:
                    source_id_index[(source, ext_id)] = s
                if c_hash:
                    hash_index[c_hash] = s
                added += 1

        if is_demo:
            set_demo("schemes", persisted_schemes)
        else:
            from app.repositories.supabase_repository import upsert_schemes
            upsert_schemes(incoming_schemes)

        return added, updated

    def _upsert_jobs(self, incoming_jobs: list[dict[str, Any]]) -> tuple[int, int]:
        is_demo = is_explicit_demo_mode()
        supabase_ready = is_supabase_connected()

        if is_demo:
            persisted_jobs = list(get_demo("jobs"))
        else:
            if not supabase_ready:
                from app.repositories.supabase_repository import SupabaseConnectionError
                raise SupabaseConnectionError("Supabase connection required for real-mode sync")
            from app.repositories.supabase_repository import list_jobs
            persisted_jobs = []
            page_size = 1000
            offset = 0
            while True:
                batch = list_jobs(limit=page_size, offset=offset) or []
                persisted_jobs.extend(batch)
                if len(batch) < page_size:
                    break
                offset += page_size

        source_id_index = {
            (j.get("source"), (j.get("external_id") or j.get("ext_id"))): j
            for j in persisted_jobs
            if j.get("source") and (j.get("external_id") or j.get("ext_id"))
        }
        hash_index = {
            j.get("content_hash"): j
            for j in persisted_jobs
            if j.get("content_hash")
        }

        added = 0
        updated = 0
        now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        valid_incoming = []

        from app.ingestion.job_intelligence import validate_and_normalize
        from app.ingestion.base_adapter import compute_freshness

        for raw_job in incoming_jobs:
            job, err = validate_and_normalize(
                raw_job,
                is_demo=is_demo,
                is_trusted_feed=(not is_demo and raw_job.get("source_type") in ("LIVE_API", "VERIFIED_SNAPSHOT", "OFFICIAL_GOV")),
            )
            if err or not job:
                if isinstance(raw_job, dict) and (raw_job.get("source") or raw_job.get("external_id") or raw_job.get("content_hash")):
                    job = dict(raw_job)
                else:
                    continue

            if is_demo is False and (
                job.get("is_demo") is True
                or job.get("source") == "DEMO_SYNTHETIC"
                or job.get("data_provenance") == "DEMO_SYNTHETIC"
            ):
                continue

            c_hash = job.get("content_hash")
            source = job.get("source")
            ext_id = job.get("external_id") or job.get("ext_id")
            if ext_id and not job.get("external_id"):
                job["external_id"] = ext_id

            target_record = None
            if source and ext_id:
                target_record = source_id_index.get((source, ext_id))
            elif c_hash:
                target_record = hash_index.get(c_hash)

            if target_record is not None:
                job["id"] = target_record.get("id") or job.get("id") or str(uuid.uuid4())
                job["fetched_at"] = target_record.get("fetched_at") or job.get("fetched_at") or now_ts
                job["last_synced_at"] = now_ts
                job["last_seen_at"] = now_ts
                if target_record.get("verified_at"):
                    job["verified_at"] = target_record["verified_at"]
                job["freshness_status"] = compute_freshness(
                    published_at=job.get("published_at"),
                    snapshot_captured_at=job.get("snapshot_captured_at"),
                    last_seen_at=now_ts,
                )
                target_record.update(job)
                raw_job.update(job)
                valid_incoming.append(job)
                updated += 1
            else:
                job["id"] = job.get("id") or str(uuid.uuid4())
                job["fetched_at"] = job.get("fetched_at") or now_ts
                job["last_synced_at"] = now_ts
                job["last_seen_at"] = now_ts
                persisted_jobs.append(job)
                if source and ext_id:
                    source_id_index[(source, ext_id)] = job
                if c_hash:
                    hash_index[c_hash] = job
                raw_job.update(job)
                valid_incoming.append(job)
                added += 1

        if is_demo:
            set_demo("jobs", persisted_jobs)
        else:
            from app.repositories.supabase_repository import upsert_jobs
            upsert_jobs(valid_incoming)

        return added, updated

    _upsert_opportunities = _upsert_jobs

    def _upsert_job_skills(self, jobs: list[dict[str, Any]]) -> int:
        is_demo = is_explicit_demo_mode()
        supabase_ready = is_supabase_connected()
        incoming_job_ids = [j.get("id") for j in jobs if j.get("id")]

        if is_demo:
            current_js = list(get_demo("job_skills"))
            existing_keys = {(js.get("job_id"), js.get("skill_id")) for js in current_js}
        else:
            if not supabase_ready:
                from app.repositories.supabase_repository import SupabaseConnectionError
                raise SupabaseConnectionError("Supabase connection required for real-mode sync")
            from app.repositories.supabase_repository import list_job_skills
            current_js = list_job_skills(job_ids=incoming_job_ids) or []
            existing_keys = {(js.get("job_id"), js.get("skill_id")) for js in current_js}

        new_links = []
        for job in jobs:
            jid = job.get("id")
            if not jid:
                continue
            for sid in job.get("skill_ids", []):
                if (jid, sid) not in existing_keys:
                    link = {
                        "job_id": jid,
                        "skill_id": sid,
                        "proficiency_required": "intermediate",
                    }
                    existing_keys.add((jid, sid))
                    new_links.append(link)

        if new_links:
            if is_demo:
                demo_js = list(get_demo("job_skills"))
                demo_js.extend(new_links)
                set_demo("job_skills", demo_js)
            else:
                from app.repositories.supabase_repository import batch_create_job_skills
                batch_create_job_skills(new_links)

        return len(new_links)
