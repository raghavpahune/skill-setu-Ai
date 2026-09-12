"""Read-only MCP tool definitions for SkillSetu."""
import asyncio
import json
from typing import Any

import secrets
from app.config import settings
from app.core.data_mode import is_explicit_demo_mode
from app.db import get_demo
from app.routers.schemes import list_schemes
from app.routers.opportunities import list_opportunities
from app.services.gap_engine import compute_gaps

ALLOWED_MCP_SOURCES = {
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
}


def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def tool_get_schemes(args: dict[str, Any]) -> dict[str, Any]:
    category = args.get("category")
    scheme_type = args.get("scheme_type")
    course_type = args.get("course_type")
    district = args.get("district")
    max_income = args.get("max_income")
    q = args.get("q")
    limit = min(int(args.get("limit", 20)), 50)

    schemes = _run_async(list_schemes(
        category=category,
        scheme_type=scheme_type,
        course_type=course_type,
        district=district,
        max_income=max_income,
        status="active",
        q=q,
        limit=limit,
        offset=0,
    ))
    return {"total_returned": len(schemes), "schemes": schemes}


def tool_get_opportunities(args: dict[str, Any]) -> dict[str, Any]:
    opportunity_type = args.get("opportunity_type")
    district = args.get("district")
    industry = args.get("industry")
    skill = args.get("skill")
    min_stipend = args.get("min_stipend")
    q = args.get("q")
    limit = min(int(args.get("limit", 20)), 50)

    opps = _run_async(list_opportunities(
        opportunity_type=opportunity_type,
        district=district,
        industry=industry,
        skill=skill,
        min_stipend=min_stipend,
        status="active",
        q=q,
        limit=limit,
        offset=0,
    ))
    return {"total_returned": len(opps), "opportunities": opps}


def tool_get_skill_gaps(args: dict[str, Any]) -> dict[str, Any]:
    limit = min(int(args.get("limit", 10)), 25)
    gaps = compute_gaps()
    return {"total_gaps_calculated": len(gaps), "top_gaps": gaps[:limit]}


def tool_get_sync_freshness(args: dict[str, Any]) -> dict[str, Any]:
    requested_source = args.get("source")
    failed_to_fetch = False
    if is_explicit_demo_mode():
        logs = [l for l in get_demo("sync_logs") if l.get("is_demo") is True]
        if requested_source:
            logs = [log for log in logs if log.get("source_name") == requested_source]
    else:
        try:
            from app.repositories.supabase_repository import list_sync_logs
            logs = list_sync_logs(limit=50, source_name=requested_source, is_demo=False)
            logs = [l for l in logs if not l.get("is_demo")]
        except Exception:
            logs = []
            failed_to_fetch = True

    logs.sort(key=lambda x: x.get("started_at", ""), reverse=True)
    last_log = logs[0] if logs else None
    last_success = next((log for log in logs if log.get("status") == "success"), None)

    if failed_to_fetch and not logs:
        status = "unavailable"
    elif last_log and last_log.get("status") == "success":
        status = "healthy"
    elif last_log and last_log.get("status") == "failed":
        status = "failed"
    else:
        status = "idle"

    return {
        "status": status,
        "total_sync_runs": len(logs),
        "last_sync_timestamp": last_log.get("completed_at") if last_log else None,
        "last_successful_sync_timestamp": last_success.get("completed_at") if last_success else None,
        "last_records_fetched": last_log.get("records_fetched", 0) if last_log else 0,
        "last_records_added": last_log.get("records_added", 0) if last_log else 0,
        "last_records_updated": last_log.get("records_updated", 0) if last_log else 0,
        "active_sources": ["data.gov.in", "adzuna", "industry_signals", "skill_forecasts"],
    }


def tool_refresh_data_source(args: dict[str, Any]) -> dict[str, Any]:
    configured_key = (getattr(settings, "admin_api_key", None) or "").strip()
    admin_key = str(args.get("admin_key") or args.get("admin_api_key") or "").strip()
    caller_role = str(args.get("role") or args.get("caller_role") or "").strip().upper()
    if caller_role and caller_role != "ADMIN":
        return {
            "status": "error",
            "error": "Unauthorized: non-admin callers cannot trigger data refresh",
        }
    if not configured_key or not admin_key or not secrets.compare_digest(admin_key, configured_key):
        return {
            "status": "error",
            "error": "Unauthorized: valid admin API key required to trigger data refresh",
        }

    source = str(args.get("source", "all")).lower().strip()
    if source not in ALLOWED_MCP_SOURCES:
        return {
            "status": "error",
            "error": f"Invalid source '{source}'. Allowed sources: {sorted(ALLOWED_MCP_SOURCES)}",
        }

    from app.ingestion.scheduler import scheduler
    result = _run_async(scheduler.execute_sync(source=source))
    safe_result = {
        "status": result.get("status", "unknown"),
        "source": source,
        "records_fetched": result.get("records_fetched", 0),
        "records_added": result.get("records_added", 0),
        "records_updated": result.get("records_updated", 0),
        "records_skipped": result.get("records_skipped", 0),
        "duration_ms": result.get("duration_ms", 0),
        "completed_at": result.get("completed_at"),
    }
    if result.get("error_message"):
        safe_result["error_message"] = str(result.get("error_message"))
    if result.get("message"):
        safe_result["message"] = str(result.get("message"))
    return safe_result


