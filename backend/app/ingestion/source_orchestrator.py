import os
import time
import datetime
import logging
from typing import Any
from pydantic import BaseModel, Field

from app.core.providers_config import (
    is_adzuna_configured,
    is_datagov_configured,
    is_supabase_configured,
    get_adzuna_credentials,
    get_datagov_key,
)
from app.core.data_mode import is_explicit_demo_mode
from app.ingestion.base_adapter import (
    SOURCE_TYPE_LIVE_API,
    SOURCE_TYPE_VERIFIED_SNAPSHOT,
    SOURCE_TYPE_SANDBOX_SIMULATION,
    SOURCE_TYPE_DEMO_SYNTHETIC,
    normalize_maharashtra_district,
    compute_content_hash,
    compute_freshness,
)
from app.ingestion.adzuna_connector import AdzunaConnector
from app.ingestion.datagov_connector import (
    DataGovConnector,
    RESOURCE_SCHOLARSHIP_ALLOCATION,
)

logger = logging.getLogger("skillsetu.ingestion.orchestrator")

SOURCE_ADZUNA = "adzuna"
SOURCE_DATAGOV = "data_gov_in"
SOURCE_SUPABASE = "supabase"
SOURCE_LOCAL_DEMO = "local_demo"

WORKLOAD_JOBS = "jobs"
WORKLOAD_LABOUR_MARKET_DEMAND = "labour_market_demand"
WORKLOAD_GOVERNMENT_SCHEMES = "government_schemes"
WORKLOAD_GOVERNMENT_DATASETS = "government_datasets"
WORKLOAD_APP_DATA = "app_data"
WORKLOAD_EMPLOYER_DEMANDS = "employer_demands"
WORKLOAD_STUDENT_PROFILES = "student_profiles"
WORKLOAD_STUDENT_ASSESSMENTS = "student_assessments"
WORKLOAD_INDUSTRY_SIGNALS = "industry_signals"
WORKLOAD_COURSES = "courses"
WORKLOAD_SKILLS = "skills"

SIGNAL_TYPE_DEMAND_TRENDS = "demand_trends"
SIGNAL_TYPE_JOB_VOLUME = "job_volume"
SIGNAL_TYPE_SKILL_DEMAND = "skill_demand"
SIGNAL_TYPE_EMPLOYER_DEMAND = "employer_demand"
SIGNAL_TYPE_SECTOR_INDICATORS = "sector_indicators"
SIGNAL_TYPE_GOVERNMENT_INDICATORS = "government_indicators"

SUPPORTED_SIGNAL_TYPES = [
    SIGNAL_TYPE_DEMAND_TRENDS,
    SIGNAL_TYPE_JOB_VOLUME,
    SIGNAL_TYPE_SKILL_DEMAND,
    SIGNAL_TYPE_EMPLOYER_DEMAND,
    SIGNAL_TYPE_SECTOR_INDICATORS,
    SIGNAL_TYPE_GOVERNMENT_INDICATORS,
]


class ExternalSourceSpec(BaseModel):
    source_id: str
    display_name: str
    supported_workloads: list[str]
    required_credentials: list[str]
    authoritative: bool
    expected_provenance: str
    timeout_seconds: float
    validation_requirements: list[str]
    freshness_expectation: str


class ExternalDataResponse(BaseModel):
    source: str
    workload: str
    status: str
    provenance: str
    records: list[dict[str, Any]] = Field(default_factory=list)
    records_count: int = 0
    fetched_at: str | None = None
    freshness_status: str = "UNKNOWN"
    error: str | None = None
    authoritative: bool = False
    is_demo: bool = False


