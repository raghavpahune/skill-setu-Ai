from __future__ import annotations

import datetime
import hashlib
import logging
import uuid
from typing import Any

from app.core.time import parse_iso_timestamp, UTC_MIN
from app.ingestion.base_adapter import (
    SOURCE_TYPE_LIVE_API,
    SOURCE_TYPE_DEMO_SYNTHETIC,
    compute_content_hash,
    compute_freshness,
    extract_skills_and_unmapped,
    normalize_maharashtra_district,
)

logger = logging.getLogger("skillsetu.ingestion.job_intelligence")


def validate_and_normalize(
    raw_data: Any,
    is_demo: bool | None = None,
    is_trusted_feed: bool = False,
) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(raw_data, dict):
        return None, "Job record must be a dictionary."

    if is_demo is False:
        is_demo_rec = bool(
            raw_data.get("is_demo") is True
            or raw_data.get("source_label") == "DEMO_SYNTHETIC"
            or raw_data.get("source_type") == "DEMO_SYNTHETIC"
            or raw_data.get("data_provenance") == "DEMO_SYNTHETIC"
            or raw_data.get("source") == "DEMO_SYNTHETIC"
        )
        if is_demo_rec:
            return None, "Real mode rejects synthetic/demo jobs."

    title = str(raw_data.get("title") or "").strip()
    if len(title) < 2:
        return None, "Job title is required and must be at least 2 characters."

    company_val = raw_data.get("company")
    if isinstance(company_val, dict):
        company = str(company_val.get("display_name") or company_val.get("name") or "").strip()
    else:
        company = str(company_val or "").strip() if company_val is not None else ""
    if "company" in raw_data and not company:
        return None, "Company name is required and must be at least 2 characters."
    if not company:
        company = "Confidential Employer"
    if len(company) < 2:
        return None, "Company name is required and must be at least 2 characters."

    loc_val = raw_data.get("location")
    if isinstance(loc_val, dict):
        district_raw = str(loc_val.get("display_name") or loc_val.get("name") or "")
    else:
        district_raw = str(raw_data.get("district") or "")
    district = normalize_maharashtra_district(district_raw)

    ind_val = raw_data.get("category")
    if isinstance(ind_val, dict):
        industry = str(ind_val.get("label") or raw_data.get("industry") or "General").strip()
    else:
        industry = str(raw_data.get("industry") or "General").strip()
    if not industry:
        industry = "General"

    apply_url_val = raw_data.get("apply_url") or raw_data.get("redirect_url") or raw_data.get("source_url")
    if apply_url_val is not None:
        apply_url = str(apply_url_val).strip()
        if not apply_url:
            return None, "Apply URL or source URL is required."
        if not (apply_url.startswith("http://") or apply_url.startswith("https://")):
            return None, "Apply URL must be a valid HTTP or HTTPS URL."
    else:
        if "apply_url" in raw_data or "redirect_url" in raw_data or "source_url" in raw_data:
            return None, "Apply URL or source URL is required."
        source_name = str(raw_data.get("source") or "opportunity").lower()
        ext_slug = str(raw_data.get("external_id") or raw_data.get("id") or "job")
        apply_url = f"https://skillsetu.gov.in/opportunities/{source_name}/{ext_slug}"

    source_url = str(raw_data.get("source_url") or apply_url).strip()
    description = str(raw_data.get("description") or "").strip()
    if not description:
        description = f"{title} position at {company} located in {district}."

    now_dt = datetime.datetime.now(datetime.timezone.utc)
    now_iso = now_dt.isoformat()

    deadline_raw = raw_data.get("deadline")
    deadline = None
    is_expired = False
    if deadline_raw is not None and str(deadline_raw).strip() != "":
        parsed_dl = parse_iso_timestamp(str(deadline_raw).strip())
        if parsed_dl == UTC_MIN:
            return None, "Invalid deadline format. Must be a valid ISO timestamp."
        deadline = parsed_dl.isoformat()
        if parsed_dl < now_dt:
            is_expired = True

    posted_date_raw = raw_data.get("posted_date") or raw_data.get("created") or raw_data.get("published_at")
    published_at = None
    if posted_date_raw:
        parsed_pub = parse_iso_timestamp(str(posted_date_raw).strip())
        if parsed_pub != UTC_MIN:
            published_at = parsed_pub.isoformat()

    content_hash = str(raw_data.get("content_hash") or compute_content_hash(title, company, district, description))
    source = str(raw_data.get("source") or ("ADZUNA_API" if is_trusted_feed else "USER_SUBMITTED"))
    external_id = str(raw_data.get("external_id") or raw_data.get("id") or content_hash)

    is_demo_flag = bool(is_demo is True or (is_demo is None and (raw_data.get("is_demo") is True or raw_data.get("source") == "DEMO_SYNTHETIC")))

    raw_id = raw_data.get("id")
    if is_demo_flag and raw_id:
        job_id = str(raw_id)
    else:
        is_valid_uuid = False
        if raw_id:
            try:
                uuid.UUID(str(raw_id))
                is_valid_uuid = True
            except (ValueError, AttributeError, TypeError):
                is_valid_uuid = False
        if is_valid_uuid:
            job_id = str(raw_id)
        else:
            job_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"skillsetu.job.{source}.{external_id}"))

    if is_demo_flag:
        data_provenance = str(raw_data.get("data_provenance") or "DEMO_SYNTHETIC")
        verification_status = str(raw_data.get("verification_status") or "VERIFIED")
        status = "expired" if is_expired else str(raw_data.get("status") or "active").lower()
        is_active_flag = False if is_expired else (raw_data.get("is_active") if "is_active" in raw_data else True)
    elif is_trusted_feed:
        data_provenance = "GOVERNMENT_OFFICIAL" if source in ("DATAGOV_IN", "OGD_DATAGOV_IN") else "VERIFIED_EXTERNAL_FEED"
        verification_status = "VERIFIED"
        status = "expired" if is_expired else str(raw_data.get("status") or "active").lower()
        is_active_flag = False if is_expired else (raw_data.get("is_active") if "is_active" in raw_data else True)
    else:
        data_provenance = "EMPLOYER_SUBMITTED" if source in ("EMPLOYER_SUBMITTED", "EMPLOYER") else "UNVERIFIED_EXTERNAL_SOURCE"
        verification_status = "PENDING"
        status = "expired" if is_expired else "pending"
        is_active_flag = False

    if is_expired:
        freshness_status = "EXPIRED"
    else:
        freshness_status = compute_freshness(
            published_at=published_at,
            snapshot_captured_at=raw_data.get("snapshot_captured_at"),
            last_seen_at=raw_data.get("last_seen_at"),
        )
        if freshness_status == "UNKNOWN" and published_at is None:
            freshness_status = "RECENT"

    master_skills = None
    try:
        from app.repositories.supabase_repository import list_skills
        master_skills = list_skills(limit=10000) or []
    except Exception:
        master_skills = []
    if not master_skills:
        try:
            from app.db import get_demo
            master_skills = get_demo("skills") or []
        except Exception:
            master_skills = []

    matched_skill_records, extracted_unmapped = extract_skills_and_unmapped(
        f"{title} {description}",
        master_skills,
        max_skills=8,
        max_unmapped=8,
    )

    skill_names = sorted(list(set(
        [s["name"] for s in matched_skill_records if "name" in s]
        + [s for s in (raw_data.get("skills") or []) if isinstance(s, str)]
    )))
    skill_ids = sorted(list(set(
        [s["id"] for s in matched_skill_records if "id" in s]
        + [sid for sid in (raw_data.get("skill_ids") or []) if isinstance(sid, str)]
    )))
    unmapped = sorted(list(set(
        extracted_unmapped
        + [u for u in (raw_data.get("unmapped_skills") or []) if isinstance(u, str)]
    )))

    normalized_record: dict[str, Any] = {
        "id": job_id,
        "title": title,
        "company": company,
        "district": district,
        "industry": industry,
        "description": description,
        "source": source,
        "source_label": raw_data.get("source_label") or ("Adzuna India Live API Feed" if source == "ADZUNA_API" else ("Employer Submission" if source == "EMPLOYER_SUBMITTED" else "External Job Source")),
        "source_type": SOURCE_TYPE_DEMO_SYNTHETIC if is_demo_flag else (SOURCE_TYPE_LIVE_API if is_trusted_feed else "USER_SUBMITTED"),
        "posted_date": published_at,
        "opportunity_type": str(raw_data.get("opportunity_type") or "job").lower(),
        "external_id": external_id,
        "portal_source": str(raw_data.get("portal_source") or source).lower(),
        "stipend_amount": raw_data.get("stipend_amount"),
        "duration_months": raw_data.get("duration_months"),
        "min_education": raw_data.get("min_education"),
        "vacancies_count": raw_data.get("vacancies_count", 1),
        "apply_url": apply_url,
        "source_url": source_url,
        "content_hash": content_hash,
        "fetched_at": raw_data.get("fetched_at") or now_iso,
        "published_at": published_at,
        "snapshot_captured_at": raw_data.get("snapshot_captured_at"),
        "last_seen_at": raw_data.get("last_seen_at") or now_iso,
        "verified_at": now_iso if verification_status == "VERIFIED" else None,
        "verification_status": verification_status,
        "verification_method": raw_data.get("verification_method") or ("STRUCTURAL_API_VALIDATION" if is_trusted_feed else "MANUAL_REVIEW"),
        "confidence": 90 if verification_status == "VERIFIED" else 40,
        "freshness_status": freshness_status,
        "is_demo": is_demo_flag,
        "is_snapshot": bool(raw_data.get("is_snapshot", False)),
        "status": status,
        "is_active": is_active_flag,
        "data_provenance": data_provenance,
        "deadline": deadline,
        "skills": skill_names,
        "skill_ids": skill_ids,
        "unmapped_skills": unmapped,
    }

    return normalized_record, None


