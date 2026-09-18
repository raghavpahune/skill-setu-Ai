from __future__ import annotations

import logging
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from pydantic import BaseModel, Field, field_validator

from app.core.data_mode import is_explicit_demo_mode
from app.core.security import require_roles, get_optional_current_user, is_demo_student_id
from app.core.time import parse_iso_timestamp, UTC_MIN
from app.db import get_demo, save_job
from app.ingestion.base_adapter import (
    compute_content_hash,
    normalize_maharashtra_district,
)
from app.routers.gov_opportunities import _is_expired
from app.services.career_recommendation_engine import _resolve_student_profile
from app.services.job_matching import match_student_to_jobs

logger = logging.getLogger("skillsetu.routers.jobs")
router = APIRouter()


class JobSubmission(BaseModel):
    title: str = Field(..., min_length=2, max_length=250)
    company: str = Field(..., min_length=2, max_length=200)
    district: str = Field(default="Maharashtra")
    industry: str = Field(default="General", min_length=2, max_length=150)
    description: str = Field(..., min_length=5, max_length=3000)
    opportunity_type: str = Field(default="job")
    stipend_amount: int | None = None
    duration_months: int | None = None
    min_education: str | None = None
    vacancies_count: int = Field(default=1, ge=1)
    apply_url: str = Field(..., min_length=5, max_length=500)
    source_url: str | None = None
    deadline: str | None = None
    skills: list[str] = Field(default_factory=list)
    status: str = Field(default="active")
    is_active: bool = True
    data_provenance: str | None = None

    @field_validator("deadline")
    @classmethod
    def validate_deadline(cls, v: str | None) -> str | None:
        if not v or not isinstance(v, str) or not v.strip():
            return None
        dt = parse_iso_timestamp(v)
        if dt == UTC_MIN:
            raise ValueError("Invalid deadline format. Must be a valid ISO timestamp.")
        return v.strip()


@router.get("/jobs")
async def list_jobs(
    district: str | None = None,
    industry: str | None = None,
    opportunity_type: str | None = None,
    limit: int = 50,
    is_demo: bool | None = Query(None, description="Explicit demo/real mode selector"),
):
    is_demo_mode = is_explicit_demo_mode(is_demo)
    if is_demo_mode:
        jobs = get_demo("jobs")
        if district and district.strip().lower() not in ("all", "all districts"):
            jobs = [j for j in jobs if j.get("district", "").lower() == district.strip().lower()]
        if industry:
            jobs = [j for j in jobs if j.get("industry", "").lower() == industry.strip().lower()]
        if opportunity_type:
            jobs = [j for j in jobs if j.get("opportunity_type", "job").lower() == opportunity_type.strip().lower()]
        return jobs[:limit]

    try:
        from app.repositories.supabase_repository import list_jobs as list_jobs_repo, SupabaseRepositoryError
        repo_jobs = list_jobs_repo(
            district=district,
            industry=industry,
            opportunity_type=opportunity_type,
            status="active",
            is_active=True,
            is_demo=False,
            limit=limit * 2 if limit else 100,
        )
    except SupabaseRepositoryError as exc:
        logger.error("[Jobs API] Authoritative repository lookup failed: %s", exc)
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Job repository is temporarily unavailable.",
        ) from exc
    except Exception as exc:
        logger.warning("[Jobs API] Unexpected failure listing jobs: %s", exc)
        repo_jobs = []

    filtered_jobs = []
    for j in (repo_jobs or []):
        if (
            j.get("is_demo") is True
            or j.get("source") == "DEMO_SYNTHETIC"
            or j.get("source_type") in ("DEMO_SYNTHETIC", "SANDBOX_SIMULATION")
            or j.get("data_provenance") == "DEMO_SYNTHETIC"
        ):
            continue
        if j.get("status", "active").lower() != "active" or j.get("is_active") is False:
            continue
        if (j.get("verification_status") or "").upper() in ("REJECTED", "UNVERIFIED"):
            continue
        if _is_expired(j.get("deadline")):
            continue
        filtered_jobs.append(j)

    return filtered_jobs[:limit]


