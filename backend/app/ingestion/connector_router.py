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

        if not adzuna_ok:
            adz_status = "NOT_CONFIGURED"
            adz_avail = "UNAVAILABLE"
            adz_prov = "NOT_CONFIGURED"
            adz_fresh = "STALE"
        elif self._adzuna_status == "ONLINE":
            adz_status = "ONLINE"
            adz_avail = "AVAILABLE"
            adz_prov = "LIVE_API"
            adz_fresh = "LIVE"
        elif self._adzuna_status in ("UNAVAILABLE", "FAILED"):
            adz_status = self._adzuna_status
            adz_avail = "UNAVAILABLE"
            adz_prov = self._adzuna_status
            adz_fresh = "STALE"
        else:
            adz_status = "CONFIGURED"
            adz_avail = "UNKNOWN"
            adz_prov = "CONFIGURED"
            adz_fresh = "UNKNOWN"

        if not datagov_ok:
            dg_status = "NOT_CONFIGURED"
            dg_avail = "UNAVAILABLE"
            dg_prov = "NOT_CONFIGURED"
            dg_fresh = "STALE"
        elif self._datagov_status == "ONLINE":
            dg_status = "ONLINE"
            dg_avail = "AVAILABLE"
            dg_prov = "LIVE_API"
            dg_fresh = "LIVE"
        elif self._datagov_status in ("UNAVAILABLE", "FAILED"):
            dg_status = self._datagov_status
            dg_avail = "UNAVAILABLE"
            dg_prov = self._datagov_status
            dg_fresh = "STALE"
        else:
            dg_status = "CONFIGURED"
            dg_avail = "UNKNOWN"
            dg_prov = "CONFIGURED"
            dg_fresh = "UNKNOWN"

        return {
            "connectors": [
                {
                    "provider_name": "Adzuna India Jobs API",
                    "source_name": "ADZUNA_API",
                    "configured": adzuna_ok,
                    "status": adz_status,
                    "availability": adz_avail,
                    "last_failure_category": self._last_adzuna_error,
                    "freshness": adz_fresh,
                    "provenance": adz_prov,
                    "timeout_seconds": self._adzuna.timeout_seconds,
                    "max_retries": self._adzuna.max_retries,
                    "fallback_available": False,
                },
                {
                    "provider_name": "data.gov.in (OGD Platform India)",
                    "source_name": "OGD_DATAGOV_IN",
                    "configured": datagov_ok,
                    "status": dg_status,
                    "availability": dg_avail,
                    "last_failure_category": self._last_datagov_error,
                    "freshness": dg_fresh,
                    "provenance": dg_prov,
                    "timeout_seconds": self._datagov.timeout_seconds,
                    "max_retries": self._datagov.max_retries,
                    "fallback_available": False,
                },
            ],
            "total_connectors": 2,
            "timestamp": time.time(),
        }


connector_registry = ExternalConnectorRegistry()
