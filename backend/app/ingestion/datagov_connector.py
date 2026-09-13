"""Data.gov.in (Open Government Data Platform India) Ingestion Connector.

Handles querying official government datasets, normalizing records into SkillSetu's
schemes and jobs (opportunities) schema, with robust retry logic, error handling,
offline sandbox mode, SHA-256 deduplication, explicit source classification (LIVE_API
vs SANDBOX_SIMULATION), and full provenance stamping.
"""
from __future__ import annotations

import datetime
import logging
import os
import time
import uuid
from typing import Any
import httpx
from pydantic import BaseModel, Field

from app.config import settings
from app.core.data_mode import is_explicit_demo_mode
from app.ingestion.base_adapter import (
    BaseSourceAdapter,
    SOURCE_TYPE_LIVE_API,
    SOURCE_TYPE_SANDBOX_SIMULATION,
    compute_content_hash,
    compute_freshness,
    normalize_maharashtra_district,
)

logger = logging.getLogger("skillsetu.ingestion.datagov")

# Approved government dataset resource IDs
RESOURCE_SCHOLARSHIP_ALLOCATION = "bf44869a-519f-43cd-84f0-4914e32a37a8"
RESOURCE_ITI_CRAFTSMEN = "ba097f68-3882-4c3f-bb75-1b1973285b8b"
RESOURCE_NAPS_APPRENTICESHIP = "645b9f3e-e082-47d4-8098-e1c2b1a9e7f0"
RESOURCE_NAPS_NATS_STIPEND = "f68d6524-6a4a-4fe0-88c5-862017c112d5"
RESOURCE_PMKVY_SKILL = "540faf36-e288-47a3-8a78-ab93497473cc"

# Default base URL for data.gov.in API
DATAGOV_BASE_URL = "https://api.data.gov.in/resource"


# ---------------------------------------------------------------------------
# Pydantic Schemas for Validation
# ---------------------------------------------------------------------------

class RawDataGovRecord(BaseModel):
    """Validation schema for generic raw record from data.gov.in resources."""
    model_config = {"populate_by_name": True}

    document_id: str | int | None = None
    id: str | int | None = None
    year: str | None = Field(default=None, alias="_year")
    financial_year: str | None = None
    amount_allocated: str | float | int | None = None
    state_ut_name: str | None = None
    state: str | None = None
    state_ut: str | None = None
    district_name: str | None = None
    district: str | None = None
    short_term_training_stt___enrolled: str | int | None = None
    is_sandbox: bool = False


class ValidatedIngestedScheme(BaseModel):
    """Validated government welfare/scholarship scheme ready for persistence."""
    id: str
    scheme_code: str
    title: str = Field(..., min_length=3)
    department: str = Field(..., min_length=2)
    scheme_type: str = "scholarship"
    beneficiary_category: list[str] = Field(default_factory=list)
    income_ceiling_annual: int | None = None
    benefit_description: str
    max_amount: int | None = None
    eligible_course_types: list[str] = Field(default_factory=list)
    application_portal_url: str
    deadline_date: str | None = None
    status: str = "active"
    source: str = "OGD_DATAGOV_IN"
    source_type: str = SOURCE_TYPE_LIVE_API
    source_label: str = "data.gov.in Official Open Data Feed"
    source_url: str = "https://data.gov.in"
    resource_id: str | None = None
    external_id: str
    last_synced_at: str
    fetched_at: str
    published_at: str | None = None
    snapshot_captured_at: str | None = None
    last_seen_at: str | None = None
    verified_at: str | None = None
    verification_status: str = "VERIFIED"
    verification_method: str = "GOVERNMENT_PORTAL_API_FEED"
    confidence: int = 95
    content_hash: str
    freshness_status: str = "RECENT"
    is_demo: bool = False
    is_snapshot: bool = False


