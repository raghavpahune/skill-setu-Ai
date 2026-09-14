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
        self._adzuna_status = "IDLE"
        self._datagov_status = "IDLE"
        self._last_adzuna_error = "NONE"
        self._last_datagov_error = "NONE"

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
            raw_demo = get_demo("jobs")[:limit]
            stamped = []
            for item in raw_demo:
                cloned = dict(item)
                cloned["source"] = "DEMO_SYNTHETIC"
                cloned["source_type"] = "DEMO_SYNTHETIC"
                cloned["is_demo"] = True
                stamped.append(cloned)
            return stamped

        if not is_adzuna_configured():
            self._adzuna_status = "NOT_CONFIGURED"
            self._last_adzuna_error = "NOT_CONFIGURED"
            return []

        try:
            jobs = self._adzuna.fetch_raw(page=1, results_per_page=limit, is_demo=False)
            if jobs:
                self._adzuna_status = "ONLINE"
                self._last_adzuna_error = "NONE"
                stamped = []
                for j in jobs:
                    cloned = dict(j)
                    cloned["source"] = "ADZUNA_API"
                    cloned["source_type"] = "LIVE_API"
                    cloned["is_demo"] = False
                    stamped.append(cloned)
                return stamped
            self._adzuna_status = "UNAVAILABLE"
            self._last_adzuna_error = "NO_DATA_RETURNED"
            return []
        except Exception as e:
            self._adzuna_status = "UNAVAILABLE"
            self._last_adzuna_error = "CONNECTOR_UNAVAILABLE"
            logger.warning(f"[ConnectorRouter] Live Adzuna fetch failed: {e}")
            return []

    def fetch_schemes_with_fallback(self, limit: int = 25, is_demo: bool | None = None) -> list[dict[str, Any]]:
        from app.db import get_demo
        from app.core.data_mode import is_explicit_demo_mode

        if is_explicit_demo_mode(is_demo):
            raw_demo = get_demo("schemes")[:limit]
            stamped = []
            for item in raw_demo:
                cloned = dict(item)
                cloned["source"] = "DEMO_SYNTHETIC"
                cloned["source_type"] = "DEMO_SYNTHETIC"
                cloned["is_demo"] = True
                stamped.append(cloned)
            return stamped

        if not is_datagov_configured():
            self._datagov_status = "NOT_CONFIGURED"
            self._last_datagov_error = "NOT_CONFIGURED"
            return []

        try:
            schemes = self._datagov.fetch_raw(limit=limit, is_demo=False)
            if schemes:
                self._datagov_status = "ONLINE"
                self._last_datagov_error = "NONE"
                stamped = []
                for s in schemes:
                    cloned = dict(s)
                    cloned["source"] = "OGD_DATAGOV_IN"
                    cloned["source_type"] = "LIVE_API"
                    cloned["is_demo"] = False
                    stamped.append(cloned)
                return stamped
            self._datagov_status = "UNAVAILABLE"
            self._last_datagov_error = "NO_DATA_RETURNED"
            return []
        except Exception as e:
            self._datagov_status = "UNAVAILABLE"
            self._last_datagov_error = "CONNECTOR_UNAVAILABLE"
            logger.warning(f"[ConnectorRouter] Live DataGov fetch failed: {e}")
            return []

    def get_diagnostics(self) -> dict[str, Any]:
        adzuna_ok = is_adzuna_configured()
        datagov_ok = is_datagov_configured()

        return {
            "connectors": [
                {
                    "provider_name": "Adzuna India Jobs API",
                    "source_name": "ADZUNA_API",
                    "configured": adzuna_ok,
                    "status": "ONLINE" if (adzuna_ok and self._adzuna_status == "ONLINE") else ("NOT_CONFIGURED" if not adzuna_ok else self._adzuna_status),
                    "availability": "AVAILABLE" if (adzuna_ok and self._adzuna_status != "UNAVAILABLE") else "UNAVAILABLE",
                    "last_failure_category": self._last_adzuna_error,
                    "freshness": "LIVE" if (adzuna_ok and self._adzuna_status == "ONLINE") else "STALE",
                    "provenance": "LIVE_API" if adzuna_ok else "NOT_CONFIGURED",
                    "timeout_seconds": self._adzuna.timeout_seconds,
                    "max_retries": self._adzuna.max_retries,
                    "fallback_available": False,
                },
                {
                    "provider_name": "data.gov.in (OGD Platform India)",
                    "source_name": "OGD_DATAGOV_IN",
                    "configured": datagov_ok,
                    "status": "ONLINE" if (datagov_ok and self._datagov_status == "ONLINE") else ("NOT_CONFIGURED" if not datagov_ok else self._datagov_status),
                    "availability": "AVAILABLE" if (datagov_ok and self._datagov_status != "UNAVAILABLE") else "UNAVAILABLE",
                    "last_failure_category": self._last_datagov_error,
                    "freshness": "LIVE" if (datagov_ok and self._datagov_status == "ONLINE") else "STALE",
                    "provenance": "LIVE_API" if datagov_ok else "NOT_CONFIGURED",
                    "timeout_seconds": self._datagov.timeout_seconds,
                    "max_retries": self._datagov.max_retries,
                    "fallback_available": False,
                },
            ],
            "total_connectors": 2,
            "timestamp": time.time(),
        }


connector_registry = ExternalConnectorRegistry()