SOURCE_REGISTRY: dict[str, ExternalSourceSpec] = {
    SOURCE_ADZUNA: ExternalSourceSpec(
        source_id=SOURCE_ADZUNA,
        display_name="Adzuna India Jobs Feed",
        supported_workloads=[WORKLOAD_JOBS, WORKLOAD_LABOUR_MARKET_DEMAND, SIGNAL_TYPE_JOB_VOLUME],
        required_credentials=["ADZUNA_APP_ID", "ADZUNA_APP_KEY"],
        authoritative=False,
        expected_provenance=SOURCE_TYPE_LIVE_API,
        timeout_seconds=25.0,
        validation_requirements=["id", "title_min_length_2", "company", "district", "non_negative_vacancies"],
        freshness_expectation="LIVE_FEED",
    ),
    SOURCE_DATAGOV: ExternalSourceSpec(
        source_id=SOURCE_DATAGOV,
        display_name="data.gov.in (OGD Platform India)",
        supported_workloads=[WORKLOAD_GOVERNMENT_SCHEMES, WORKLOAD_GOVERNMENT_DATASETS, SIGNAL_TYPE_GOVERNMENT_INDICATORS],
        required_credentials=["DATA_GOV_API_KEY"],
        authoritative=False,
        expected_provenance=SOURCE_TYPE_LIVE_API,
        timeout_seconds=30.0,
        validation_requirements=["id", "title_min_length_3", "department_or_company", "valid_provenance"],
        freshness_expectation="PORTAL_FEED",
    ),
    SOURCE_SUPABASE: ExternalSourceSpec(
        source_id=SOURCE_SUPABASE,
        display_name="Supabase Managed PostgreSQL",
        supported_workloads=[
            WORKLOAD_APP_DATA,
            WORKLOAD_EMPLOYER_DEMANDS,
            WORKLOAD_STUDENT_PROFILES,
            WORKLOAD_STUDENT_ASSESSMENTS,
            WORKLOAD_INDUSTRY_SIGNALS,
            WORKLOAD_COURSES,
            WORKLOAD_SKILLS,
            WORKLOAD_GOVERNMENT_SCHEMES,
            WORKLOAD_JOBS,
        ],
        required_credentials=["SUPABASE_URL", "SUPABASE_KEY"],
        authoritative=True,
        expected_provenance="VERIFIED",
        timeout_seconds=15.0,
        validation_requirements=["schema_type_match", "row_level_security", "authoritative_persistence"],
        freshness_expectation="SYSTEM_OF_RECORD",
    ),
    SOURCE_LOCAL_DEMO: ExternalSourceSpec(
        source_id=SOURCE_LOCAL_DEMO,
        display_name="SkillSetu Demonstration Baseline",
        supported_workloads=[
            WORKLOAD_JOBS,
            WORKLOAD_GOVERNMENT_SCHEMES,
            WORKLOAD_EMPLOYER_DEMANDS,
            WORKLOAD_STUDENT_PROFILES,
            WORKLOAD_STUDENT_ASSESSMENTS,
            WORKLOAD_COURSES,
            WORKLOAD_SKILLS,
        ],
        required_credentials=[],
        authoritative=False,
        expected_provenance=SOURCE_TYPE_DEMO_SYNTHETIC,
        timeout_seconds=1.0,
        validation_requirements=["is_demo_stamped", "source_demo_synthetic"],
        freshness_expectation="STATIC_BASELINE",
    ),
}


def resolve_source_for_workload(workload: str, requires_live: bool = True, is_demo: bool = False) -> str:
    if is_demo:
        return SOURCE_LOCAL_DEMO
    if requires_live:
        if workload in (WORKLOAD_JOBS, WORKLOAD_LABOUR_MARKET_DEMAND, SIGNAL_TYPE_JOB_VOLUME):
            return SOURCE_ADZUNA
        if workload in (WORKLOAD_GOVERNMENT_SCHEMES, WORKLOAD_GOVERNMENT_DATASETS, SIGNAL_TYPE_GOVERNMENT_INDICATORS):
            return SOURCE_DATAGOV
    return SOURCE_SUPABASE


def normalize_vacancies_count(val: Any) -> int:
    if val is None:
        return 1
    if isinstance(val, (int, float)):
        try:
            return max(1, int(val))
        except (ValueError, OverflowError):
            return 1
    if isinstance(val, str):
        cleaned = val.strip()
        if cleaned.isdigit():
            return max(1, int(cleaned))
    return 1