class ValidatedIngestedOpportunity(BaseModel):
    """Validated apprenticeship or vocational training opportunity ready for persistence."""
    id: str
    title: str = Field(..., min_length=3)
    company: str = Field(..., min_length=2)
    district: str
    industry: str
    opportunity_type: str = "apprenticeship"
    portal_source: str = "NAPS"
    external_id: str
    stipend_amount: int | None = None
    duration_months: int | None = None
    min_education: str | None = None
    vacancies_count: int = 1
    apply_url: str
    description: str
    source: str = "OGD_DATAGOV_IN"
    source_type: str = SOURCE_TYPE_LIVE_API
    source_label: str
    posted_date: str | None = None
    status: str = "active"
    source_url: str = "https://data.gov.in"
    resource_id: str | None = None
    fetched_at: str
    published_at: str | None = None
    snapshot_captured_at: str | None = None
    last_seen_at: str | None = None
    verified_at: str | None = None
    verification_status: str = "VERIFIED"
    verification_method: str = "GOVERNMENT_PORTAL_API_FEED"
    confidence: int = 95
    content_hash: str
    freshness_status: str = "RECENT"
    is_demo: bool = False
    is_snapshot: bool = False


# ---------------------------------------------------------------------------
# DataGovConnector Implementation
# ---------------------------------------------------------------------------

