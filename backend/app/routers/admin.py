"""Admin Data Management API — inspection, filtering, aggregate analytics, and management of student assessments, employer demands, and government opportunities."""
from collections import Counter
from datetime import datetime, timezone
import logging
from typing import Any
import uuid
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status as http_status
from pydantic import BaseModel, Field

logger = logging.getLogger("skillsetu.admin")
from app.config import settings
from app.db import (
    get_demo,
    delete_student_assessment,
    update_employer_demand_status,
    delete_employer_demand,
    save_gov_opportunity,
    update_gov_opportunity,
    delete_gov_opportunity,
    update_course,
    delete_course,
    save_industry_signal,
    update_industry_signal,
    delete_industry_signal,
    get_industry_signal_by_id,
)
from app.ingestion.industry_intelligence import industry_ingestor, calculate_freshness

from app.core.data_mode import is_explicit_demo_mode
from app.core.security import verify_admin_access, is_demo_student_id
from app.repositories.supabase_repository import SupabaseRepositoryError

router = APIRouter()

verify_admin_key = verify_admin_access


@router.get("/admin/data-governance", dependencies=[Depends(verify_admin_key)])
async def get_admin_data_governance():
    """Retrieve platform-wide data governance breakdown: real user submissions vs synthetic demo baseline."""
    from app.db import get_data_governance_summary
    return get_data_governance_summary()


class DemandValidationUpdate(BaseModel):

    status: str | None = Field(None, description="'VALIDATED' | 'REJECTED' | 'PENDING'")
    validation_status: str | None = Field(None, description="'VALIDATED' | 'REJECTED' | 'PENDING'")
    admin_notes: str | None = None
    validated_by: str | None = "Admin Team"


