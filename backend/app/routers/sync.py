import logging
from typing import Any
from fastapi import APIRouter, Header, HTTPException, Query, status, Depends

logger = logging.getLogger(__name__)
from app.config import settings
from app.core.data_mode import is_explicit_demo_mode
from app.db import get_demo, is_supabase_connected
from app.ingestion.datagov_connector import (
    DataGovConnector,
    RESOURCE_SCHOLARSHIP_ALLOCATION,
    RESOURCE_ITI_CRAFTSMEN,
    RESOURCE_NAPS_APPRENTICESHIP,
    RESOURCE_NAPS_NATS_STIPEND,
    RESOURCE_PMKVY_SKILL,
)
from app.ingestion.adzuna_connector import AdzunaConnector
from app.ingestion.sync_engine import SyncEngine
from app.ingestion.scheduler import scheduler

from app.core.security import get_optional_current_user

router = APIRouter()


ALLOWED_SOURCES = {
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


@router.post("/sync/trigger")
async def trigger_sync(
    source: str = Query("data.gov.in", description="Source to ingest data from"),
    x_admin_key: str | None = Header(None, alias="X-Admin-Key"),
    current_user: Any = Depends(get_optional_current_user),
):
    source_norm = (source or "data.gov.in").lower().strip()
    if source_norm not in ALLOWED_SOURCES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid sync source selector '{source}'. Allowed sources: {sorted(ALLOWED_SOURCES)}",
        )

    if settings.admin_api_key and settings.admin_api_key.strip():
        is_admin_user = current_user and (current_user.get("role") or "").upper() == "ADMIN"
        is_key_match = x_admin_key and x_admin_key.strip() == settings.admin_api_key.strip()
        if not is_admin_user and not is_key_match:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized: invalid or missing admin credentials",
            )

    result = await scheduler.execute_sync(source=source_norm)
    return result


@router.get("/sync/logs")
async def get_sync_logs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    is_demo: bool | None = Query(None, description="Explicit demo/real mode selector"),
):
    from app.db import decode_sync_log
    if is_explicit_demo_mode(is_demo):
        raw_logs = list(get_demo("sync_logs"))
        logs = [decode_sync_log(l) for l in raw_logs if l.get("is_demo") is True]
    else:
        try:
            from app.repositories.supabase_repository import list_sync_logs
            raw_logs = list_sync_logs(limit=limit + offset, is_demo=False)
        except Exception as e:
            logger.warning("[Sync] Failed fetching sync_logs from repository: %s", e)
            raw_logs = []
        if not raw_logs:
            from app.db import _cache
            raw_logs = list(_cache.get("sync_logs", []))
        decoded_logs = [decode_sync_log(l) for l in raw_logs]
        logs = [l for l in decoded_logs if not l.get("is_demo")]
    logs.sort(key=lambda x: x.get("started_at", ""), reverse=True)
    return logs[offset : offset + limit]