@router.post("/jobs", status_code=http_status.HTTP_201_CREATED)
async def create_job_endpoint(
    data: JobSubmission,
    current_user: dict = Depends(require_roles(["EMPLOYER", "ADMIN"])),
):
    now_iso = datetime.now(timezone.utc).isoformat()
    norm_district = normalize_maharashtra_district(data.district)
    norm_title = data.title.strip()
    norm_company = data.company.strip()
    norm_desc = data.description.strip()
    content_hash = compute_content_hash(norm_title, norm_company, norm_district, norm_desc)
    job_id = f"job-{uuid.uuid4().hex[:12]}"

    role = (current_user.get("role") or "").upper()
    if role == "ADMIN":
        provenance = data.data_provenance or "ADMIN_CREATED"
        verification_status = "VERIFIED"
        status = data.status.lower()
        is_active = data.is_active
    else:
        provenance = "EMPLOYER_SUBMITTED"
        verification_status = "PENDING"
        status = "pending"
        is_active = False

    if _is_expired(data.deadline):
        status = "expired"
        is_active = False

    record = {
        "id": job_id,
        "title": norm_title,
        "company": norm_company,
        "district": norm_district,
        "industry": data.industry.strip(),
        "description": norm_desc,
        "opportunity_type": data.opportunity_type.lower(),
        "portal_source": "employer_portal" if role != "ADMIN" else "admin_portal",
        "stipend_amount": data.stipend_amount,
        "duration_months": data.duration_months,
        "min_education": data.min_education,
        "vacancies_count": data.vacancies_count,
        "apply_url": data.apply_url.strip(),
        "source_url": data.source_url.strip() if data.source_url else data.apply_url.strip(),
        "content_hash": content_hash,
        "external_id": job_id,
        "source": "EMPLOYER_SUBMITTED" if role != "ADMIN" else "ADMIN_CREATED",
        "source_label": "Employer Submission" if role != "ADMIN" else "Admin Submission",
        "source_type": "USER_SUBMITTED",
        "data_provenance": provenance,
        "status": status,
        "is_active": is_active,
        "verification_status": verification_status,
        "verification_method": "MANUAL_REVIEW" if role != "ADMIN" else "ADMIN_VERIFIED",
        "confidence": 50 if role != "ADMIN" else 90,
        "freshness_status": "EXPIRED" if status == "expired" else "NEW",
        "deadline": data.deadline,
        "is_demo": False,
        "is_snapshot": False,
        "created_at": now_iso,
        "updated_at": now_iso,
        "user_id": current_user.get("id"),
        "user_email": current_user.get("email"),
        "skills": data.skills,
    }

    try:
        saved = save_job(record)
    except Exception as e:
        logger.exception("[Jobs API] Failed persisting job: %s", e)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database persistence failed for job.",
        ) from e

    if data.skills:
        try:
            from app.db import _cache
            from app.repositories.supabase_repository import list_skills, batch_create_job_skills
            master_skills = None
            try:
                master_skills = list_skills(limit=10000) or []
            except Exception:
                master_skills = []
            if not master_skills:
                try:
                    master_skills = get_demo("skills") or []
                except Exception:
                    master_skills = []

            skill_name_to_id = {}
            for sk in master_skills:
                sid = sk.get("id")
                sname = sk.get("name")
                if sid and sname:
                    skill_name_to_id[str(sname).strip().lower()] = str(sid)
                for syn in (sk.get("synonyms") or []):
                    if sid and syn:
                        skill_name_to_id[str(syn).strip().lower()] = str(sid)

            new_links = []
            seen_links = set()
            for s in data.skills:
                if not isinstance(s, str) or not s.strip():
                    continue
                s_clean = s.strip().lower()
                target_id = skill_name_to_id.get(s_clean)
                if not target_id:
                    continue
                pair = (saved["id"], target_id)
                if pair not in seen_links:
                    seen_links.add(pair)
                    new_links.append({
                        "job_id": saved["id"],
                        "skill_id": target_id,
                        "proficiency_required": "intermediate",
                    })

            if new_links:
                try:
                    batch_create_job_skills(new_links)
                except Exception as b_err:
                    logger.warning("[Jobs API] Failed persisting job_skills to database: %s", b_err)
                _cache.setdefault("job_skills", []).extend(new_links)
        except Exception as sk_err:
            logger.warning("[Jobs API] Failed resolving or linking skills for job %s: %s", saved.get("id"), sk_err)

    return {
        "status": "created",
        "message": f"Job '{saved['id']}' created successfully.",
        "job": saved,
    }


