"""Opportunities API — internships, apprenticeships, vocational training, and jobs."""
import logging
from fastapi import APIRouter, HTTPException, Query, status as http_status
from app.core.data_mode import is_explicit_demo_mode
from app.db import get_demo
from app.routers.gov_opportunities import _is_expired

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_skills_by_job(is_demo: bool = False, job_ids: list[str] | None = None) -> dict[str, list[dict]]:
    """Build a lookup of required skills per job/opportunity."""
    if is_demo:
        job_skills = get_demo("job_skills")
        skills_map = {s["id"]: s for s in get_demo("skills")}
    else:
        try:
            from app.repositories import supabase_repository
            job_skills = supabase_repository.list_job_skills(job_ids=job_ids) if job_ids else []
            skills = supabase_repository.list_skills(limit=1000) or []
            skills_map = {s["id"]: s for s in skills}
        except Exception:
            job_skills = []
            skills_map = {}

    result: dict[str, list[dict]] = {}
    for js in job_skills:
        jid = js.get("job_id")
        sid = js.get("skill_id")
        if not jid or not sid:
            continue
        skill_info = skills_map.get(sid, {})
        if jid not in result:
            result[jid] = []
        result[jid].append({
            "skill_id": sid,
            "skill_name": skill_info.get("name", sid),
            "category": skill_info.get("category", ""),
            "proficiency_required": js.get("proficiency_required", "intermediate"),
        })
    return result


@router.get("/opportunities")
async def list_opportunities(
    opportunity_type: str | None = None,
    district: str | None = None,
    industry: str | None = None,
    skill: str | None = None,
    min_stipend: int | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    is_demo: bool | None = Query(None, description="Explicit demo/real mode selector"),
):
    """List opportunities (jobs, internships, apprenticeships, vocational training).

    Supports filtering by opportunity type, district, industry, required skill,
    stipend, status, and search query.
    """
    is_demo_mode = is_explicit_demo_mode(is_demo)
    if is_demo_mode:
        jobs = get_demo("jobs")
        skills_by_job = _get_skills_by_job(is_demo=True)
    else:
        try:
            from app.repositories import supabase_repository
            from app.repositories.supabase_repository import SupabaseRepositoryError
            fetch_limit = 5000 if (skill or status or min_stipend or q) else (offset + limit)
            raw_jobs = supabase_repository.list_jobs(
                district=district,
                industry=industry,
                opportunity_type=opportunity_type,
                status=status if status else "active",
                is_active=True,
                is_demo=False,
                limit=fetch_limit,
            ) or []
            job_ids = [j.get("id") for j in raw_jobs if j.get("id")]
            skills_by_job = _get_skills_by_job(is_demo=False, job_ids=job_ids)
        except SupabaseRepositoryError as exc:
            logger.error("[Opportunities API] Repository lookup failed: %s", exc)
            raise HTTPException(
                status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Opportunities repository is temporarily unavailable.",
            ) from exc
        except Exception as exc:
            logger.warning("[Opportunities API] Unexpected failure: %s", exc)
            raw_jobs = []
            skills_by_job = {}

        jobs = []
        for j in raw_jobs:
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
            jobs.append(j)

    filtered = []
    for j in jobs:
        opp_type = j.get("opportunity_type", "job")

        # Opportunity type filter (job, internship, apprenticeship, vocational_training)
        if opportunity_type and opp_type.lower() != opportunity_type.lower():
            continue

        # District filter
        if district and j.get("district", "").lower() != district.lower():
            continue

        # Industry filter
        if industry and j.get("industry", "").lower() != industry.lower():
            continue

        # Status filter
        if status and j.get("status", "active").lower() != status.lower():
            continue

        # Minimum stipend filter
        if min_stipend is not None:
            stipend = j.get("stipend_amount")
            if stipend is None or stipend < min_stipend:
                continue

        # Attached skills
        opp_skills = skills_by_job.get(j.get("id", ""), [])

        # Skill filter: matches either skill ID or skill name (case-insensitive)
        if skill:
            skill_lower = skill.lower()
            matched_skill = any(
                skill_lower == s["skill_id"].lower() or skill_lower in s["skill_name"].lower()
                for s in opp_skills
            )
            if not matched_skill:
                continue

        # Search query (title, company, description)
        if q:
            q_lower = q.lower()
            corpus = f"{j.get('title', '')} {j.get('company', '')} {j.get('description', '')}".lower()
            if q_lower not in corpus:
                continue

        ev_status = "UNVERIFIED"
        if not is_demo_mode:
            emp_id = j.get("employer_id")
            comp_name = (j.get("company") or "").strip().lower()
            emp_rec = None
            if emp_id:
                try:
                    from app.repositories.supabase_repository import get_employer
                    emp_rec = get_employer(emp_id)
                except Exception:
                    pass
            if not emp_rec and comp_name:
                from app.db import _cache
                for e in _cache.get("employers", []):
                    if (e.get("name") or "").strip().lower() == comp_name or (e.get("company_name") or "").strip().lower() == comp_name:
                        emp_rec = e
                        break
            if emp_rec and (emp_rec.get("is_demo") is True or emp_rec.get("source") == "DEMO_SYNTHETIC"):
                emp_rec = None
            if emp_rec:
                ev_status = (emp_rec.get("verification_status") or "UNVERIFIED").upper()

        filtered.append({
            "id": j.get("id"),
            "title": j.get("title"),
            "company": j.get("company"),
            "district": j.get("district"),
            "industry": j.get("industry"),
            "opportunity_type": opp_type,
            "portal_source": j.get("portal_source", "direct"),
            "stipend_amount": j.get("stipend_amount"),
            "duration_months": j.get("duration_months"),
            "min_education": j.get("min_education"),
            "vacancies_count": j.get("vacancies_count", 1),
            "apply_url": j.get("apply_url"),
            "description": j.get("description", ""),
            "posted_date": j.get("posted_date"),
            "status": j.get("status", "active"),
            "source": j.get("source") or ("DEMO_SYNTHETIC" if is_demo_mode else "UNKNOWN"),
            "skills": opp_skills,
            "employer_verification_status": ev_status,
            "is_employer_verified": (ev_status == "VERIFIED"),
        })

    return filtered[offset : offset + limit]