@router.get("/sync/status")
async def get_sync_status(
    is_demo: bool | None = Query(None, description="Explicit demo/real mode selector"),
):
    dg_connector = DataGovConnector()
    adz_connector = AdzunaConnector()
    is_demo_mode = is_explicit_demo_mode(is_demo)
    from app.db import decode_sync_log

    if is_demo_mode:
        raw_logs = list(get_demo("sync_logs"))
        logs = [decode_sync_log(l) for l in raw_logs if l.get("is_demo") is True]
    else:
        try:
            from app.repositories.supabase_repository import list_sync_logs
            raw_logs = list_sync_logs(limit=20, is_demo=False)
        except Exception as e:
            logger.warning("[Sync] Failed fetching sync_logs from repository: %s", e)
            raw_logs = []
        if not raw_logs:
            from app.db import _cache
            raw_logs = list(_cache.get("sync_logs", []))
        decoded_logs = [decode_sync_log(l) for l in raw_logs]
        logs = [l for l in decoded_logs if not l.get("is_demo")]

    logs.sort(key=lambda x: x.get("started_at", ""), reverse=True)
    last_run = logs[0] if logs else None
    last_success = next(
        (l for l in logs if (l.get("status") or "").lower() in ("success", "no_data")),
        None,
    )

    dg_configured = True if is_demo_mode else dg_connector.has_api_key
    adz_configured = True if is_demo_mode else adz_connector.has_credentials

    source_configs = {
        "data.gov.in": {
            "configured": dg_configured,
            "aliases": ("data.gov.in", "schemes", "ogd"),
            "unconfigured_error": "DATA_GOV_API_KEY is not configured in production environment.",
        },
        "adzuna": {
            "configured": adz_configured,
            "aliases": ("adzuna", "jobs"),
            "unconfigured_error": "ADZUNA_APP_ID / ADZUNA_APP_KEY not configured in production environment.",
        },
        "industry_signals": {
            "configured": True,
            "aliases": ("industry_signals", "industry"),
            "unconfigured_error": None,
        },
        "skill_forecasts": {
            "configured": is_supabase_connected(),
            "aliases": ("skill_forecasts", "forecasts", "forecast"),
            "unconfigured_error": "Supabase client is not configured or unavailable in production environment.",
        },
    }

    sources_summary = {}

    for src_name, cfg in source_configs.items():
        is_conf = cfg["configured"]
        aliases = cfg["aliases"]
        unconf_err = cfg["unconfigured_error"]

        matching_log = next(
            (
                l for l in logs
                if (isinstance(l.get("sources_detail"), dict) and src_name in l["sources_detail"])
                or l.get("source_name") in aliases
            ),
            None,
        )

        if is_demo_mode:
            demo_fetched = matching_log.get("records_fetched", 10) if matching_log else 10
            sources_summary[src_name] = {
                "source": src_name,
                "status": "SUCCESS",
                "configured": True,
                "last_sync": matching_log.get("completed_at") if matching_log else None,
                "records_fetched": demo_fetched,
                "records_added": demo_fetched,
                "records_updated": 0,
                "records_skipped": 0,
                "error": None,
            }
            continue

        if not is_conf:
            sources_summary[src_name] = {
                "source": src_name,
                "status": "NOT_CONFIGURED",
                "configured": False,
                "last_sync": matching_log.get("completed_at") if matching_log else None,
                "records_fetched": 0,
                "records_added": 0,
                "records_updated": 0,
                "records_skipped": 0,
                "error": unconf_err,
            }
            continue

        if matching_log is None:
            sources_summary[src_name] = {
                "source": src_name,
                "status": "IDLE",
                "configured": True,
                "last_sync": None,
                "records_fetched": 0,
                "records_added": 0,
                "records_updated": 0,
                "records_skipped": 0,
                "error": None,
            }
            continue

        last_sync_ts = matching_log.get("completed_at") or matching_log.get("started_at")
        src_detail = (
            matching_log.get("sources_detail", {}).get(src_name)
            if isinstance(matching_log.get("sources_detail"), dict)
            else None
        )

        if src_detail:
            raw_status = (src_detail.get("status") or "").upper()
            detail_err = src_detail.get("error")
            rec_fetched = src_detail.get("records_fetched", 0)
            rec_added = src_detail.get("records_added", 0)
            rec_updated = src_detail.get("records_updated", 0)
            rec_skipped = src_detail.get("records_skipped", 0)

            if raw_status in ("FAILED", "FAIL"):
                eval_status = "FAILED"
                eval_error = detail_err or f"{src_name} sync run failed"
            elif raw_status == "PARTIAL":
                eval_status = "PARTIAL"
                eval_error = detail_err
            elif raw_status == "NO_DATA" or (raw_status == "SUCCESS" and rec_fetched == 0):
                eval_status = "NO_DATA"
                eval_error = None
            elif raw_status == "SUCCESS":
                eval_status = "SUCCESS"
                eval_error = None
            elif raw_status == "NOT_CONFIGURED":
                eval_status = "NOT_CONFIGURED"
                eval_error = detail_err or unconf_err
            else:
                if rec_fetched > 0:
                    eval_status = "SUCCESS"
                    eval_error = None
                else:
                    eval_status = "NO_DATA"
                    eval_error = None

            sources_summary[src_name] = {
                "source": src_name,
                "status": eval_status,
                "configured": True,
                "last_sync": last_sync_ts,
                "records_fetched": rec_fetched,
                "records_added": rec_added,
                "records_updated": rec_updated,
                "records_skipped": rec_skipped,
                "error": eval_error,
            }
        elif matching_log.get("source_name") in aliases:
            log_st = (matching_log.get("status") or "").lower()
            rec_fetched = matching_log.get("records_fetched", 0)
            rec_added = matching_log.get("records_added", 0)
            rec_updated = matching_log.get("records_updated", 0)
            rec_skipped = matching_log.get("records_skipped", 0)
            log_err = matching_log.get("error_message")

            if log_st == "failed":
                eval_status = "FAILED"
                eval_error = log_err or f"{src_name} sync run failed"
            elif log_st == "partial":
                eval_status = "PARTIAL"
                eval_error = log_err
            elif log_st == "no_data":
                eval_status = "NO_DATA"
                eval_error = None
            elif log_st == "not_configured":
                eval_status = "NOT_CONFIGURED"
                eval_error = log_err or unconf_err
            elif log_st == "idle":
                eval_status = "IDLE"
                eval_error = None
            elif log_st == "success":
                if rec_fetched > 0:
                    eval_status = "SUCCESS"
                    eval_error = None
                else:
                    eval_status = "NO_DATA"
                    eval_error = None
            else:
                eval_status = "FAILED"
                eval_error = log_err or f"{src_name} sync run failed"

            sources_summary[src_name] = {
                "source": src_name,
                "status": eval_status,
                "configured": True,
                "last_sync": last_sync_ts,
                "records_fetched": rec_fetched,
                "records_added": rec_added,
                "records_updated": rec_updated,
                "records_skipped": rec_skipped,
                "error": eval_error,
            }
        else:
            sources_summary[src_name] = {
                "source": src_name,
                "status": "IDLE",
                "configured": True,
                "last_sync": None,
                "records_fetched": 0,
                "records_added": 0,
                "records_updated": 0,
                "records_skipped": 0,
                "error": None,
            }

    if is_demo_mode:
        overall_status = "healthy"
    else:
        configured_statuses = [
            s["status"] for s in sources_summary.values() if s.get("configured")
        ]
        if any(st == "FAILED" for st in configured_statuses):
            overall_status = "failed"
        elif sources_summary["data.gov.in"]["status"] in ("NO_DATA", "PARTIAL", "NOT_CONFIGURED"):
            overall_status = "degraded"
        elif any(st in ("NO_DATA", "PARTIAL") for st in configured_statuses):
            overall_status = "degraded"
        elif all(st == "IDLE" for st in configured_statuses):
            overall_status = "idle"
        elif sources_summary["data.gov.in"]["status"] == "SUCCESS":
            overall_status = "healthy"
        else:
            overall_status = "degraded"

    return {
        "status": overall_status,
        "api_key_configured": dg_configured,
        "adzuna_configured": adz_configured,
        "sources": sources_summary,
        "scheduler": scheduler.get_status(latest_log=last_run, latest_success_log=last_success),
        "refresh_interval_minutes": settings.effective_refresh_interval_minutes,
        "total_sync_runs": len(logs),
        "last_sync": last_run,
        "last_successful_sync": last_success,
        "approved_datasets": [
            {
                "resource_id": RESOURCE_SCHOLARSHIP_ALLOCATION,
                "title": "Allocation under Pre-Matric, Post-Matric & MCM Scholarship Schemes",
                "target_entity": "schemes",
            },
            {
                "resource_id": RESOURCE_ITI_CRAFTSMEN,
                "title": "Craftsmen Training Scheme (CTS) through ITIs",
                "target_entity": "schemes",
            },
            {
                "resource_id": RESOURCE_NAPS_APPRENTICESHIP,
                "title": "District-wise Apprentices Engaged under NAPS",
                "target_entity": "jobs (apprenticeship)",
            },
            {
                "resource_id": RESOURCE_NAPS_NATS_STIPEND,
                "title": "Stipend Disbursal Benchmark under NAPS & NATS",
                "target_entity": "jobs (stipend)",
            },
            {
                "resource_id": RESOURCE_PMKVY_SKILL,
                "title": "Candidates Enrolled & Placed under PMKVY",
                "target_entity": "jobs (vocational_training)",
            },
        ],
    }