def validate_job_item(item: dict[str, Any]) -> tuple[bool, str | None, dict[str, Any] | None]:
    if not isinstance(item, dict):
        return False, "Record is not a dictionary", None
    raw_id = item.get("id") or item.get("external_id")
    if not raw_id or str(raw_id).strip() == "":
        return False, "Missing required job ID", None
    title = str(item.get("title") or "").strip()
    if len(title) < 2:
        return False, "Job title fails minimum length (2)", None

    company_val = item.get("company")
    if isinstance(company_val, dict):
        company_name = str(company_val.get("display_name") or company_val.get("name") or "Employer").strip()
    else:
        company_name = str(company_val or "Employer").strip()

    loc_val = item.get("location")
    if isinstance(loc_val, dict):
        display_loc = str(loc_val.get("display_name") or "")
        area_parts = [str(p) for p in (loc_val.get("area") or []) if p]
        raw_loc = " ".join([display_loc] + area_parts)
    else:
        raw_loc = str(item.get("district") or item.get("location") or "")
    canonical_district = normalize_maharashtra_district(raw_loc, default="Pune")

    cleaned = dict(item)
    cleaned["id"] = str(raw_id)
    cleaned["title"] = title
    cleaned["company"] = company_name
    cleaned["district"] = canonical_district
    cleaned["vacancies_count"] = normalize_vacancies_count(item.get("vacancies_count"))
    cleaned["source"] = item.get("source") or "ADZUNA_API"
    cleaned["source_type"] = item.get("source_type") or SOURCE_TYPE_LIVE_API
    cleaned["is_demo"] = False
    return True, None, cleaned


def validate_scheme_item(item: dict[str, Any]) -> tuple[bool, str | None, dict[str, Any] | None]:
    if not isinstance(item, dict):
        return False, "Record is not a dictionary", None
    raw_id = item.get("id") or item.get("external_id") or item.get("document_id") or item.get("_id")
    if not raw_id or str(raw_id).strip() == "":
        return False, "Missing required scheme ID", None
    raw_title = item.get("title") or item.get("name") or item.get("scheme_name")
    if not raw_title and (item.get("_year") or item.get("financial_year")):
        raw_title = f"National Scholarship Fund ({item.get('_year') or item.get('financial_year')})"
    title = str(raw_title or "").strip()
    if len(title) < 3:
        return False, "Scheme title fails minimum length (3)", None

    cleaned = dict(item)
    cleaned["id"] = str(raw_id)
    cleaned["title"] = title
    cleaned["source"] = item.get("source") or "OGD_DATAGOV_IN"
    cleaned["source_type"] = item.get("source_type") or SOURCE_TYPE_LIVE_API
    cleaned["is_demo"] = False
    return True, None, cleaned


def create_industry_signal_contract(source: str, signal_type: str, raw_data: dict[str, Any]) -> dict[str, Any]:
    if signal_type not in SUPPORTED_SIGNAL_TYPES:
        raise ValueError(f"Unsupported signal_type '{signal_type}'. Must be one of: {SUPPORTED_SIGNAL_TYPES}")
    title = str(raw_data.get("title") or "").strip()
    if len(title) < 5:
        raise ValueError("Industry signal title must have at least 5 characters.")
    description = str(raw_data.get("description") or "").strip()
    if len(description) < 15:
        raise ValueError("Industry signal description must have at least 15 characters.")
    source_url = str(raw_data.get("source_url") or "").strip()
    if len(source_url) < 5:
        raise ValueError("Industry signal source_url must have at least 5 characters.")

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    pub_at = raw_data.get("published_at") or now_iso
    content_hash = compute_content_hash(title, source, signal_type, pub_at)

    return {
        "title": title,
        "description": description,
        "signal_type": signal_type,
        "category": str(raw_data.get("category") or "INDUSTRY_DEMAND").upper().replace(" ", "_"),
        "industry": str(raw_data.get("industry") or "Cross-Sector & Emerging Tech").strip(),
        "skills": list(raw_data.get("skills") or []),
        "tools": list(raw_data.get("tools") or []),
        "source_name": str(raw_data.get("source_name") or source).strip(),
        "source_url": source_url,
        "source_type": SOURCE_TYPE_LIVE_API if not raw_data.get("is_demo") else SOURCE_TYPE_DEMO_SYNTHETIC,
        "provenance": SOURCE_TYPE_LIVE_API if not raw_data.get("is_demo") else SOURCE_TYPE_DEMO_SYNTHETIC,
        "published_at": pub_at,
        "fetched_at": now_iso,
        "content_hash": content_hash,
        "is_active": bool(raw_data.get("is_active", True)),
        "validation_status": str(raw_data.get("validation_status") or "APPROVED"),
        "is_demo": bool(raw_data.get("is_demo", False)),
    }