@router.get("/opportunities/summary")
async def opportunities_summary(
    is_demo: bool | None = Query(None, description="Explicit demo/real mode selector"),
):
    """Return count breakdown by opportunity_type and portal source."""
    if is_explicit_demo_mode(is_demo):
        jobs = get_demo("jobs")
    else:
        try:
            from app.repositories import supabase_repository
            from app.repositories.supabase_repository import SupabaseRepositoryError
            raw_jobs = supabase_repository.list_jobs(
                status="active",
                is_active=True,
                is_demo=False,
                limit=1000,
            ) or []
            jobs = []
            for j in raw_jobs:
                if (
                    j.get("is_demo") is True
                    or j.get("source") == "DEMO_SYNTHETIC"
                    or j.get("source_type") in ("DEMO_SYNTHETIC", "SANDBOX_SIMULATION")
                    or j.get("data_provenance") == "DEMO_SYNTHETIC"
                ):
                    continue
                if (
                    j.get("status", "active").lower() == "active"
                    and j.get("is_active") is not False
                    and (j.get("verification_status") or "").upper() not in ("REJECTED", "UNVERIFIED")
                    and not _is_expired(j.get("deadline"))
                ):
                    jobs.append(j)
        except SupabaseRepositoryError as exc:
            logger.error("[Opportunities API] Summary query failed: %s", exc)
            raise HTTPException(
                status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Opportunities repository is temporarily unavailable.",
            ) from exc
        except Exception as exc:
            logger.warning("[Opportunities API] Summary query failed: %s", exc)
            jobs = []

    type_counts: dict[str, int] = {}
    district_counts: dict[str, int] = {}

    for j in jobs:
        opp_type = j.get("opportunity_type", "job")
        type_counts[opp_type] = type_counts.get(opp_type, 0) + 1
        dist = j.get("district", "Unknown")
        district_counts[dist] = district_counts.get(dist, 0) + 1

    return {
        "total_opportunities": len(jobs),
        "by_type": type_counts,
        "top_districts": sorted(
            [{"district": k, "count": v} for k, v in district_counts.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:5],
    }


@router.get("/opportunities/{opportunity_id}")
async def get_opportunity(
    opportunity_id: str,
    is_demo: bool | None = Query(None, description="Explicit demo/real mode selector"),
):
    """Get single opportunity details by ID, including required skills."""
    if is_explicit_demo_mode(is_demo):
        jobs = get_demo("jobs")
        skills_by_job = _get_skills_by_job(is_demo=True)
        for j in jobs:
            if j.get("id") == opportunity_id:
                return {
                    "id": j["id"],
                    "title": j["title"],
                    "company": j["company"],
                    "district": j["district"],
                    "industry": j["industry"],
                    "opportunity_type": j.get("opportunity_type", "job"),
                    "portal_source": j.get("portal_source", "direct"),
                    "stipend_amount": j.get("stipend_amount"),
                    "duration_months": j.get("duration_months"),
                    "min_education": j.get("min_education"),
                    "vacancies_count": j.get("vacancies_count", 1),
                    "apply_url": j.get("apply_url"),
                    "description": j.get("description", ""),
                    "posted_date": j.get("posted_date"),
                    "status": j.get("status", "active"),
                    "source": j.get("source", "DEMO_SYNTHETIC"),
                    "skills": skills_by_job.get(j["id"], []),
                }
    else:
        try:
            from app.repositories import supabase_repository
            from app.repositories.supabase_repository import SupabaseRepositoryError
            job = supabase_repository.get_job(opportunity_id)
        except SupabaseRepositoryError as e:
            logger.error("[Opportunities] Repository lookup failed for %s: %s", opportunity_id, e)
            raise HTTPException(
                status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Opportunities repository is temporarily unavailable.",
            ) from e
        except Exception as e:
            logger.warning("[Opportunities] Repository lookup failed for %s: %s", opportunity_id, e)
            job = None

        if job:
            if (
                job.get("is_demo") is True
                or job.get("source") == "DEMO_SYNTHETIC"
                or job.get("source_type") in ("DEMO_SYNTHETIC", "SANDBOX_SIMULATION")
                or job.get("data_provenance") == "DEMO_SYNTHETIC"
            ):
                raise HTTPException(status_code=404, detail="Opportunity not found")
            if (
                job.get("status", "active").lower() != "active"
                or job.get("is_active") is False
                or (job.get("verification_status") or "").upper() in ("REJECTED", "UNVERIFIED")
                or _is_expired(job.get("deadline"))
            ):
                raise HTTPException(status_code=404, detail="Opportunity not found")

            skills_by_job = _get_skills_by_job(is_demo=False, job_ids=[opportunity_id])
            return {
                "id": job["id"],
                "title": job.get("title", ""),
                "company": job.get("company", ""),
                "district": job.get("district", ""),
                "industry": job.get("industry", ""),
                "opportunity_type": job.get("opportunity_type", "job"),
                "portal_source": job.get("portal_source", "direct"),
                "stipend_amount": job.get("stipend_amount"),
                "duration_months": job.get("duration_months"),
                "min_education": job.get("min_education"),
                "vacancies_count": job.get("vacancies_count", 1),
                "apply_url": job.get("apply_url"),
                "description": job.get("description", ""),
                "posted_date": job.get("posted_date"),
                "status": job.get("status", "active"),
                "source": job.get("source") or "UNKNOWN",
                "skills": skills_by_job.get(job["id"], []),
            }

    raise HTTPException(status_code=404, detail="Opportunity not found")
