import os
from typing import Any
from pydantic import BaseModel, Field

SUPPORTED_WORKLOADS = [
    "career_copilot",
    "skill_gap_analysis",
    "learning_roadmap",
    "employee_transition",
    "employer_candidate_analysis",
    "institute_curriculum_analysis",
    "government_policy_analysis",
    "data_insight_generation",
]


class ServiceCredentials(BaseModel):
    configured: bool
    service_name: str
    status: str = "UNKNOWN"
    fallback_available: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


def get_gemini_key() -> str:
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
    if not key:
        try:
            from app.config import settings
            key = settings.gemini_api_key or ""
        except Exception:
            pass
    clean_key = str(key).strip().strip("'\"")
    if clean_key in ("your_key_here", ""):
        return ""
    return clean_key


def get_workload_ai_key(workload: str) -> str:
    cleaned = str(workload).strip().lower()
    env_suffix = cleaned.upper()
    specific_key = os.getenv(f"GEMINI_API_KEY_{env_suffix}") or ""
    clean_specific = str(specific_key).strip().strip("'\"")
    if clean_specific and clean_specific != "your_key_here":
        return clean_specific
    return get_gemini_key()


def is_workload_ai_configured(workload: str) -> bool:
    provider = get_workload_provider(workload)
    if provider == "gemini":
        return bool(get_workload_ai_key(workload))
    if provider in ("deterministic_fallback", "demo_fallback", "demo"):
        return True
    return False


def get_workload_provider(workload: str) -> str:
    cleaned = str(workload).strip().lower()
    env_provider = os.getenv(f"AI_PROVIDER_{cleaned.upper()}")
    if env_provider:
        prov = env_provider.strip().lower()
        if prov in ("gemini", "deterministic_fallback", "demo_fallback", "demo"):
            return prov
        return "unsupported"
    return "gemini"


def get_adzuna_credentials() -> tuple[str, str]:
    app_id = os.getenv("ADZUNA_APP_ID") or ""
    app_key = os.getenv("ADZUNA_APP_KEY") or ""
    if not (app_id and app_key):
        try:
            from app.config import settings
            app_id = app_id or getattr(settings, "adzuna_app_id", "") or ""
            app_key = app_key or getattr(settings, "adzuna_app_key", "") or ""
        except Exception:
            pass
    clean_id = str(app_id).strip()
    clean_key = str(app_key).strip()
    if clean_id in ("your_id_here", "") or clean_key in ("your_key_here", ""):
        return "", ""
    return clean_id, clean_key


def get_datagov_key() -> str:
    key = os.getenv("DATA_GOV_API_KEY") or ""
    if not key:
        try:
            from app.config import settings
            key = getattr(settings, "data_gov_api_key", "") or ""
        except Exception:
            pass
    clean_key = str(key).strip()
    if clean_key in ("your_key_here", ""):
        return ""
    return clean_key


def is_gemini_configured() -> bool:
    return bool(get_gemini_key())


def is_adzuna_configured() -> bool:
    app_id, app_key = get_adzuna_credentials()
    return bool(app_id and app_key)


def is_datagov_configured() -> bool:
    return bool(get_datagov_key())


def is_supabase_configured() -> bool:
    url = os.getenv("SUPABASE_URL") or ""
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_KEY")
        or os.getenv("SUPABASE_KEY")
        or ""
    )
    if not (url and key):
        try:
            from app.config import settings
            url = url or settings.supabase_url or ""
            key = key or settings.supabase_service_key or settings.supabase_anon_key or ""
        except Exception:
            pass
    clean_url = str(url).strip()
    clean_key = str(key).strip()
    if clean_url in ("your_url_here", "") or clean_key in ("your_key_here", ""):
        return False
    return bool(clean_url and clean_key)