def tool_get_sync_logs(args: dict[str, Any]) -> dict[str, Any]:
    limit = min(max(int(args.get("limit", 10)), 1), 50)
    source = args.get("source")
    if is_explicit_demo_mode():
        logs = [l for l in get_demo("sync_logs") if l.get("is_demo") is True]
        if source:
            logs = [log for log in logs if log.get("source_name") == source]
    else:
        try:
            from app.repositories.supabase_repository import list_sync_logs
            logs = list_sync_logs(limit=limit, source_name=source, is_demo=False)
            logs = [l for l in logs if not l.get("is_demo")]
        except Exception:
            logs = []

    logs.sort(key=lambda x: x.get("started_at", ""), reverse=True)
    safe_logs = []
    for log in logs[:limit]:
        safe_logs.append({
            "id": log.get("id"),
            "source_name": log.get("source_name"),
            "status": log.get("status"),
            "records_fetched": log.get("records_fetched", 0),
            "records_added": log.get("records_added", 0),
            "records_updated": log.get("records_updated", 0),
            "started_at": log.get("started_at"),
            "completed_at": log.get("completed_at"),
            "duration_ms": log.get("duration_ms", 0),
            "error_message": log.get("error_message"),
        })
    return {"total_logs": len(safe_logs), "logs": safe_logs}


TOOLS = {
    "get_schemes": {
        "name": "get_schemes",
        "description": "Query government welfare schemes, scholarships, fee waivers, hostel grants, and training subsidies with multi-parameter filtering.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Target beneficiary category: SC, ST, OBC, EWS, Women, or Open",
                },
                "scheme_type": {
                    "type": "string",
                    "description": "Type of scheme: scholarship, fee_waiver, hostel_allowance, training_scheme, stipend, or tool_grant",
                },
                "course_type": {
                    "type": "string",
                    "description": "Eligible course type: ITI, Polytechnic, Diploma, or Engineering",
                },
                "district": {
                    "type": "string",
                    "description": "Maharashtra district name (e.g. Pune, Mumbai, Nagpur)",
                },
                "max_income": {
                    "type": "integer",
                    "description": "Annual family income in INR (filters schemes where ceiling is applicable)",
                },
                "q": {
                    "type": "string",
                    "description": "Search keywords matching title, department, or description",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum records to return (default 20, max 50)",
                },
            },
        },
        "handler": tool_get_schemes,
    },
    "get_opportunities": {
        "name": "get_opportunities",
        "description": "Query opportunities including full-time jobs, apprenticeships (NAPS), internships, and vocational training (PMKVY) with attached skill requirements.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "opportunity_type": {
                    "type": "string",
                    "enum": ["job", "internship", "apprenticeship", "vocational_training"],
                    "description": "Type of opportunity to filter by",
                },
                "district": {
                    "type": "string",
                    "description": "Target Maharashtra district (e.g. Pune, Mumbai, Nashik)",
                },
                "industry": {
                    "type": "string",
                    "description": "Industry sector (e.g. Manufacturing, Electric Vehicles, IT/ITES)",
                },
                "skill": {
                    "type": "string",
                    "description": "Required skill name or skill ID (e.g. Python, CNC Programming, PLC)",
                },
                "min_stipend": {
                    "type": "integer",
                    "description": "Minimum monthly stipend in INR",
                },
                "q": {
                    "type": "string",
                    "description": "Text search matching title, company, or description",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum records to return (default 20, max 50)",
                },
            },
        },
        "handler": tool_get_opportunities,
    },
    "get_skill_gaps": {
        "name": "get_skill_gaps",
        "description": "Compute and rank current labour-market skill demand vs. supply deficits, urgency rankings, and shortages for curriculum and career planning.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "district": {
                    "type": "string",
                    "description": "District to compute gaps for (omit for state-wide)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of top skill gaps to return (default 10, max 25)",
                },
            },
        },
        "handler": tool_get_skill_gaps,
    },
    "get_sync_freshness": {
        "name": "get_sync_freshness",
        "description": "Check the health, freshness, and audit history of external data sources (e.g. data.gov.in ingestion runs).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Source name to check (default: data.gov.in)",
                },
            },
        },
        "handler": tool_get_sync_freshness,
    },
    "refresh_data_source": {
        "name": "refresh_data_source",
        "description": "Trigger automated real-data ingestion and synchronization for an approved external data source.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Source to refresh (all, data.gov.in, adzuna, jobs, schemes, industry_signals, skill_forecasts)",
                },
                "admin_key": {
                    "type": "string",
                    "description": "Optional admin API key for authentication",
                },
            },
        },
        "handler": tool_refresh_data_source,
    },
    "get_sync_logs": {
        "name": "get_sync_logs",
        "description": "Retrieve recent synchronization audit logs showing record counts, duration, and execution statuses.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum log entries to return (default 10, max 50)",
                },
                "source": {
                    "type": "string",
                    "description": "Filter by source name (optional)",
                },
            },
        },
        "handler": tool_get_sync_logs,
    },
}
