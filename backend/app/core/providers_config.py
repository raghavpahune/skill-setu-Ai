import os
from typing import Any
from pydantic import BaseModel, Field


class ServiceCredentials(BaseModel):
    configured: bool
    service_name: str
    status: str = "UNKNOWN"
    fallback_available: bool = True
    details: dict[str, Any] = Field(default_factory=dict)


def get_gemini_key() -> str:
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
    if not key:
        try:
            from app.config import settings
            key = settings.gemini_api_key or ""
        except Exception:
            pass
    return str(key).strip().strip("'\"")


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
    key = get_gemini_key()
    return bool(key and key != "your_key_here")


def is_adzuna_configured() -> bool:
    app_id, app_key = get_adzuna_credentials()
    return bool(app_id and app_key)


def is_datagov_configured() -> bool:
    return bool(get_datagov_key())


def get_safe_integration_diagnostics() -> dict[str, Any]:
    from app.db import is_supabase_connected, list_users

    gemini_ok = is_gemini_configured()
    adzuna_ok = is_adzuna_configured()
    datagov_ok = is_datagov_configured()
    sb_connected = is_supabase_connected()

    last_ai_error = None
    try:
        from ai.router import ai_router
        last_ai_error = ai_router.get_last_error_category()
    except Exception:
        pass

    users_count = len(list_users())

    return {
        "status": "success",
        "timestamp": os.getenv("DIAGNOSTICS_TIMESTAMP", "live"),
        "ai": {
            "provider": "gemini",
            "model": "gemini-3.6-flash",
            "configured": gemini_ok,
            "available": gemini_ok,
            "fallback_available": True,
            "last_failure_category": last_ai_error or ("NONE" if gemini_ok else "NOT_CONFIGURED"),
            "supported_tasks": [
                "career_copilot",
                "skill_gap_analysis",
                "learning_roadmap",
                "employee_transition",
                "employer_candidate_analysis",
                "institute_curriculum_analysis",
                "government_policy_analysis",
                "data_insight_generation",
            ],
        },
        "external_data": {
            "adzuna_jobs": {
                "provider": "Adzuna India Jobs API",
                "source_name": "ADZUNA_API",
                "configured": adzuna_ok,
                "status": "ONLINE" if adzuna_ok else "NOT_CONFIGURED",
                "fallback_available": True,
                "fallback_source": "VERIFIED_SNAPSHOT",
            },
            "datagov_schemes": {
                "provider": "data.gov.in (OGD Platform India)",
                "source_name": "OGD_DATAGOV_IN",
                "configured": datagov_ok,
                "status": "ONLINE" if datagov_ok else "NOT_CONFIGURED",
                "fallback_available": True,
                "fallback_source": "VERIFIED_SNAPSHOT",
            },
            "supabase_database": {
                "provider": "Supabase Managed PostgreSQL",
                "configured": bool(os.getenv("SUPABASE_URL")),
                "connected": sb_connected,
                "status": "CONNECTED" if sb_connected else "STANDALONE_CACHE",
                "users_in_memory": users_count,
            },
        },
    }