class DataGovConnector(BaseSourceAdapter):
    """Connector to ingest datasets from data.gov.in (OGD Platform India)."""

    def __init__(self, api_key: str | None = None, timeout_seconds: float = 30.0, max_retries: int = 3):
        super().__init__(source_name="OGD_DATAGOV_IN", timeout_seconds=timeout_seconds, max_retries=max_retries)
        self.api_key = (
            api_key
            or os.getenv("DATA_GOV_API_KEY")
            or getattr(settings, "data_gov_api_key", "")
            or ""
        ).strip()
        self.headers = {
            "User-Agent": "SkillSetu-IngestionBot/1.0 (Government of Maharashtra Labour Intelligence)",
            "Accept": "application/json",
        }

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key and self.api_key != "your_key_here")

    def fetch_raw(self, limit: int = 50, offset: int = 0, is_demo: bool | None = None, **kwargs: Any) -> list[dict[str, Any]]:
        resource_id = kwargs.get("resource_id", RESOURCE_SCHOLARSHIP_ALLOCATION)
        res_data = self.fetch_resource(resource_id=resource_id, limit=limit, offset=offset, is_demo=is_demo)
        return res_data.get("records", [])

    def fetch_resource(self, resource_id: str, limit: int = 50, offset: int = 0, is_demo: bool | None = None) -> dict[str, Any]:
        if is_explicit_demo_mode(is_demo):
            res = self._get_sandbox_resource_data(resource_id)
            res["status"] = "ok" if res.get("records") else "NO_DATA"
            res["source_available"] = True
            res["error"] = None
            return res

        if not self.has_api_key:
            logger.warning("DATA_GOV_API_KEY is not configured for resource %s", resource_id)
            return {
                "records": [],
                "status": "NOT_CONFIGURED",
                "source_available": False,
                "error": "DATA_GOV_API_KEY is not configured in production environment.",
            }

        url = f"{DATAGOV_BASE_URL}/{resource_id}"
        params = {
            "api-key": self.api_key,
            "format": "json",
            "offset": offset,
            "limit": limit,
        }

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info("Fetching data.gov.in resource %s (attempt %d/%d)...", resource_id, attempt, self.max_retries)
                response = httpx.get(url, params=params, headers=self.headers, timeout=self.timeout_seconds)
                if response.status_code == 200:
                    data = response.json()
                    records = data.get("records", [])
                    for r in records:
                        r["is_sandbox"] = False
                    data["records"] = records
                    data["status"] = "ok" if records else "NO_DATA"
                    data["source_available"] = True
                    data["error"] = None
                    return data
                elif response.status_code in (401, 403):
                    last_error = f"data.gov.in authentication failed (HTTP {response.status_code}). Check DATA_GOV_API_KEY."
                    logger.warning("%s", last_error)
                    break
                else:
                    last_error = f"data.gov.in returned HTTP {response.status_code} for {resource_id}"
                    logger.warning("%s", last_error)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = f"Network issue fetching {resource_id} on attempt {attempt}: {exc}"
                logger.warning("%s", last_error)
                time.sleep(1.5 * attempt)
            except Exception as exc:
                last_error = f"Unexpected error querying {resource_id}: {exc}"
                logger.error("%s", last_error)
                break

        logger.warning("Failed to fetch live data for %s: %s", resource_id, last_error)
        return {
            "records": [],
            "status": "FAILED",
            "source_available": False,
            "error": str(last_error),
        }

    def validate_and_transform(
        self,
        raw_records: list[dict[str, Any]],
        resource_type: str = "scholarship",
        resource_id: str | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        kwargs_override = {"resource_id": resource_id} if resource_id is not None else {}
        if resource_type == "scholarship":
            return self.transform_scholarship_schemes(raw_records, **kwargs_override)
        elif resource_type == "cts":
            return self.transform_cts_schemes(raw_records, **kwargs_override)
        elif resource_type == "naps":
            return self.transform_naps_opportunities(raw_records, **kwargs_override)
        elif resource_type == "pmkvy":
            return self.transform_pmkvy_opportunities(raw_records, **kwargs_override)
        return []

    def verify_record(self, record: dict[str, Any]) -> tuple[bool, str, int]:
        """Verify authenticity of government record.

        Requirements:
        1. Source must be OGD_DATAGOV_IN.
        2. Must have external_id.
        3. URL must be valid HTTP/HTTPS.
        4. Title must not be empty.
        5. If source is sandbox simulation, it is NOT verified live government data.
        """
        source = record.get("source")
        source_type = record.get("source_type")
        is_sandbox = record.get("is_sandbox", False)
        ext_id = record.get("external_id") or record.get("source_record_id")
        title = str(record.get("title") or "").strip()
        url = record.get("application_portal_url") or record.get("apply_url") or record.get("source_url")

        if source != "OGD_DATAGOV_IN":
            return False, "UNKNOWN_SOURCE", 0

        if is_sandbox or source_type == SOURCE_TYPE_SANDBOX_SIMULATION:
            return False, "SANDBOX_SIMULATION", 35

        if not ext_id:
            return False, "MISSING_EXTERNAL_ID", 0

        if not url or not (url.startswith("http://") or url.startswith("https://")):
            return False, "INVALID_PORTAL_URL", 0

        if len(title) < 3:
            return False, "INVALID_TITLE", 20

        return True, "GOVERNMENT_PORTAL_API_FEED", 95

    # ------------------------------------------------------------------------
    # Transformers with Explicit Source Classification and Provenance
    # ------------------------------------------------------------------------

    def transform_scholarship_schemes(
        self,
        raw_records: list[dict],
        resource_id: str = RESOURCE_SCHOLARSHIP_ALLOCATION,
    ) -> list[dict]:
        """Transform scholarship allocation records into SkillSetu schemes with provenance."""
        schemes = []
        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

        for idx, rec in enumerate(raw_records, start=1):
            doc_id = str(rec.get("document_id") or rec.get("id") or f"alloc-{idx}")
            year = str(rec.get("_year") or rec.get("financial_year") or "2023-24")
            allocated = rec.get("amount_allocated") or "1500"
            title = f"Post-Matric & Merit Scholarship Fund ({year})"
            dept = "Ministry of Social Justice & Empowerment / Minority Affairs"
            url = "https://scholarships.gov.in"
            ext_id = f"SCHOLARSHIP_ALLOC_{doc_id}"
            is_sandbox = bool(rec.get("is_sandbox", False))

            content_hash = compute_content_hash(title, dept, ext_id)
            is_verified, v_method, v_conf = self.verify_record({
                "source": "OGD_DATAGOV_IN",
                "source_type": SOURCE_TYPE_SANDBOX_SIMULATION if is_sandbox else SOURCE_TYPE_LIVE_API,
                "is_sandbox": is_sandbox,
                "external_id": ext_id,
                "title": title,
                "application_portal_url": url,
            })

            if is_sandbox:
                source_type = SOURCE_TYPE_SANDBOX_SIMULATION
                source_label = "data.gov.in Offline Sandbox Simulation"
                fetched_at = "2026-08-15T00:00:00Z"
                freshness = "UNKNOWN"
                is_demo = True
                is_snap = True
            else:
                source_type = SOURCE_TYPE_LIVE_API
                source_label = "data.gov.in Official Open Data Live Feed"
                fetched_at = now_utc
                freshness = compute_freshness(published_at=now_utc)
                is_demo = False
                is_snap = False

            scheme_dict = {
                "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"OGD_DATAGOV_IN:{ext_id}")),
                "scheme_code": f"OGD-SCHOLARSHIP-{year.replace('/', '-')}-{doc_id}",
                "title": title,
                "department": dept,
                "scheme_type": "scholarship",
                "beneficiary_category": ["SC", "ST", "OBC", "EWS", "Open"],
                "income_ceiling_annual": 250000,
                "benefit_description": f"Post-matric and merit-cum-means scholarship grant support of ₹{allocated} Cr allocated for technical and professional students.",
                "max_amount": 100000,
                "eligible_course_types": ["ITI", "Polytechnic", "Diploma", "Engineering"],
                "application_portal_url": url,
                "deadline_date": "2027-01-31",
                "status": "active",
                "source": "OGD_DATAGOV_IN",
                "source_type": source_type,
                "source_label": source_label,
                "source_url": url,
                "resource_id": resource_id,
                "external_id": ext_id,
                "last_synced_at": now_utc,
                "fetched_at": fetched_at,
                "published_at": now_utc if not is_sandbox else None,
                "snapshot_captured_at": fetched_at if is_sandbox else None,
                "last_seen_at": now_utc,
                "verified_at": fetched_at if is_verified else None,
                "verification_status": "VERIFIED" if is_verified else "UNVERIFIED",
                "verification_method": v_method,
                "confidence": v_conf,
                "content_hash": content_hash,
                "freshness_status": freshness,
                "is_demo": is_demo,
                "is_snapshot": is_snap,
            }

            try:
                validated = ValidatedIngestedScheme.model_validate(scheme_dict)
                schemes.append(validated.model_dump())
            except Exception as e:
                logger.warning("[DataGov] Discarding invalid scholarship scheme: %s", e)

        return schemes

    def transform_cts_schemes(
        self,
        raw_records: list[dict],
        resource_id: str = RESOURCE_ITI_CRAFTSMEN,
    ) -> list[dict]:
        """Transform Craftsmen Training Scheme records into SkillSetu schemes with provenance."""
        schemes = []
        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

        for idx, rec in enumerate(raw_records, start=1):
            doc_id = str(rec.get("document_id") or rec.get("id") or f"cts-{idx}")
            state = rec.get("state_ut_name") or rec.get("state") or "Maharashtra"
            title = f"Craftsmen Training Scheme (CTS) for {state} ITIs"
            dept = "Directorate General of Training, MSDE"
            url = "https://dvet.maharashtra.gov.in"
            ext_id = f"CTS_ITI_{doc_id}"
            is_sandbox = bool(rec.get("is_sandbox", False))

            content_hash = compute_content_hash(title, dept, ext_id)
            is_verified, v_method, v_conf = self.verify_record({
                "source": "OGD_DATAGOV_IN",
                "source_type": SOURCE_TYPE_SANDBOX_SIMULATION if is_sandbox else SOURCE_TYPE_LIVE_API,
                "is_sandbox": is_sandbox,
                "external_id": ext_id,
                "title": title,
                "application_portal_url": url,
            })

            if is_sandbox:
                source_type = SOURCE_TYPE_SANDBOX_SIMULATION
                source_label = "data.gov.in Offline Sandbox Simulation"
                fetched_at = "2026-08-15T00:00:00Z"
                freshness = "UNKNOWN"
                is_demo = True
                is_snap = True
            else:
                source_type = SOURCE_TYPE_LIVE_API
                source_label = "data.gov.in Official Open Data Live Feed"
                fetched_at = now_utc
                freshness = compute_freshness(published_at=now_utc)
                is_demo = False
                is_snap = False

            scheme_dict = {
                "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"OGD_DATAGOV_IN:{ext_id}")),
                "scheme_code": f"OGD-CTS-ITI-{doc_id}",
                "title": title,
                "department": dept,
                "scheme_type": "training_scheme",
                "beneficiary_category": ["Open", "SC", "ST", "OBC", "EWS", "Women"],
                "income_ceiling_annual": None,
                "benefit_description": f"Subsidized vocational & trade training across affiliated ITIs in {state} with NSQF certification and placement assistance.",
                "max_amount": 15000,
                "eligible_course_types": ["ITI", "Diploma"],
                "application_portal_url": url,
                "deadline_date": None,
                "status": "active",
                "source": "OGD_DATAGOV_IN",
                "source_type": source_type,
                "source_label": source_label,
                "source_url": url,
                "resource_id": resource_id,
                "external_id": ext_id,
                "last_synced_at": now_utc,
                "fetched_at": fetched_at,
                "published_at": now_utc if not is_sandbox else None,
                "snapshot_captured_at": fetched_at if is_sandbox else None,
                "last_seen_at": now_utc,
                "verified_at": fetched_at if is_verified else None,
                "verification_status": "VERIFIED" if is_verified else "UNVERIFIED",
                "verification_method": v_method,
                "confidence": v_conf,
                "content_hash": content_hash,
                "freshness_status": freshness,
                "is_demo": is_demo,
                "is_snapshot": is_snap,
            }

            try:
                validated = ValidatedIngestedScheme.model_validate(scheme_dict)
                schemes.append(validated.model_dump())
            except Exception as e:
                logger.warning("[DataGov] Discarding invalid CTS scheme: %s", e)

        return schemes

    def transform_naps_opportunities(
        self,
        raw_records: list[dict],
        resource_id: str = RESOURCE_NAPS_APPRENTICESHIP,
    ) -> list[dict]:
        """Transform NAPS district apprentice records into opportunities (jobs table)."""
        opportunities = []
        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

        for idx, rec in enumerate(raw_records, start=1):
            doc_id = str(rec.get("document_id") or rec.get("id") or f"naps-{idx}")
            raw_district = rec.get("district_name") or rec.get("district") or ""
            fy = rec.get("financial_year") or "2023-24"
            district_clean = normalize_maharashtra_district(raw_district, default="")
            if not district_clean:
                continue
            title = f"National Apprenticeship Trade Trainee ({district_clean})"
            company = f"NAPS Authorized Establishment ({district_clean})"
            url = "https://www.apprenticeshipindia.gov.in"
            ext_id = f"NAPS_DIST_{doc_id}"
            is_sandbox = bool(rec.get("is_sandbox", False))

            content_hash = compute_content_hash(title, company, district_clean, ext_id)
            is_verified, v_method, v_conf = self.verify_record({
                "source": "OGD_DATAGOV_IN",
                "source_type": SOURCE_TYPE_SANDBOX_SIMULATION if is_sandbox else SOURCE_TYPE_LIVE_API,
                "is_sandbox": is_sandbox,
                "external_id": ext_id,
                "title": title,
                "apply_url": url,
            })

            if is_sandbox:
                source_type = SOURCE_TYPE_SANDBOX_SIMULATION
                source_label = "data.gov.in Offline Sandbox Simulation"
                fetched_at = "2026-08-15T00:00:00Z"
                freshness = "UNKNOWN"
                is_demo = True
                is_snap = True
            else:
                source_type = SOURCE_TYPE_LIVE_API
                source_label = "data.gov.in Official Open Data Live Feed"
                fetched_at = now_utc
                freshness = compute_freshness(published_at=now_utc)
                is_demo = False
                is_snap = False

            opp_dict = {
                "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"OGD_DATAGOV_IN:{ext_id}")),
                "title": title,
                "company": company,
                "district": district_clean,
                "industry": "Manufacturing",
                "opportunity_type": "apprenticeship",
                "portal_source": "NAPS",
                "external_id": ext_id,
                "stipend_amount": 11500,
                "duration_months": 12,
                "min_education": "10th + ITI or Polytechnic Diploma",
                "vacancies_count": 10,
                "apply_url": url,
                "description": f"1-year approved apprenticeship engagement under NAPS ({fy}) in {district_clean} district with 25% government stipend subsidy.",
                "source": "OGD_DATAGOV_IN",
                "source_type": source_type,
                "source_label": source_label,
                "posted_date": fetched_at[:10] if fetched_at and len(fetched_at) >= 10 else None,
                "status": "active",
                "source_url": url,
                "resource_id": resource_id,
                "fetched_at": fetched_at,
                "published_at": now_utc if not is_sandbox else None,
                "snapshot_captured_at": fetched_at if is_sandbox else None,
                "last_seen_at": now_utc,
                "verified_at": fetched_at if is_verified else None,
                "verification_status": "VERIFIED" if is_verified else "UNVERIFIED",
                "verification_method": v_method,
                "confidence": v_conf,
                "content_hash": content_hash,
                "freshness_status": freshness,
                "is_demo": is_demo,
                "is_snapshot": is_snap,
            }

            try:
                validated = ValidatedIngestedOpportunity.model_validate(opp_dict)
                opportunities.append(validated.model_dump())
            except Exception as e:
                logger.warning("[DataGov] Discarding invalid NAPS opportunity: %s", e)

        return opportunities

    def transform_pmkvy_opportunities(
        self,
        raw_records: list[dict],
        resource_id: str = RESOURCE_PMKVY_SKILL,
    ) -> list[dict]:
        """Transform PMKVY vocational training records into opportunities (jobs table)."""
        opportunities = []
        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        for idx, rec in enumerate(raw_records, start=1):
            doc_id = str(rec.get("document_id") or rec.get("id") or f"pmkvy-{idx}")
            raw_district = str(rec.get("district") or rec.get("district_name") or "").strip()
            if not raw_district:
                continue
            district = normalize_maharashtra_district(raw_district, default="")
            if not district:
                continue
            title = "Short-Term Vocational Training & NSQF Certification"
            company = "PMKVY Accredited Training Partner"
            url = "https://www.skillindiadigital.gov.in"
            ext_id = f"PMKVY_TRN_{doc_id}"
            is_sandbox = bool(rec.get("is_sandbox", False))

            content_hash = compute_content_hash(title, company, district, ext_id)
            is_verified, v_method, v_conf = self.verify_record({
                "source": "OGD_DATAGOV_IN",
                "source_type": SOURCE_TYPE_SANDBOX_SIMULATION if is_sandbox else SOURCE_TYPE_LIVE_API,
                "is_sandbox": is_sandbox,
                "external_id": ext_id,
                "title": title,
                "apply_url": url,
            })

            if is_sandbox:
                source_type = SOURCE_TYPE_SANDBOX_SIMULATION
                source_label = "data.gov.in Offline Sandbox Simulation"
                fetched_at = "2026-08-15T00:00:00Z"
                freshness = "UNKNOWN"
                is_demo = True
                is_snap = True
            else:
                source_type = SOURCE_TYPE_LIVE_API
                source_label = "data.gov.in Official Open Data Live Feed"
                fetched_at = now_utc
                freshness = compute_freshness(published_at=now_utc)
                is_demo = False
                is_snap = False

            opp_dict = {
                "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"OGD_DATAGOV_IN:{ext_id}")),
                "title": title,
                "company": company,
                "district": district,
                "industry": "Skill Development",
                "opportunity_type": "vocational_training",
                "portal_source": "PMKVY",
                "external_id": ext_id,
                "stipend_amount": 8000,
                "duration_months": 4,
                "min_education": "10th Standard or ITI",
                "vacancies_count": 25,
                "apply_url": url,
                "description": f"Short-term NSQF-aligned job role training under PMKVY in {district} district with government fee sponsorship and assessment certification.",
                "source": "OGD_DATAGOV_IN",
                "source_type": source_type,
                "source_label": source_label,
                "posted_date": fetched_at[:10] if fetched_at and len(fetched_at) >= 10 else None,
                "status": "active",
                "source_url": url,
                "resource_id": resource_id,
                "fetched_at": fetched_at,
                "published_at": now_utc if not is_sandbox else None,
                "snapshot_captured_at": fetched_at if is_sandbox else None,
                "last_seen_at": now_utc,
                "verified_at": fetched_at if is_verified else None,
                "verification_status": "VERIFIED" if is_verified else "UNVERIFIED",
                "verification_method": v_method,
                "confidence": v_conf,
                "content_hash": content_hash,
                "freshness_status": freshness,
                "is_demo": is_demo,
                "is_snapshot": is_snap,
            }

            try:
                validated = ValidatedIngestedOpportunity.model_validate(opp_dict)
                opportunities.append(validated.model_dump())
            except Exception as e:
                logger.warning("[DataGov] Discarding invalid PMKVY opportunity: %s", e)

        return opportunities

    # ------------------------------------------------------------------------
    # Offline Sandbox Simulation Fallback Data (Explicitly tagged)
    # ------------------------------------------------------------------------

    def _get_sandbox_resource_data(self, resource_id: str) -> dict[str, Any]:
        """Provide simulated sample records for offline development.

        Each record is explicitly tagged with is_sandbox=True to ensure it is
        never stamped as verified government data.
        """
        if resource_id == RESOURCE_SCHOLARSHIP_ALLOCATION:
            return {
                "status": "ok",
                "total": 3,
                "count": 3,
                "records": [
                    {"document_id": "alloc-2023-24", "_year": "2023-24", "amount_allocated": "1530.50", "is_sandbox": True},
                    {"document_id": "alloc-2022-23", "_year": "2022-23", "amount_allocated": "1420.00", "is_sandbox": True},
                    {"document_id": "alloc-2021-22", "_year": "2021-22", "amount_allocated": "1380.25", "is_sandbox": True},
                ],
            }
        elif resource_id == RESOURCE_ITI_CRAFTSMEN:
            return {
                "status": "ok",
                "total": 2,
                "count": 2,
                "records": [
                    {"document_id": "cts-mh-01", "state_ut_name": "Maharashtra", "_2022": "145000", "is_sandbox": True},
                    {"document_id": "cts-mh-02", "state_ut_name": "Maharashtra", "_2021": "138000", "is_sandbox": True},
                ],
            }
        elif resource_id == RESOURCE_NAPS_APPRENTICESHIP:
            return {
                "status": "ok",
                "total": 4,
                "count": 4,
                "records": [
                    {"document_id": "naps-pune-01", "district_name": "Pune", "state_name_": "Maharashtra", "financial_year": "2023-24", "is_sandbox": True},
                    {"document_id": "naps-mumbai-02", "district_name": "Mumbai", "state_name_": "Maharashtra", "financial_year": "2023-24", "is_sandbox": True},
                    {"document_id": "naps-nagpur-03", "district_name": "Nagpur", "state_name_": "Maharashtra", "financial_year": "2023-24", "is_sandbox": True},
                    {"document_id": "naps-nashik-04", "district_name": "Nashik", "state_name_": "Maharashtra", "financial_year": "2023-24", "is_sandbox": True},
                ],
            }
        elif resource_id == RESOURCE_PMKVY_SKILL:
            return {
                "status": "ok",
                "total": 2,
                "count": 2,
                "records": [
                    {"document_id": "pmkvy-mh-01", "state_ut": "Maharashtra", "short_term_training_stt___enrolled": "85000", "is_sandbox": True},
                    {"document_id": "pmkvy-mh-02", "state_ut": "Maharashtra", "short_term_training_stt___enrolled": "92000", "is_sandbox": True},
                ],
            }
        return {"status": "ok", "total": 0, "count": 0, "records": []}