@router.get("/admin/assessments", dependencies=[Depends(verify_admin_key)])
async def list_admin_assessments(
    source: str | None = Query(None, description="'USER_SUBMITTED' | 'DEMO_SYNTHETIC' | 'all'"),
    district: str | None = Query(None, description="District filter or 'all'"),
    career_goal: str | None = Query(None, description="Target role filter or 'all'"),
    date_from: str | None = Query(None, description="ISO start date YYYY-MM-DD"),
    date_to: str | None = Query(None, description="ISO end date YYYY-MM-DD"),
    search: str | None = Query(None, description="Search term for candidate name, course, or skills"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Retrieve and filter student assessment records with pagination and source distinction."""
    try:
        from app.repositories.supabase_repository import list_student_assessments
        assessments = list_student_assessments()
    except Exception as e:
        logger.exception("[AdminAssessments] Supabase query failed: %s", e)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database query failed listing assessments.",
        ) from e
    results = assessments

    # 1. Filter by Data Source
    if source and source.strip() and source.lower() != "all":
        results = [a for a in results if a.get("source", "").lower() == source.strip().lower()]

    # 2. Filter by District
    if district and district.strip() and district.lower() != "all":
        d_clean = district.strip().lower()
        results = [a for a in results if d_clean in a.get("district", "").lower() or a.get("district", "").lower() in d_clean]

    # 3. Filter by Career Goal
    if career_goal and career_goal.strip() and career_goal.lower() != "all":
        g_clean = career_goal.strip().lower()
        results = [a for a in results if g_clean in a.get("career_goal", "").lower() or a.get("career_goal", "").lower() in g_clean]

    # 4. Filter by Date Range
    if date_from and date_from.strip():
        f_clean = date_from.strip()
        results = [a for a in results if a.get("submitted_at", "")[:10] >= f_clean]

    if date_to and date_to.strip():
        t_clean = date_to.strip()
        results = [a for a in results if a.get("submitted_at", "")[:10] <= t_clean]

    # 5. Search Text Filter (name, education, career_goal, skills)
    if search and search.strip():
        q = search.strip().lower()
        filtered = []
        for a in results:
            name_match = q in a.get("name", "").lower()
            edu_match = q in a.get("education", "").lower()
            goal_match = q in a.get("career_goal", "").lower()
            skill_match = any(
                q in (s.get("skill_name", "") if isinstance(s, dict) else str(s)).lower()
                for s in a.get("current_skills", [])
            )
            if name_match or edu_match or goal_match or skill_match:
                filtered.append(a)
        results = filtered

    total_count = len(results)
    paginated = results[offset : offset + limit]

    return {
        "status": "success",
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "assessments": paginated,
    }


@router.get("/admin/assessments/stats/summary", dependencies=[Depends(verify_admin_key)])
async def get_admin_assessment_stats():
    """Calculate aggregate analytics, labor-market demand distribution, and skill deficits."""
    try:
        from app.repositories.supabase_repository import list_student_assessments
        assessments = list_student_assessments()
    except Exception as e:
        logger.exception("[AdminStats] Supabase query failed: %s", e)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database query failed retrieving assessment statistics.",
        ) from e

    total_submissions = len(assessments)
    user_submitted_count = sum(1 for a in assessments if a.get("source") == "USER_SUBMITTED")
    demo_synthetic_count = sum(1 for a in assessments if a.get("source") == "DEMO_SYNTHETIC")

    avg_quiz_score = (
        round(sum(a.get("quiz_score_pct", 0) for a in assessments) / max(1, total_submissions), 1)
        if total_submissions > 0 else 0.0
    )
    avg_skill_match = (
        round(sum(a.get("skill_match_pct", 0) for a in assessments) / max(1, total_submissions), 1)
        if total_submissions > 0 else 0.0
    )

    # Distributions
    district_counts = Counter(a.get("district", "Maharashtra") for a in assessments)
    district_distribution = [{"district": k, "count": v} for k, v in district_counts.most_common(10)]

    career_counts = Counter(a.get("career_goal", "Unspecified") for a in assessments)
    career_goal_distribution = [{"career_goal": k, "count": v} for k, v in career_counts.most_common(10)]

    # Missing Skills Aggregation
    missing_skills_counter = Counter()
    for a in assessments:
        eval_summary = a.get("evaluation_summary", {})
        for m in eval_summary.get("missing_skills", []):
            sk_name = m.get("name") if isinstance(m, dict) else str(m)
            if sk_name:
                missing_skills_counter[sk_name] += 1

    top_missing_skills = [
        {"skill_name": k, "deficit_count": v}
        for k, v in missing_skills_counter.most_common(10)
    ]

    # Domain Interests Aggregation
    interests_counter = Counter()
    for a in assessments:
        for interest in a.get("interests", []):
            if interest:
                interests_counter[interest] += 1

    top_interests = [{"domain": k, "count": v} for k, v in interests_counter.most_common(8)]

    # Readiness Distribution
    readiness_counter = Counter()
    for a in assessments:
        lvl = a.get("evaluation_summary", {}).get("readiness_level", "EVALUATED")
        readiness_counter[lvl] += 1

    return {
        "status": "success",
        "total_submissions": total_submissions,
        "user_submitted_count": user_submitted_count,
        "demo_synthetic_count": demo_synthetic_count,
        "avg_quiz_score": avg_quiz_score,
        "avg_skill_match": avg_skill_match,
        "district_distribution": district_distribution,
        "career_goal_distribution": career_goal_distribution,
        "top_missing_skills": top_missing_skills,
        "top_interests": top_interests,
        "readiness_distribution": dict(readiness_counter),
        "data_provenance": "SEPARATED_AUDITED_RECORDS",
        "provenance_note": "User-submitted records represent candidate self-assessments. Demo records are synthetic baseline benchmarks.",
    }


@router.get("/admin/assessments/{assessment_id}", dependencies=[Depends(verify_admin_key)])
async def get_admin_assessment_detail(assessment_id: str):
    """Retrieve full individual student assessment record for administrative audit."""
    a = None
    try:
        from app.repositories.supabase_repository import get_student_assessment
        a = get_student_assessment(assessment_id)
    except Exception as e:
        logger.exception("[AdminAssessmentDetail] Supabase error for %s: %s", assessment_id, e)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database query failed for assessment '{assessment_id}'.",
        ) from e

    if not a and is_demo_student_id(assessment_id):
        assessments = get_demo("student_assessments")
        for item in assessments:
            if item.get("id") == assessment_id:
                a = item
                break

    if a:
        return {"status": "success", "assessment": a}

    raise HTTPException(status_code=404, detail=f"Assessment record '{assessment_id}' not found.")


@router.delete("/admin/assessments/{assessment_id}", dependencies=[Depends(verify_admin_key)])
async def delete_admin_assessment(assessment_id: str):
    """Delete student assessment record from system memory cache and connected database."""
    deleted = False
    try:
        from app.repositories.supabase_repository import delete_student_assessment_repo
        deleted = delete_student_assessment_repo(assessment_id)
    except Exception as e:
        logger.exception("[AdminAssessmentDelete] Supabase deletion failed for %s: %s", assessment_id, e)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database deletion failed for assessment '{assessment_id}'.",
        ) from e

    from app.db import delete_student_assessment
    try:
        cache_deleted = delete_student_assessment(assessment_id)
    except Exception:
        cache_deleted = False

    if deleted or cache_deleted:
        return {
            "status": "success",
            "message": f"Assessment record '{assessment_id}' successfully removed.",
            "deleted_id": assessment_id,
        }

    raise HTTPException(status_code=404, detail=f"Assessment record '{assessment_id}' not found.")


# ============================================================================
# PHASE 14: EMPLOYER DEMAND MANAGEMENT & VALIDATION ENDPOINTS
# ============================================================================

@router.get("/admin/employer/demands", dependencies=[Depends(verify_admin_key)])
async def list_admin_employer_demands(
    district: str | None = Query(None, description="District filter or 'all'"),
    industry: str | None = Query(None, description="Industry filter or 'all'"),
    role: str | None = Query(None, description="Role filter or 'all'"),
    status: str | None = Query(None, description="'PENDING' | 'VALIDATED' | 'REJECTED' | 'all'"),
    source: str | None = Query(None, description="'EMPLOYER_SUBMITTED' | 'DEMO_SYNTHETIC' | 'all'"),
    search: str | None = Query(None, description="Search company name, role, or skills"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    is_demo: bool | None = Query(None, description="Explicit demo/real mode selector"),
):
    """List employer demands for administrative audit and validation with aggregate counts."""
    if is_explicit_demo_mode(is_demo):
        all_demands = get_demo("employer_demands")
    else:
        try:
            from app.repositories.supabase_repository import list_employer_demands
            all_demands = list_employer_demands() or []
        except SupabaseRepositoryError as e:
            logger.exception("[AdminDemands] Repository failure loading demands: %s", e)
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database query failed for administrative listing.",
            ) from e
        except Exception as e:
            logger.warning("[AdminDemands] Failed loading demands from repository: %s", e)
            all_demands = []

    # Calculate overall KPIs
    total_demands = len(all_demands)
    pending_count = sum(1 for d in all_demands if (d.get("validation_status") or d.get("status", "")).upper() == "PENDING")
    validated_count = sum(1 for d in all_demands if (d.get("validation_status") or d.get("status", "")).upper() == "VALIDATED" or d.get("status") == "active")
    rejected_count = sum(1 for d in all_demands if (d.get("validation_status") or d.get("status", "")).upper() == "REJECTED")
    employer_submitted_count = sum(1 for d in all_demands if d.get("source") == "EMPLOYER_SUBMITTED")
    demo_synthetic_count = sum(1 for d in all_demands if d.get("source") == "DEMO_SYNTHETIC")

    results = all_demands

    # 1. District filter
    if district and district.strip() and district.lower() != "all":
        d_clean = district.strip().lower()
        results = [d for d in results if d_clean in d.get("district", "").lower()]

    # 2. Industry filter
    if industry and industry.strip() and industry.lower() != "all":
        i_clean = industry.strip().lower()
        results = [d for d in results if i_clean in d.get("industry", "").lower()]

    # 3. Role filter
    if role and role.strip() and role.lower() != "all":
        r_clean = role.strip().lower()
        results = [
            d for d in results
            if r_clean in d.get("job_role", "").lower() or r_clean in d.get("role_title", "").lower()
        ]

    # 4. Status / Validation status filter
    if status and status.strip() and status.lower() != "all":
        s_clean = status.strip().upper()
        results = [
            d for d in results
            if (d.get("validation_status") or d.get("status", "")).upper() == s_clean
        ]

    # 5. Source filter
    if source and source.strip() and source.lower() != "all":
        src_clean = source.strip().upper()
        results = [d for d in results if d.get("source", "").upper() == src_clean]

    # 6. Search text filter
    if search and search.strip():
        q = search.strip().lower()
        filtered = []
        for d in results:
            company_match = q in (d.get("company_name") or d.get("employer_name") or "").lower()
            role_match = q in (d.get("job_role") or d.get("role_title") or "").lower()
            skills_match = any(q in (s.get("name") if isinstance(s, dict) else str(s)).lower() for s in (d.get("required_skills") or d.get("skills") or []))
            if company_match or role_match or skills_match:
                filtered.append(d)
        results = filtered

    total_filtered = len(results)
    paginated = results[offset : offset + limit]

    return {
        "status": "success",
        "total_demands": total_demands,
        "filtered_count": total_filtered,
        "pending_count": pending_count,
        "validated_count": validated_count,
        "rejected_count": rejected_count,
        "employer_submitted_count": employer_submitted_count,
        "demo_synthetic_count": demo_synthetic_count,
        "limit": limit,
        "offset": offset,
        "demands": paginated,
    }


@router.patch("/admin/employer/demands/{demand_id}", dependencies=[Depends(verify_admin_key)])
@router.patch("/admin/employer/demands/{demand_id}/status", dependencies=[Depends(verify_admin_key)])
async def update_demand_validation_status(demand_id: str, update: DemandValidationUpdate):
    """Mark an employer requirement as VALIDATED or REJECTED after administrative review."""
    raw_status = update.status or update.validation_status
    if not raw_status:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either 'status' or 'validation_status' must be provided.",
        )
    target_status = raw_status.strip().upper()
    if target_status not in {"VALIDATED", "REJECTED", "PENDING"}:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Status must be one of: 'VALIDATED', 'REJECTED', 'PENDING'.",
        )

    try:
        updated = update_employer_demand_status(
            demand_id=demand_id,
            new_status=target_status,
            admin_notes=update.admin_notes,
            validated_by=update.validated_by or "Administrator",
        )
    except Exception as e:
        logger.error("[AdminRouter] Supabase error updating demand status: %s", e)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database update failed for employer demand.",
        ) from e

    if not updated:
        raise HTTPException(status_code=404, detail=f"Employer demand '{demand_id}' not found.")

    return {
        "status": "success",
        "message": f"Employer demand '{demand_id}' successfully marked as {target_status}.",
        "demand": updated,
    }


@router.delete("/admin/employer/demands/{demand_id}", dependencies=[Depends(verify_admin_key)])
async def delete_admin_employer_demand(demand_id: str):
    """Delete employer demand record from system memory cache and database."""
    try:
        deleted = delete_employer_demand(demand_id)
    except Exception as e:
        logger.exception("[AdminRouter] Supabase error deleting demand: %s", e)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database deletion failed for employer demand.",
        ) from e

    if deleted:
        return {
            "status": "success",
            "message": f"Employer demand '{demand_id}' successfully removed.",
            "deleted_id": demand_id,
        }

    raise HTTPException(status_code=404, detail=f"Employer demand '{demand_id}' not found.")


# ============================================================================
# PHASE 15: GOVERNMENT OPPORTUNITIES MANAGEMENT ENDPOINTS
# ============================================================================

class GovOpportunityCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=300)
    department: str = Field(..., min_length=3, max_length=300)
    description: str = Field(default="", max_length=2000)
    eligibility_criteria: str = Field(default="", max_length=1000)
    target_skills: list[str] = Field(default_factory=list)
    district_coverage: str | list[str] = Field(default="State-wide (Maharashtra)")
    opportunity_type: str = Field(default="training_program")
    application_url: str | None = None
    deadline: str | None = None
    status: str = Field(default="active")


class GovOpportunityUpdate(BaseModel):
    name: str | None = None
    department: str | None = None
    description: str | None = None
    eligibility_criteria: str | None = None
    target_skills: list[str] | None = None
    district_coverage: str | list[str] | None = None
    opportunity_type: str | None = None
    application_url: str | None = None
    deadline: str | None = None
    status: str | None = None


@router.get("/admin/gov/opportunities", dependencies=[Depends(verify_admin_key)])
async def list_admin_gov_opportunities(
    district: str | None = Query(None),
    domain: str | None = Query(None),
    opportunity_type: str | None = Query(None),
    status: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    is_demo: bool | None = Query(None, description="Explicit demo/real mode selector"),
):
    """List and filter government opportunities for administrative management."""
    if is_explicit_demo_mode(is_demo):
        all_records = get_demo("gov_opportunities")
    else:
        try:
            from app.repositories.supabase_repository import list_gov_opportunities
            all_records = list_gov_opportunities(limit=1000) or []
        except SupabaseRepositoryError as e:
            logger.exception("[AdminGovOpportunities] Repository failure loading opportunities: %s", e)
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database query failed for administrative listing.",
            ) from e
        except Exception as e:
            logger.warning("[AdminGovOpportunities] Failed loading opportunities: %s", e)
            all_records = []

    results = all_records

    if district and district.lower() != "all":
        d_clean = district.lower()
        filtered = []
        for r in results:
            coverage = r.get("district_coverage", "")
            if isinstance(coverage, list):
                districts = [d.lower() for d in coverage]
            else:
                districts = [coverage.lower()] if coverage else []
            if d_clean in districts or any("state-wide" in d for d in districts):
                filtered.append(r)
        results = filtered

    if domain and domain.lower() != "all":
        d_clean = domain.lower()
        results = [r for r in results if d_clean in [s.lower() for s in (r.get("target_skills") or [])]]

    if opportunity_type and opportunity_type.lower() != "all":
        results = [r for r in results if r.get("opportunity_type", "").lower() == opportunity_type.lower()]

    if status and status.lower() != "all":
        results = [r for r in results if r.get("status", "active").lower() == status.lower()]

    if search and search.strip():
        q = search.strip().lower()
        results = [
            r for r in results
            if q in r.get("name", "").lower() or q in r.get("department", "").lower() or q in r.get("description", "").lower()
        ]

    total_all = len(all_records)
    active_count = sum(1 for r in all_records if r.get("status", "active").lower() == "active")
    inactive_count = total_all - active_count
    demo_count = sum(1 for r in all_records if r.get("source") == "DEMO_SYNTHETIC")

    return {
        "status": "success",
        "total": total_all,
        "active_count": active_count,
        "inactive_count": inactive_count,
        "demo_count": demo_count,
        "filtered_count": len(results),
        "limit": limit,
        "offset": offset,
        "opportunities": results[offset: offset + limit],
    }


@router.post("/admin/gov/opportunities", dependencies=[Depends(verify_admin_key)])
async def create_admin_gov_opportunity(data: GovOpportunityCreate):
    """Create a new government opportunity record."""
    record = {
        "id": f"gov-{uuid.uuid4().hex[:8]}",
        "name": data.name,
        "department": data.department,
        "description": data.description,
        "eligibility_criteria": data.eligibility_criteria,
        "target_skills": data.target_skills,
        "district_coverage": data.district_coverage,
        "opportunity_type": data.opportunity_type,
        "application_url": data.application_url,
        "deadline": data.deadline,
        "source": "ADMIN_CREATED",
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "status": data.status,
        "is_demo": False,
    }

    saved = save_gov_opportunity(record)
    return {
        "status": "success",
        "message": f"Government opportunity '{saved['id']}' created.",
        "opportunity": saved,
    }


@router.patch("/admin/gov/opportunities/{opp_id}", dependencies=[Depends(verify_admin_key)])
async def update_admin_gov_opportunity(opp_id: str, data: GovOpportunityUpdate):
    """Update fields on a government opportunity record."""
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=422, detail="No fields to update.")

    updates["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    updated = update_gov_opportunity(opp_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Government opportunity '{opp_id}' not found.")

    return {
        "status": "success",
        "message": f"Government opportunity '{opp_id}' updated.",
        "opportunity": updated,
    }


@router.delete("/admin/gov/opportunities/{opp_id}", dependencies=[Depends(verify_admin_key)])
async def delete_admin_gov_opportunity(opp_id: str):
    """Delete a government opportunity record."""
    deleted = delete_gov_opportunity(opp_id)
    if deleted:
        return {
            "status": "success",
            "message": f"Government opportunity '{opp_id}' removed.",
            "deleted_id": opp_id,
        }

    raise HTTPException(status_code=404, detail=f"Government opportunity '{opp_id}' not found.")


# ============================================================================
# PHASE 25: INSTITUTE COURSES & VOCATIONAL PROGRAMS MANAGEMENT ENDPOINTS
# ============================================================================

class AdminCourseUpdate(BaseModel):
    name: str | None = None
    institute: str | None = None
    district: str | None = None
    category: str | None = None
    description: str | None = None
    skills: list[str] | None = None
    nsqf_level: int | None = None
    enrolment_count: int | None = None
    placed_count: int | None = None
    status: str | None = None


@router.get("/admin/institute/courses", dependencies=[Depends(verify_admin_key)])
@router.get("/admin/courses", dependencies=[Depends(verify_admin_key)])
async def list_admin_courses(
    district: str | None = Query(None),
    category: str | None = Query(None),
    skill: str | None = Query(None),
    source: str | None = Query(None),
    status: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List and audit academic & vocational course records with source separation."""
    from app.repositories.supabase_repository import list_courses, SupabaseRepositoryError
    try:
        all_courses = list_courses(
            district=district,
            category=category,
            source=source,
            status=status,
        )
    except SupabaseRepositoryError as e:
        logger.exception("[Admin] Failed querying courses from Supabase: %s", e)
        raise HTTPException(
            status_code=500,
            detail="Database query failed for courses.",
        )

    results = all_courses

    if district and district.lower() != "all":
        d_clean = district.strip().lower()
        results = [c for c in results if d_clean in c.get("district", "").lower()]

    if category and category.lower() != "all":
        cat_clean = category.strip().lower()
        results = [c for c in results if cat_clean in c.get("category", "").lower()]

    if skill and skill.lower() != "all":
        sk_clean = skill.strip().lower()
        results = [
            c for c in results
            if any(sk_clean in s.lower() for s in (c.get("skills") or c.get("skills_taught") or []))
        ]

    if source and source.lower() != "all":
        src_clean = source.strip().lower()
        results = [c for c in results if src_clean == c.get("source", "DEMO_SYNTHETIC").lower()]

    if status and status.lower() != "all":
        st_clean = status.strip().lower()
        results = [c for c in results if st_clean == c.get("status", "active").lower()]

    if search and search.strip():
        q = search.strip().lower()
        results = [
            c for c in results
            if q in c.get("name", "").lower()
            or q in (c.get("institute") or c.get("institute_name") or "").lower()
            or q in c.get("description", "").lower()
            or any(q in s.lower() for s in (c.get("skills") or []))
        ]

    total_all = len(all_courses)
    user_submitted_count = sum(1 for c in all_courses if c.get("source") == "USER_SUBMITTED")
    demo_synthetic_count = total_all - user_submitted_count

    return {
        "status": "success",
        "total": total_all,
        "user_submitted_count": user_submitted_count,
        "demo_synthetic_count": demo_synthetic_count,
        "filtered_count": len(results),
        "limit": limit,
        "offset": offset,
        "courses": results[offset : offset + limit],
    }


@router.patch("/admin/institute/courses/{course_id}", dependencies=[Depends(verify_admin_key)])
@router.patch("/admin/courses/{course_id}", dependencies=[Depends(verify_admin_key)])
async def update_admin_course(course_id: str, data: AdminCourseUpdate):
    """Administratively update course syllabus, status, and placement health."""
    from app.repositories.supabase_repository import (
        update_course_repo,
        CourseNotFoundError,
        SupabaseRepositoryError,
    )
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=422, detail="No fields to update.")

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    try:
        updated = update_course_repo(course_id, updates)
    except CourseNotFoundError:
        raise HTTPException(status_code=404, detail=f"Course '{course_id}' not found.")
    except SupabaseRepositoryError as e:
        logger.exception("[Admin] Failed updating course '%s' in Supabase: %s", course_id, e)
        raise HTTPException(
            status_code=500,
            detail="Database update failed for course.",
        )

    try:
        update_course(course_id, updates)
    except Exception:
        pass

    return {
        "status": "success",
        "message": f"Course '{course_id}' updated.",
        "course": updated,
    }


@router.delete("/admin/institute/courses/{course_id}", dependencies=[Depends(verify_admin_key)])
@router.delete("/admin/courses/{course_id}", dependencies=[Depends(verify_admin_key)])
async def delete_admin_course(course_id: str):
    """Administratively remove a course record."""
    from app.repositories.supabase_repository import (
        delete_course_repo,
        SupabaseRepositoryError,
    )
    try:
        deleted = delete_course_repo(course_id)
    except SupabaseRepositoryError as e:
        logger.exception("[Admin] Failed deleting course '%s' from Supabase: %s", course_id, e)
        raise HTTPException(
            status_code=500,
            detail="Database deletion failed for course.",
        )

    if deleted:
        try:
            delete_course(course_id)
        except Exception:
            pass
        return {
            "status": "success",
            "message": f"Course '{course_id}' removed.",
            "deleted_id": course_id,
        }

    raise HTTPException(status_code=404, detail=f"Course '{course_id}' not found.")


# ---------------------------------------------------------------------------
# Phase 26: Industry Intelligence & Automated Ingestion Admin APIs
# ---------------------------------------------------------------------------

class IndustrySignalAdminUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    category: str | None = None
    industry: str | None = None
    skills: list[str] | None = None
    tools: list[str] | None = None
    validation_status: str | None = None  # APPROVED, PENDING, REJECTED, ARCHIVED
    is_active: bool | None = None
    admin_notes: str | None = None


@router.post("/admin/industry/ingest", dependencies=[Depends(verify_admin_key)])
async def trigger_admin_industry_ingestion(feeds: list[dict[str, Any]] | None = None):
    """Admin endpoint to manually trigger automated ingestion across trusted industry feeds."""
    from app.core.data_mode import is_explicit_demo_mode
    result = industry_ingestor.ingest_from_feeds(feeds, is_demo=is_explicit_demo_mode())
    return {
        "status": "success",
        "message": f"Industry ingestion run finished: {result['records_added']} added, {result['records_updated']} updated, {result['records_duplicated']} duplicated, {result['records_rejected']} rejected.",
        "summary": result,
    }


@router.get("/admin/industry/signals", dependencies=[Depends(verify_admin_key)])
async def list_admin_industry_signals(
    category: str | None = Query(None),
    industry: str | None = Query(None),
    status: str | None = Query(None),  # APPROVED, PENDING, REJECTED, ARCHIVED, all
    freshness: str | None = Query(None),  # NEW, RECENT, OLDER, EXPIRED, all
    source: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    is_demo: bool | None = Query(None, description="Explicit demo/real mode selector"),
):
    """Admin endpoint to view, filter, and audit all industry signals including pending/rejected."""
    from app.repositories.supabase_repository import list_industry_signals as list_industry_signals_repo, SupabaseRepositoryError
    try:
        raw_signals = list_industry_signals_repo()
    except SupabaseRepositoryError as e:
        logger.exception("[AdminSignals] Failed querying signals: %s", e)
        raise HTTPException(status_code=500, detail="Industry signals database unavailable.")
    if is_explicit_demo_mode(is_demo):
        skills_map = {s["id"]: s["name"] for s in get_demo("skills")}
    else:
        try:
            from app.repositories.supabase_repository import list_skills
            skills_map = {s["id"]: s.get("name", s["id"]) for s in (list_skills() or []) if "id" in s}
        except Exception:
            skills_map = {}

    # Normalize all records for admin view
    results = []
    for s in raw_signals:
        pub = s.get("published_at") or (f"{s['signal_date']}T00:00:00Z" if s.get("signal_date") else "2026-01-01T00:00:00Z")
        is_act = s.get("is_active", True)
        val_st = s.get("validation_status", "APPROVED")
        fresh = s.get("freshness") or calculate_freshness(pub, is_act, val_st)

        skills = s.get("skills", [])
        if not skills and "affected_skills" in s:
            skills = [skills_map.get(sid, sid) for sid in s.get("affected_skills", [])]

        results.append({
            "id": s.get("id"),
            "title": s.get("title"),
            "description": s.get("description") or s.get("summary") or "",
            "category": s.get("category", "INDUSTRY_DEMAND"),
            "industry": s.get("industry") or s.get("technology") or "Cross-Sector Tech",
            "skills": skills,
            "tools": s.get("tools", []),
            "source_name": s.get("source_name") or s.get("source") or "Industry Analysis",
            "source_url": s.get("source_url") or "https://data.gov.in",
            "source_type": s.get("source_type") or "INDUSTRY_ANNOUNCEMENT",
            "published_at": pub,
            "collected_at": s.get("collected_at") or pub,
            "updated_at": s.get("updated_at") or pub,
            "validation_status": val_st,
            "is_active": is_act,
            "is_demo": s.get("is_demo", s.get("source_label") == "DEMO_SYNTHETIC"),
            "data_provenance": s.get("data_provenance") or ("DEMO_SYNTHETIC" if s.get("source_label") == "DEMO_SYNTHETIC" else "UNVERIFIED_EXTERNAL_SOURCE"),
            "freshness": fresh,
            "admin_notes": s.get("admin_notes"),
            "is_ai_processed": s.get("is_ai_processed", False),
        })

    # Total counts before query filtering
    total_count = len(results)
    approved_count = sum(1 for r in results if r["validation_status"] == "APPROVED")
    pending_count = sum(1 for r in results if r["validation_status"] == "PENDING")
    rejected_count = sum(1 for r in results if r["validation_status"] == "REJECTED")
    active_count = sum(1 for r in results if r["is_active"] is True)
    fresh_count = sum(1 for r in results if r["freshness"] == "NEW")

    # Apply filters
    if category and category.lower() != "all":
        results = [r for r in results if r["category"].lower() == category.lower()]

    if industry and industry.lower() != "all":
        results = [r for r in results if industry.lower() in r["industry"].lower()]

    if status and status.lower() != "all":
        results = [r for r in results if r["validation_status"].lower() == status.lower()]

    if freshness and freshness.lower() != "all":
        results = [r for r in results if r["freshness"].lower() == freshness.lower()]

    if source and source.lower() != "all":
        results = [r for r in results if source.lower() in r["source_name"].lower()]

    if search and search.strip():
        q = search.strip().lower()
        results = [
            r for r in results
            if q in r["title"].lower()
            or q in r["description"].lower()
            or any(q in sk.lower() for sk in r["skills"])
            or any(q in tl.lower() for tl in r["tools"])
            or q in r["industry"].lower()
            or q in r["source_name"].lower()
        ]

    # Sort descending by published_at
    results.sort(key=lambda x: x["published_at"], reverse=True)

    return {
        "status": "success",
        "total": total_count,
        "approved_count": approved_count,
        "pending_count": pending_count,
        "rejected_count": rejected_count,
        "active_count": active_count,
        "fresh_count": fresh_count,
        "filtered_count": len(results),
        "limit": limit,
        "offset": offset,
        "signals": results[offset : offset + limit],
    }


@router.patch("/admin/industry/signals/{signal_id}", dependencies=[Depends(verify_admin_key)])
async def update_admin_industry_signal(signal_id: str, updates: IndustrySignalAdminUpdate):
    """Admin endpoint to approve, reject, archive, activate, or edit an industry signal."""
    matched = get_industry_signal_by_id(signal_id)
    if not matched:
        raise HTTPException(status_code=404, detail=f"Industry signal '{signal_id}' not found.")

    patch_dict = {k: v for k, v in updates.model_dump().items() if v is not None}
    if not patch_dict:
        raise HTTPException(status_code=422, detail="No fields provided for update.")

    now_iso = datetime.now(timezone.utc).isoformat()
    patch_dict["updated_at"] = now_iso

    # Recalculate freshness if status or active flag updated
    is_act = patch_dict.get("is_active", matched.get("is_active", True))
    val_st = patch_dict.get("validation_status", matched.get("validation_status", "APPROVED"))
    pub = matched.get("published_at") or now_iso
    patch_dict["freshness"] = calculate_freshness(pub, is_act, val_st)

    updated = update_industry_signal(signal_id, patch_dict)
    return {
        "status": "success",
        "message": f"Industry signal '{signal_id}' updated.",
        "signal": updated,
    }


@router.delete("/admin/industry/signals/{signal_id}", dependencies=[Depends(verify_admin_key)])
async def delete_admin_industry_signal(signal_id: str):
    """Admin endpoint to permanently delete an industry signal record."""
    deleted = delete_industry_signal(signal_id)
    if deleted:
        return {
            "status": "success",
            "message": f"Industry signal '{signal_id}' removed.",
            "deleted_id": signal_id,
        }
    raise HTTPException(status_code=404, detail=f"Industry signal '{signal_id}' not found.")


@router.get("/admin/industry/ingestion-status", dependencies=[Depends(verify_admin_key)])
async def get_admin_industry_ingestion_status():
    """Admin endpoint to view overall status, registered feeds, and audit telemetry."""
    status_data = industry_ingestor.get_ingestion_status()
    return {
        "status": "success",
        "ingestion_status": status_data,
    }


# ============================================================================
# Phase 32F: Admin Skill Forecasts Management
# ============================================================================

class SkillForecastAdminCreate(BaseModel):
    skill_id: str
    period: str = Field("12m", description="'6m' | '12m' | '24m'")
    current_demand: str = Field("medium", description="'low' | 'medium' | 'high' | 'very_high'")
    future_demand: str = Field("high", description="'low' | 'medium' | 'high' | 'very_high'")
    trend: str = Field("rising", description="'rising' | 'stable' | 'declining'")
    confidence: int = Field(80, ge=0, le=100)


class SkillForecastAdminUpdate(BaseModel):
    current_demand: str | None = None
    future_demand: str | None = None
    trend: str | None = None
    confidence: int | None = None


@router.get("/admin/forecasts", dependencies=[Depends(verify_admin_key)])
async def list_admin_forecasts(
    skill_id: str | None = Query(None),
    period: str | None = Query(None),
    trend: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Admin endpoint to view and filter skill forecasts directly from Supabase."""
    from app.repositories.supabase_repository import list_skill_forecasts, SupabaseRepositoryError
    try:
        forecasts = list_skill_forecasts(
            skill_id=skill_id,
            period=period,
            trend=trend,
            limit=limit,
            offset=offset,
        )
        return {
            "status": "success",
            "total": len(forecasts),
            "forecasts": forecasts,
        }
    except SupabaseRepositoryError as e:
        logger.exception("[AdminForecasts] Supabase query failed: %s", e)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database query failed listing forecasts.",
        ) from e


@router.post("/admin/forecasts", dependencies=[Depends(verify_admin_key)])
async def create_admin_forecast(payload: SkillForecastAdminCreate):
    """Admin endpoint to create or upsert a skill forecast record into Supabase."""
    from app.repositories.supabase_repository import create_skill_forecast, SupabaseRepositoryError
    try:
        created = create_skill_forecast(payload.model_dump())
        return {
            "status": "success",
            "message": f"Skill forecast for '{payload.skill_id}' ({payload.period}) persisted.",
            "forecast": created,
        }
    except SupabaseRepositoryError as e:
        logger.exception("[AdminForecasts] Supabase persistence failed: %s", e)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database persistence failed for skill forecast.",
        ) from e


@router.patch("/admin/forecasts/{forecast_id}", dependencies=[Depends(verify_admin_key)])
async def update_admin_forecast(forecast_id: str, updates: SkillForecastAdminUpdate):
    """Admin endpoint to update a skill forecast record in Supabase."""
    from app.repositories.supabase_repository import (
        update_skill_forecast_repo,
        SkillForecastNotFoundError,
        SupabaseRepositoryError,
    )
    patch_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    if not patch_data:
        raise HTTPException(status_code=422, detail="No fields provided for update.")
    try:
        updated = update_skill_forecast_repo(forecast_id, patch_data)
        return {
            "status": "success",
            "message": f"Skill forecast '{forecast_id}' updated.",
            "forecast": updated,
        }
    except SkillForecastNotFoundError:
        raise HTTPException(status_code=404, detail=f"Skill forecast '{forecast_id}' not found.")
    except SupabaseRepositoryError as e:
        logger.exception("[AdminForecasts] Supabase update failed for %s: %s", forecast_id, e)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database update failed for skill forecast '{forecast_id}'.",
        ) from e


@router.delete("/admin/forecasts/{forecast_id}", dependencies=[Depends(verify_admin_key)])
async def delete_admin_forecast(forecast_id: str):
    """Admin endpoint to delete a skill forecast record from Supabase."""
    from app.repositories.supabase_repository import (
        delete_skill_forecast_repo,
        SupabaseRepositoryError,
    )
    try:
        deleted = delete_skill_forecast_repo(forecast_id)
        if deleted:
            return {
                "status": "success",
                "message": f"Skill forecast '{forecast_id}' removed.",
                "deleted_id": forecast_id,
            }
        raise HTTPException(status_code=404, detail=f"Skill forecast '{forecast_id}' not found.")
    except SupabaseRepositoryError as e:
        logger.exception("[AdminForecasts] Supabase deletion failed for %s: %s", forecast_id, e)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database deletion failed for skill forecast '{forecast_id}'.",
        ) from e


@router.post("/admin/forecasts/recompute", dependencies=[Depends(verify_admin_key)])
async def recompute_admin_forecasts():
    """Admin endpoint to recompute and authoritatively persist multi-horizon forecasts to Supabase."""
    from app.services.forecast_engine import persist_computed_forecasts
    from app.repositories.supabase_repository import SupabaseRepositoryError
    try:
        persisted = persist_computed_forecasts()
        return {
            "status": "success",
            "message": f"Recomputed and persisted {len(persisted)} forecast records to Supabase.",
            "count": len(persisted),
        }
    except SupabaseRepositoryError as e:
        logger.exception("[AdminForecasts] Recomputation failed: %s", e)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database persistence failed during forecast recomputation.",
        ) from e