class JobIntelligenceIngestor:
    def __init__(self):
        pass

    def validate_and_normalize(
        self,
        raw_data: Any,
        is_demo: bool | None = None,
        is_trusted_feed: bool = False,
    ) -> tuple[dict[str, Any] | None, str | None]:
        return validate_and_normalize(raw_data, is_demo=is_demo, is_trusted_feed=is_trusted_feed)

    def deduplicate_jobs(self, jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        source_id_index: dict[tuple[str, str], dict[str, Any]] = {}
        hash_index: dict[str, dict[str, Any]] = {}

        for j in jobs:
            source = j.get("source")
            ext_id = j.get("external_id")
            c_hash = j.get("content_hash")

            target = None
            if source and ext_id and (source, ext_id) in source_id_index:
                target = source_id_index[(source, ext_id)]
            elif c_hash and c_hash in hash_index:
                target = hash_index[c_hash]

            if target is not None:
                for k, v in j.items():
                    if v is not None and (k not in target or target[k] is None):
                        target[k] = v
                target["last_seen_at"] = j.get("last_seen_at") or target.get("last_seen_at")
            else:
                deduped.append(j)
                if source and ext_id:
                    source_id_index[(source, ext_id)] = j
                if c_hash:
                    hash_index[c_hash] = j

        return deduped


job_ingestor = JobIntelligenceIngestor()
