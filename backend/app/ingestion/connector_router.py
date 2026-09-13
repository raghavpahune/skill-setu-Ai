import os
import time
import logging
from typing import Any
from app.core.providers_config import is_adzuna_configured, is_datagov_configured
from app.ingestion.adzuna_connector import AdzunaConnector
from app.ingestion.datagov_connector import DataGovConnector

logger = logging.getLogger("skillsetu.ingestion.router")


class ExternalConnectorRegistry:
    def __init__(self):
        self._adzuna = AdzunaConnector()
        self._datagov = DataGovConnector()
        self._health_cache: dict[str, dict[str, Any]] = {}

    @property
    def adzuna(self) -> AdzunaConnector:
        return self._adzuna

    @property
    def datagov(self) -> DataGovConnector:
        return self._datagov

    def fetch_jobs_with_fallback(self, limit: int = 25, is_demo: bool | None = None) -> list[dict[str, Any]]:
        from app.db import get_demo
        from app.core.data_mode import is_explicit_demo_mode

        if is_explicit_demo_mode(is_demo):
            return get_demo("jobs")[:limit]

        if is_adzuna_configured():
            try:
                jobs = self._adzuna.fetch_raw(page=1, results_per_page=limit)
                if jobs:
                    return jobs
            except Exception as e:
                logger.warning(f"[ConnectorRouter] Live Adzuna fetch failed, falling back: {e}")

        try:
            from app.repositories import supabase_repository
            db_jobs = supabase_repository.list_jobs(limit=limit)
            if db_jobs:
                return db_jobs
        except Exception:
            pass

        return get_demo("jobs")[:limit]

    def fetch_schemes_with_fallback(self, limit: int = 25, is_demo: bool | None = None) -> list[dict[str, Any]]:
        from app.db import get_demo
        from app.core.data_mode import is_explicit_demo_mode

        if is_explicit_demo_mode(is_demo):
            return get_demo("schemes")[:limit]

        if is_datagov_configured():
            try:
                schemes = self._datagov.fetch_schemes(limit=limit)
                if schemes:
                    return schemes
            except Exception as e:
                logger.warning(f"[ConnectorRouter] Live DataGov fetch failed, falling back: {e}")

        try:
            from app.repositories import supabase_repository
            db_schemes = supabase_repository.list_schemes(limit=limit)
            if db_schemes:
                return db_schemes
        except Exception:
            pass

        return get_demo("schemes")[:limit]

    def get_diagnostics(self) -> dict[str, Any]:
        adzuna_ok = is_adzuna_configured()
        datagov_ok = is_datagov_configured()

        return {
            "connectors": [
                {
                    "provider_name": "Adzuna India",
                    "source_name": "ADZUNA_API",
                    "configured": adzuna_ok,
                    "status": "ONLINE" if adzuna_ok else "NOT_CONFIGURED",
                    "timeout_seconds": self._adzuna.timeout_seconds,
                    "max_retries": self._adzuna.max_retries,
                    "fallback_available": True,
                    "fallback_source": "VERIFIED_SNAPSHOT",
                },
                {
                    "provider_name": "data.gov.in (OGD Platform India)",
                    "source_name": "OGD_DATAGOV_IN",
                    "configured": datagov_ok,
                    "status": "ONLINE" if datagov_ok else "NOT_CONFIGURED",
                    "timeout_seconds": self._datagov.timeout_seconds,
                    "max_retries": self._datagov.max_retries,
                    "fallback_available": True,
                    "fallback_source": "VERIFIED_SNAPSHOT",
                },
            ],
            "total_connectors": 2,
            "timestamp": time.time(),
        }


connector_registry = ExternalConnectorRegistry()