@router.get("/jobs/recommended/{student_id}")
async def recommended_jobs(
    student_id: str,
    limit: int = Query(10, ge=1, le=50),
    is_demo: bool | None = Query(None, description="Explicit demo/real mode selector"),
    current_user: dict | None = Depends(get_optional_current_user),
):
    resolved_id = student_id
    if student_id == "me" and current_user:
        resolved_id = current_user.get("id") or "me"

    from app.routers.student import _verify_student_recommendations_access
    _verify_student_recommendations_access(resolved_id, current_user)

    profile = _resolve_student_profile(resolved_id)
    if not profile:
        if student_id == "me" or (current_user and resolved_id == current_user.get("id")):
            return {"student_id": resolved_id, "total_matches": 0, "recommended_jobs": [], "status": "unassessed"}
        raise HTTPException(status_code=404, detail=f"Student profile '{student_id}' not found.")

    if is_demo is True:
        use_demo = True
    elif is_demo is False:
        use_demo = False
    else:
        use_demo = is_demo_student_id(resolved_id) or profile.get("is_demo") or profile.get("source") == "DEMO_SYNTHETIC"

    if use_demo:
        jobs = get_demo("jobs")
        raw_job_skills = get_demo("job_skills")
        skills_dict = {s["id"]: s.get("name", s["id"]) for s in get_demo("skills")}
        job_skills_map: dict[str, list[str]] = {}
        for js in raw_job_skills:
            jid = js.get("job_id")
            sid = js.get("skill_id")
            if jid and sid:
                sname = skills_dict.get(sid, sid)
                job_skills_map.setdefault(jid, []).append(sname)
        active_jobs = jobs
        note = "Recommendations are based on skill and profile overlap with demo job dataset."
    else:
        try:
            from app.repositories.supabase_repository import list_jobs as list_jobs_repo, list_job_skills, list_skills
            db_jobs = list_jobs_repo(status="active", is_active=True, is_demo=False, limit=1000) or []
            job_ids = [j.get("id") for j in db_jobs if j.get("id")]
            raw_job_skills = list_job_skills(job_ids=job_ids) if job_ids else []
            skills_repo = list_skills(limit=1000) or []
            skills_dict = {s["id"]: s.get("name", s["id"]) for s in skills_repo}
            job_skills_map = {}
            for js in raw_job_skills:
                jid = js.get("job_id")
                sid = js.get("skill_id")
                if jid and sid:
                    sname = skills_dict.get(sid, sid)
                    job_skills_map.setdefault(jid, []).append(sname)
        except Exception as e:
            logger.exception("[RecommendedJobs] Supabase error listing jobs: %s", e)
            raise HTTPException(
                status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Job repository is temporarily unavailable for recommendations.",
            ) from e

        valid_jobs = [
            j for j in db_jobs
            if j.get("is_demo") is False
            and j.get("source") != "DEMO_SYNTHETIC"
            and j.get("source_type") not in ("DEMO_SYNTHETIC", "SANDBOX_SIMULATION")
            and j.get("data_provenance") != "DEMO_SYNTHETIC"
            and j.get("status", "active").lower() == "active"
            and j.get("is_active") is not False
            and (j.get("verification_status") or "").upper() not in ("REJECTED", "UNVERIFIED")
            and not _is_expired(j.get("deadline"))
        ]
        active_jobs = valid_jobs
        note = "Recommendations are based on verified live job vacancies in Maharashtra."

    ranked = match_student_to_jobs(profile, active_jobs, job_skills_map=job_skills_map)

    return {
        "student_id": student_id,
        "total_matches": len(ranked),
        "recommended_jobs": ranked[:limit],
        "provenance_note": note,
    }


@router.get("/jobs/demand")
async def job_demand(
    group_by: str = Query("district", enum=["district", "skill", "industry"]),
    is_demo: bool | None = Query(None, description="Explicit demo/real mode selector"),
):
    is_demo_mode = is_explicit_demo_mode(is_demo)
    if is_demo_mode:
        jobs = get_demo("jobs")
        job_skills = get_demo("job_skills")
        skills = {s["id"]: s["name"] for s in get_demo("skills")}
    else:
        try:
            from app.repositories.supabase_repository import list_jobs as list_jobs_repo, list_job_skills, list_skills
            raw_jobs = list_jobs_repo(status="active", is_active=True, is_demo=False, limit=1000) or []
            jobs = [
                j for j in raw_jobs
                if j.get("is_demo") is False
                and j.get("source") != "DEMO_SYNTHETIC"
                and j.get("source_type") not in ("DEMO_SYNTHETIC", "SANDBOX_SIMULATION")
                and j.get("data_provenance") != "DEMO_SYNTHETIC"
                and j.get("status", "active").lower() == "active"
                and j.get("is_active") is not False
                and (j.get("verification_status") or "").upper() not in ("REJECTED", "UNVERIFIED")
                and not _is_expired(j.get("deadline"))
            ]
            job_ids = [j.get("id") for j in jobs if j.get("id")]
            job_skills = list_job_skills(job_ids=job_ids) if job_ids else []
            skills = {s["id"]: s.get("name", s["id"]) for s in (list_skills(limit=1000) or [])}
        except Exception as exc:
            logger.error("[Jobs API] Authoritative lookup for job_demand failed: %s", exc)
            raise HTTPException(
                status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Job demand data is temporarily unavailable.",
            ) from exc

    if group_by == "district":
        counts = Counter(j["district"] for j in jobs if j.get("district"))
    elif group_by == "industry":
        counts = Counter(j["industry"] for j in jobs if j.get("industry"))
    elif group_by == "skill":
        counts = Counter(js["skill_id"] for js in job_skills if js.get("skill_id"))
        counts = {skills.get(k, k): v for k, v in counts.items()}
    else:
        counts = {}

    result = [{"name": k, "count": v} for k, v in counts.items()]
    result.sort(key=lambda x: x["count"], reverse=True)
    return result
