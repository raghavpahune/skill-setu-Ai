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
from app.ingestion.adzuna_connector import AdzunaConnector
from app.ingestion.datagov_connector import (
    DataGovConnector,
    RESOURCE_SCHOLARSHIP_ALLOCATION,
    RESOURCE_ITI_CRAFTSMEN,
    RESOURCE_NAPS_APPRENTICESHIP,
    RESOURCE_PMKVY_SKILL,
)

logger = logging.getLogger("skillsetu.ingestion.sync_engine")


class SyncEngine:

    def __init__(
        self,
        datagov_connector: DataGovConnector | None = None,
        adzuna_connector: AdzunaConnector | None = None,
    ):
        self.datagov_connector = datagov_connector or DataGovConnector()
        self.adzuna_connector = adzuna_connector or AdzunaConnector()
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
                        (RESOURCE_SCHOLARSHIP_ALLOCATION, "scholarship"),
                        (RESOURCE_ITI_CRAFTSMEN, "cts"),
                        (RESOURCE_NAPS_APPRENTICESHIP, "naps"),
                        (RESOURCE_PMKVY_SKILL, "pmkvy"),
                    ]
                    all_transformed_schemes = []
                    all_transformed_opps = []

                    for r_id, r_type in res_list:
                        raw_res = self.datagov_connector.fetch_resource(r_id)
                        res_status = raw_res.get("status")
                        if res_status in ("NOT_CONFIGURED", "FAILED"):
                            dg_errors.append(f"{r_id}: {raw_res.get('error')}")
                            continue
                        recs = raw_res.get("records", [])
                        dg_fetched += len(recs)
                        if r_type in ("scholarship", "cts"):
                            if r_type == "scholarship":
                                trans = self.datagov_connector.transform_scholarship_schemes(recs)
                            else:
                                trans = self.datagov_connector.transform_cts_schemes(recs)
                            dg_skipped += max(0, len(recs) - len(trans))
                            all_transformed_schemes.extend(trans)
                        else:
                            if r_type == "naps":
                                trans = self.datagov_connector.transform_naps_opportunities(recs)
                            else:
                                trans = self.datagov_connector.transform_pmkvy_opportunities(recs)
                            dg_skipped += max(0, len(recs) - len(trans))
                            all_transformed_opps.extend(trans)

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
                    logger.info("[SyncEngine] Ingesting live job vacancies from Adzuna India...")
                    adzuna_raw = self.adzuna_connector.fetch_raw(page=1, results_per_page=25, where="Maharashtra")
                    adz_fetched = len(adzuna_raw)
                    adz_added = 0
                    adz_updated = 0
                    adz_skipped = 0

                    if adzuna_raw:
                        adzuna_jobs = self.adzuna_connector.validate_and_transform(adzuna_raw)
                        adz_skipped = max(0, adz_fetched - len(adzuna_jobs))
                        added_j, updated_j = self._upsert_jobs(adzuna_jobs)
                        adz_added += added_j
                        adz_updated += updated_j
                        self._upsert_job_skills(adzuna_jobs)

                    total_fetched += adz_fetched
                    total_added += adz_added
                    total_updated += adz_updated
                    total_skipped += adz_skipped

                    adz_status = self.adzuna_connector.last_status
                    adz_err = self.adzuna_connector.last_error

                    if adz_status in ("NOT_CONFIGURED", "FAILED"):
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
        elif supabase_ready:
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
        elif not settings.use_demo_data:
            from app.repositories.supabase_repository import SupabaseConnectionError
            raise SupabaseConnectionError("Supabase connection required for real-mode sync")
        else:
            persisted_schemes = list(get_demo("schemes"))

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

        if supabase_ready and not is_demo:
            from app.repositories.supabase_repository import upsert_schemes
            upsert_schemes(incoming_schemes)
        else:
            set_demo("schemes", persisted_schemes)

        return added, updated

    def _upsert_jobs(self, incoming_jobs: list[dict[str, Any]]) -> tuple[int, int]:
        is_demo = is_explicit_demo_mode()
        supabase_ready = is_supabase_connected()

        if is_demo:
            persisted_jobs = list(get_demo("jobs"))
        elif supabase_ready:
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
        elif not settings.use_demo_data:
            from app.repositories.supabase_repository import SupabaseConnectionError
            raise SupabaseConnectionError("Supabase connection required for real-mode sync")
        else:
            persisted_jobs = list(get_demo("jobs"))

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

        for job in incoming_jobs:
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
                job["last_synced_at"] = now_ts
                job["last_seen_at"] = now_ts
                target_record.update(job)
                updated += 1
            else:
                job["id"] = job.get("id") or str(uuid.uuid4())
                job["last_synced_at"] = now_ts
                job["last_seen_at"] = now_ts
                persisted_jobs.append(job)
                if source and ext_id:
                    source_id_index[(source, ext_id)] = job
                if c_hash:
                    hash_index[c_hash] = job
                added += 1

        if supabase_ready and not is_demo:
            from app.repositories.supabase_repository import upsert_jobs
            upsert_jobs(incoming_jobs)
        else:
            set_demo("jobs", persisted_jobs)

        return added, updated

    _upsert_opportunities = _upsert_jobs

    def _upsert_job_skills(self, jobs: list[dict[str, Any]]) -> int:
        is_demo = is_explicit_demo_mode()
        supabase_ready = is_supabase_connected()
        incoming_job_ids = [j.get("id") for j in jobs if j.get("id")]

        if is_demo:
            current_js = list(get_demo("job_skills"))
            existing_keys = {(js.get("job_id"), js.get("skill_id")) for js in current_js}
        elif supabase_ready:
            from app.repositories.supabase_repository import list_job_skills
            current_js = list_job_skills(job_ids=incoming_job_ids) or []
            existing_keys = {(js.get("job_id"), js.get("skill_id")) for js in current_js}
        elif not settings.use_demo_data:
            from app.repositories.supabase_repository import SupabaseConnectionError
            raise SupabaseConnectionError("Supabase connection required for real-mode sync")
        else:
            current_js = list(get_demo("job_skills"))
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
            if supabase_ready and not is_demo:
                from app.repositories.supabase_repository import batch_create_job_skills
                batch_create_job_skills(new_links)
            else:
                demo_js = list(get_demo("job_skills"))
                demo_js.extend(new_links)
                set_demo("job_skills", demo_js)

        return len(new_links)