class SourceOrchestrator:
    def __init__(
        self,
        adzuna_connector: AdzunaConnector | None = None,
        datagov_connector: DataGovConnector | None = None,
    ):
        self._adzuna_connector = adzuna_connector or AdzunaConnector()
        self._datagov_connector = datagov_connector or DataGovConnector()
        self._source_statuses: dict[str, str] = {
            SOURCE_ADZUNA: "IDLE",
            SOURCE_DATAGOV: "IDLE",
            SOURCE_SUPABASE: "IDLE",
        }
        self._last_errors: dict[str, str] = {
            SOURCE_ADZUNA: "NONE",
            SOURCE_DATAGOV: "NONE",
            SOURCE_SUPABASE: "NONE",
        }

    def get_source_spec(self, source_id: str) -> ExternalSourceSpec | None:
        return SOURCE_REGISTRY.get(source_id)

    def list_sources(self) -> list[ExternalSourceSpec]:
        return list(SOURCE_REGISTRY.values())

    def is_source_configured(self, source_id: str) -> bool:
        if source_id == SOURCE_ADZUNA:
            return bool((self._adzuna_connector and self._adzuna_connector.has_credentials) or is_adzuna_configured())
        if source_id == SOURCE_DATAGOV:
            return bool((self._datagov_connector and self._datagov_connector.has_api_key) or is_datagov_configured())
        if source_id == SOURCE_SUPABASE:
            return is_supabase_configured()
        if source_id == SOURCE_LOCAL_DEMO:
            return True
        return False

    def fetch_data(
        self,
        workload: str,
        limit: int = 25,
        is_demo: bool | None = None,
        requires_live: bool = True,
        **kwargs: Any,
    ) -> ExternalDataResponse:
        from app.db import get_demo

        explicit_demo = is_explicit_demo_mode(is_demo)

        if explicit_demo:
            source_id = SOURCE_LOCAL_DEMO
            demo_key = "jobs" if workload in (WORKLOAD_JOBS, WORKLOAD_LABOUR_MARKET_DEMAND, SIGNAL_TYPE_JOB_VOLUME) else "schemes"
            raw_records = get_demo(demo_key)[:limit]
            stamped = []
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            for r in raw_records:
                cloned = dict(r)
                cloned["source"] = "DEMO_SYNTHETIC"
                cloned["source_type"] = SOURCE_TYPE_DEMO_SYNTHETIC
                cloned["provenance"] = SOURCE_TYPE_DEMO_SYNTHETIC
                cloned["is_demo"] = True
                cloned["fetched_at"] = now_iso
                cloned["freshness_status"] = "STATIC_BASELINE"
                stamped.append(cloned)
            return ExternalDataResponse(
                source=source_id,
                workload=workload,
                status="SUCCESS",
                provenance=SOURCE_TYPE_DEMO_SYNTHETIC,
                records=stamped,
                records_count=len(stamped),
                fetched_at=now_iso,
                freshness_status="STATIC_BASELINE",
                error=None,
                authoritative=False,
                is_demo=True,
            )

        source_id = resolve_source_for_workload(workload, requires_live=requires_live, is_demo=False)
        spec = SOURCE_REGISTRY.get(source_id)
        authoritative = spec.authoritative if spec else False

        if not self.is_source_configured(source_id):
            self._source_statuses[source_id] = "NOT_CONFIGURED"
            self._last_errors[source_id] = "CREDENTIALS_MISSING"
            return ExternalDataResponse(
                source=source_id,
                workload=workload,
                status="NOT_CONFIGURED",
                provenance="NOT_CONFIGURED",
                records=[],
                records_count=0,
                fetched_at=None,
                freshness_status="UNKNOWN",
                error=f"Source '{source_id}' credentials are not configured in production environment.",
                authoritative=authoritative,
                is_demo=False,
            )

        fetch_start = time.perf_counter()
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        try:
            if source_id == SOURCE_ADZUNA:
                raw_items = self._adzuna_connector.fetch_raw(
                    page=kwargs.get("page", 1),
                    results_per_page=limit,
                    what=kwargs.get("what", "engineer OR developer OR technician"),
                    where=kwargs.get("where", "Maharashtra"),
                    is_demo=False,
                )
                if not raw_items:
                    self._source_statuses[source_id] = "UNAVAILABLE"
                    self._last_errors[source_id] = "EMPTY_OR_FAILED_UPSTREAM"
                    return ExternalDataResponse(
                        source=source_id,
                        workload=workload,
                        status="UNAVAILABLE",
                        provenance="UNAVAILABLE",
                        records=[],
                        records_count=0,
                        fetched_at=now_iso,
                        freshness_status="UNKNOWN",
                        error="Adzuna upstream returned empty result or failed connection.",
                        authoritative=False,
                        is_demo=False,
                    )
                validated_records = []
                for item in raw_items:
                    try:
                        ok, err, valid_record = validate_job_item(item)
                        if ok and valid_record:
                            valid_record["fetched_at"] = now_iso
                            valid_record["freshness_status"] = compute_freshness(
                                published_at=valid_record.get("created"),
                                last_seen_at=now_iso,
                            )
                            validated_records.append(valid_record)
                    except Exception as item_err:
                        logger.warning(f"[SourceOrchestrator] Discarding malformed job item: {item_err}")

                if not validated_records:
                    self._source_statuses[source_id] = "VALIDATION_FAILED"
                    self._last_errors[source_id] = "VALIDATION_FAILED"
                    return ExternalDataResponse(
                        source=source_id,
                        workload=workload,
                        status="VALIDATION_FAILED",
                        provenance="VALIDATION_FAILED",
                        records=[],
                        records_count=0,
                        fetched_at=now_iso,
                        freshness_status="UNKNOWN",
                        error="All records failed schema validation",
                        authoritative=False,
                        is_demo=False,
                    )

                self._source_statuses[source_id] = "ONLINE"
                self._last_errors[source_id] = "NONE"
                return ExternalDataResponse(
                    source=source_id,
                    workload=workload,
                    status="SUCCESS",
                    provenance=SOURCE_TYPE_LIVE_API,
                    records=validated_records,
                    records_count=len(validated_records),
                    fetched_at=now_iso,
                    freshness_status="LIVE",
                    error=None,
                    authoritative=False,
                    is_demo=False,
                )

            elif source_id == SOURCE_DATAGOV:
                raw_items = self._datagov_connector.fetch_raw(
                    limit=limit,
                    offset=kwargs.get("offset", 0),
                    is_demo=False,
                    resource_id=kwargs.get("resource_id", RESOURCE_SCHOLARSHIP_ALLOCATION),
                )
                if not raw_items:
                    self._source_statuses[source_id] = "UNAVAILABLE"
                    self._last_errors[source_id] = "EMPTY_OR_FAILED_UPSTREAM"
                    return ExternalDataResponse(
                        source=source_id,
                        workload=workload,
                        status="UNAVAILABLE",
                        provenance="UNAVAILABLE",
                        records=[],
                        records_count=0,
                        fetched_at=now_iso,
                        freshness_status="UNKNOWN",
                        error="data.gov.in upstream returned empty result or failed connection.",
                        authoritative=False,
                        is_demo=False,
                    )

                try:
                    transformed = self._datagov_connector.validate_and_transform(
                        raw_items,
                        resource_type=kwargs.get("resource_type", "scholarship"),
                        resource_id=kwargs.get("resource_id", RESOURCE_SCHOLARSHIP_ALLOCATION),
                    )
                except Exception as transform_err:
                    logger.warning(f"[SourceOrchestrator] DataGov transformation error: {transform_err}")
                    self._source_statuses[source_id] = "VALIDATION_FAILED"
                    self._last_errors[source_id] = "TRANSFORMATION_FAILED"
                    return ExternalDataResponse(
                        source=source_id,
                        workload=workload,
                        status="VALIDATION_FAILED",
                        provenance="VALIDATION_FAILED",
                        records=[],
                        records_count=0,
                        fetched_at=now_iso,
                        freshness_status="UNKNOWN",
                        error=f"data.gov.in transformation failed: {transform_err}",
                        authoritative=False,
                        is_demo=False,
                    )

                if not transformed:
                    self._source_statuses[source_id] = "VALIDATION_FAILED"
                    self._last_errors[source_id] = "TRANSFORMATION_EMPTY"
                    return ExternalDataResponse(
                        source=source_id,
                        workload=workload,
                        status="VALIDATION_FAILED",
                        provenance="VALIDATION_FAILED",
                        records=[],
                        records_count=0,
                        fetched_at=now_iso,
                        freshness_status="UNKNOWN",
                        error="data.gov.in transformation returned no valid records for raw input.",
                        authoritative=False,
                        is_demo=False,
                    )

                is_opportunity_resource = kwargs.get("resource_type") in ("naps", "pmkvy")
                validated_records = []
                for item in transformed:
                    try:
                        if is_opportunity_resource:
                            ok, err, valid_record = validate_job_item(item)
                        else:
                            ok, err, valid_record = validate_scheme_item(item)
                        if ok and valid_record:
                            valid_record["fetched_at"] = now_iso
                            valid_record["freshness_status"] = compute_freshness(
                                published_at=valid_record.get("published_at"),
                                last_seen_at=now_iso,
                            )
                            validated_records.append(valid_record)
                    except Exception as item_err:
                        logger.warning(f"[SourceOrchestrator] Discarding malformed scheme item: {item_err}")

                if not validated_records:
                    self._source_statuses[source_id] = "VALIDATION_FAILED"
                    self._last_errors[source_id] = "VALIDATION_FAILED"
                    return ExternalDataResponse(
                        source=source_id,
                        workload=workload,
                        status="VALIDATION_FAILED",
                        provenance="VALIDATION_FAILED",
                        records=[],
                        records_count=0,
                        fetched_at=now_iso,
                        freshness_status="UNKNOWN",
                        error="All records failed schema validation",
                        authoritative=False,
                        is_demo=False,
                    )

                self._source_statuses[source_id] = "ONLINE"
                self._last_errors[source_id] = "NONE"
                return ExternalDataResponse(
                    source=source_id,
                    workload=workload,
                    status="SUCCESS",
                    provenance=SOURCE_TYPE_LIVE_API,
                    records=validated_records,
                    records_count=len(validated_records),
                    fetched_at=now_iso,
                    freshness_status="LIVE",
                    error=None,
                    authoritative=False,
                    is_demo=False,
                )

            else:
                from app.repositories import supabase_repository
                client = supabase_repository.get_client()

                records = []
                if workload == WORKLOAD_STUDENT_PROFILES:
                    records = supabase_repository.list_student_profiles()[:limit]
                elif workload == WORKLOAD_STUDENT_ASSESSMENTS:
                    records = supabase_repository.list_student_assessments(limit=limit)
                elif workload == WORKLOAD_EMPLOYER_DEMANDS:
                    records = supabase_repository.list_employer_demands(limit=limit)
                elif workload == WORKLOAD_COURSES:
                    records = supabase_repository.list_courses(limit=limit)
                elif workload == WORKLOAD_INDUSTRY_SIGNALS:
                    records = supabase_repository.list_industry_signals(limit=limit)
                elif workload == WORKLOAD_SKILLS:
                    records = supabase_repository.list_skills(limit=limit)
                elif workload == WORKLOAD_JOBS:
                    records = supabase_repository.list_jobs(limit=limit)
                elif workload == WORKLOAD_GOVERNMENT_SCHEMES:
                    records = supabase_repository.list_schemes(limit=limit)
                else:
                    self._source_statuses[SOURCE_SUPABASE] = "ONLINE"
                    self._last_errors[SOURCE_SUPABASE] = "NONE"
                    return ExternalDataResponse(
                        source=SOURCE_SUPABASE,
                        workload=workload,
                        status="UNSUPPORTED_WORKLOAD",
                        provenance="NOT_SUPPORTED",
                        records=[],
                        records_count=0,
                        fetched_at=now_iso,
                        freshness_status="UNKNOWN",
                        error=f"Workload '{workload}' is not supported by Supabase repository.",
                        authoritative=True,
                        is_demo=False,
                    )

                self._source_statuses[SOURCE_SUPABASE] = "ONLINE"
                self._last_errors[SOURCE_SUPABASE] = "NONE"
                return ExternalDataResponse(
                    source=SOURCE_SUPABASE,
                    workload=workload,
                    status="SUCCESS",
                    provenance="VERIFIED",
                    records=records,
                    records_count=len(records),
                    fetched_at=now_iso,
                    freshness_status="SYSTEM_OF_RECORD",
                    error=None,
                    authoritative=True,
                    is_demo=False,
                )

        except Exception as e:
            self._source_statuses[source_id] = "UNAVAILABLE"
            self._last_errors[source_id] = "UPSTREAM_EXCEPTION"
            logger.warning(f"[SourceOrchestrator] Upstream query failed for '{source_id}': {e}")
            return ExternalDataResponse(
                source=source_id,
                workload=workload,
                status="UNAVAILABLE",
                provenance="UNAVAILABLE",
                records=[],
                records_count=0,
                fetched_at=now_iso,
                freshness_status="UNKNOWN",
                error=f"Upstream exception occurred during fetch: {e}",
                authoritative=authoritative,
                is_demo=False,
            )

    def get_source_diagnostics(self) -> dict[str, Any]:
        sources_diag = []
        for src_id, spec in SOURCE_REGISTRY.items():
            configured = self.is_source_configured(src_id)
            current_status = self._source_statuses.get(src_id, "IDLE")
            if not configured and src_id != SOURCE_LOCAL_DEMO:
                display_status = "NOT_CONFIGURED"
                availability = "NOT_CONFIGURED"
            elif current_status == "ONLINE":
                display_status = "ONLINE"
                availability = "AVAILABLE"
            elif current_status in ("UNAVAILABLE", "VALIDATION_FAILED"):
                display_status = current_status
                availability = "UNAVAILABLE"
            elif src_id == SOURCE_LOCAL_DEMO:
                display_status = "ONLINE"
                availability = "AVAILABLE"
            else:
                display_status = "CONFIGURED" if configured else "NOT_CONFIGURED"
                availability = "UNKNOWN" if configured else "UNAVAILABLE"

            sources_diag.append({
                "source_id": spec.source_id,
                "display_name": spec.display_name,
                "supported_workloads": spec.supported_workloads,
                "required_credentials": spec.required_credentials,
                "configured": configured,
                "status": display_status,
                "availability": availability,
                "authoritative": spec.authoritative,
                "expected_provenance": spec.expected_provenance,
                "timeout_seconds": spec.timeout_seconds,
                "freshness_expectation": spec.freshness_expectation,
                "fallback_available": False if src_id != SOURCE_LOCAL_DEMO else True,
                "last_failure_category": self._last_errors.get(src_id, "NONE"),
            })

        return {
            "source_registry": sources_diag,
            "total_registered_sources": len(sources_diag),
            "timestamp": time.time(),
        }


source_orchestrator = SourceOrchestrator()