def get_safe_integration_diagnostics() -> dict[str, Any]:
    from app.db import is_supabase_connected

    gemini_ok = is_gemini_configured()
    adzuna_ok = is_adzuna_configured()
    datagov_ok = is_datagov_configured()
    sb_configured = is_supabase_configured()
    sb_connected = is_supabase_connected()

    last_ai_error = None
    try:
        from ai.router import ai_router
        last_ai_error = ai_router.get_last_error_category()
    except Exception:
        pass

    workload_routing = {}
    for w in SUPPORTED_WORKLOADS:
        workload_routing[w] = {
            "configured_provider": get_workload_provider(w),
            "has_dedicated_key": bool(os.getenv(f"GEMINI_API_KEY_{w.upper()}")),
            "effective_configured": is_workload_ai_configured(w),
            "fallback_mechanism": "deterministic_fallback",
        }

    adz_status_raw = "UNKNOWN"
    dg_status_raw = "UNKNOWN"
    try:
        from app.ingestion.source_orchestrator import source_orchestrator, SOURCE_ADZUNA, SOURCE_DATAGOV
        adz_status_raw = source_orchestrator._source_statuses.get(SOURCE_ADZUNA, "UNKNOWN")
        dg_status_raw = source_orchestrator._source_statuses.get(SOURCE_DATAGOV, "UNKNOWN")
    except Exception:
        pass

    if not adzuna_ok:
        adz_status = "NOT_CONFIGURED"
        adz_avail = "UNAVAILABLE"
        adz_prov = "NOT_CONFIGURED"
    elif adz_status_raw == "ONLINE":
        adz_status = "ONLINE"
        adz_avail = "AVAILABLE"
        adz_prov = "LIVE_API"
    elif adz_status_raw in ("UNAVAILABLE", "VALIDATION_FAILED"):
        adz_status = adz_status_raw
        adz_avail = "UNAVAILABLE"
        adz_prov = adz_status_raw
    else:
        adz_status = "CONFIGURED"
        adz_avail = "UNKNOWN"
        adz_prov = "CONFIGURED"

    if not datagov_ok:
        dg_status = "NOT_CONFIGURED"
        dg_avail = "UNAVAILABLE"
        dg_prov = "NOT_CONFIGURED"
    elif dg_status_raw == "ONLINE":
        dg_status = "ONLINE"
        dg_avail = "AVAILABLE"
        dg_prov = "LIVE_API"
    elif dg_status_raw in ("UNAVAILABLE", "VALIDATION_FAILED"):
        dg_status = dg_status_raw
        dg_avail = "UNAVAILABLE"
        dg_prov = dg_status_raw
    else:
        dg_status = "CONFIGURED"
        dg_avail = "UNKNOWN"
        dg_prov = "CONFIGURED"

    effective_ai_configured = gemini_ok or any(
        cfg.get("effective_configured") for cfg in workload_routing.values()
    )

    return {
        "status": "success",
        "timestamp": os.getenv("DIAGNOSTICS_TIMESTAMP", "live"),
        "ai": {
            "real_provider": "gemini",
            "model": "gemini-3.6-flash",
            "configured": effective_ai_configured,
            "available": effective_ai_configured,
            "fallback_mechanism": "deterministic_fallback",
            "fallback_available": True,
            "last_failure_category": last_ai_error or ("NONE" if effective_ai_configured else "NOT_CONFIGURED"),
            "supported_tasks": list(SUPPORTED_WORKLOADS),
            "workload_routing": workload_routing,
        },
        "external_data": {
            "adzuna_jobs": {
                "provider": "Adzuna India Jobs API",
                "source_name": "ADZUNA_API",
                "configured": adzuna_ok,
                "status": adz_status,
                "availability": adz_avail,
                "provenance": adz_prov,
                "fallback_available": False,
            },
            "datagov_schemes": {
                "provider": "data.gov.in (OGD Platform India)",
                "source_name": "OGD_DATAGOV_IN",
                "configured": datagov_ok,
                "status": dg_status,
                "availability": dg_avail,
                "provenance": dg_prov,
                "fallback_available": False,
            },
            "supabase_database": {
                "provider": "Supabase Managed PostgreSQL",
                "configured": sb_configured,
                "connected": sb_connected,
                "status": "CONNECTED" if sb_connected else ("DISCONNECTED" if sb_configured else "NOT_CONFIGURED"),
                "authoritative": True,
                "fallback_available": False,
            },
        },
    }
