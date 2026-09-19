"""Employer Validation & Industry Demand API — confirm/correct/reject skill demand, submit requirements, and track talent deficits."""
import datetime
import logging
import uuid
from collections import Counter
from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from app.core.security import get_current_user, get_optional_current_user, require_roles
from pydantic import BaseModel, Field, model_validator
from app.core.data_mode import is_explicit_demo_mode
from app.db import get_demo, save_employer_record
from app.services.employer_verification import verify_employer_credentials, validate_gstin
from app.repositories.supabase_repository import (
    get_employer_feedback,
    list_employer_feedback,
    update_employer_feedback,
    FeedbackNotFoundError,
    get_employer_demand,
    list_employer_demands,
    create_employer_demand,
    update_employer_demand,
    delete_employer_demand_repo,
    DemandNotFoundError,
    SupabaseRepositoryError,
    get_employer,
    upsert_employer,
    create_employer_verification,
    get_latest_employer_verification,
)

logger = logging.getLogger("skillsetu.employer")
router = APIRouter()


class FeedbackSubmission(BaseModel):
    feedback_id: str
    status: str  # confirmed, corrected, rejected
    notes: str | None = None
    proficiency_required: str | None = None


class DemandSubmission(BaseModel):
    employer_id: str | None = None
    company: str | None = None
    company_name: str | None = None
    employer_name: str | None = None
    gstin: str | None = Field(default=None, description="Optional 15-character Indian GSTIN")
    corporate_website: str | None = Field(default=None, description="Optional company domain/URL")
    industry: str = Field(..., min_length=2, max_length=150)
    district: str = Field(..., min_length=2, max_length=100)
    title: str | None = None
    job_role: str | None = None
    role_title: str | None = None
    required_skills: list[str] | None = None
    skills: list[str] | None = None
    preferred_proficiency: str = "intermediate"
    proficiency_required: str | None = None
    openings: int | None = None
    openings_count: int | None = None
    positions_count: int | None = None
    experience_level: str = "Entry Level (0-1 yrs)"
    hiring_timeline: str = "Immediate (0-30 days)"
    urgency: str | None = None
    additional_requirements: str | None = None
    hiring_challenge: str | None = None
    nsqf_level: int = 5

    @model_validator(mode="after")
    def validate_company_and_skills(self):
        c_name = (self.company_name or self.employer_name or self.company or "").strip()
        if len(c_name) < 2:
            raise ValueError("Company or employer name must be at least 2 characters.")
        r_skills = self.required_skills or self.skills or []
        if not r_skills or len(r_skills) == 0:
            raise ValueError("At least one required skill must be specified.")
        return self


class EmployerDemandSubmission(DemandSubmission):
    pass


@router.get("/employer/validate")
async def list_validations(
    status: str | None = None,
    district: str | None = None,
    industry: str | None = None,
    demand_level: str | None = None,
    is_demo: bool | None = Query(None, description="Explicit demo/real mode selector"),
):
    """List skill demand summaries for employer validation with enriched metadata and filtering."""
    if is_explicit_demo_mode(is_demo):
        feedback = get_demo("employer_feedback")
        skills_map = {s["id"]: s for s in get_demo("skills")}
        employers_map = {e["id"]: e for e in get_demo("employers")}
    else:
        feedback = list_employer_feedback(status=status, demand_level=demand_level)
        try:
            from app.repositories.supabase_repository import list_skills
            repo_skills = list_skills(limit=10000) or []
            skills_map = {s["id"]: s for s in repo_skills if "id" in s}
        except SupabaseRepositoryError as e:
            raise HTTPException(
                status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skills repository is temporarily unavailable.",
            ) from e
        except Exception:
            skills_map = {}
        try:
            from app.repositories.supabase_repository import get_client
            client = get_client()
            res = client.table("employers").select("*").execute()
            employers_map = {e["id"]: e for e in (res.data or []) if "id" in e}
        except Exception as e:
            raise HTTPException(
                status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Employer repository is temporarily unavailable.",
            ) from e

    results = []
    is_demo_active = is_explicit_demo_mode(is_demo)
    for f in feedback:
        skill_info = skills_map.get(f.get("skill_id"), {})
        has_employer = f.get("employer_id") in employers_map
        employer_info = employers_map.get(f.get("employer_id"), {})

        item = {
            **f,
            "skill_name": skill_info.get("name", "Unknown Skill"),
            "skill_category": skill_info.get("category", "General"),
            "nsqf_level": skill_info.get("nsqf_level", 5),
            "employer_name": employer_info.get("name") if has_employer else ("Industry Partner" if is_demo_active else None),
            "industry": employer_info.get("industry") if has_employer else ("General Industry" if is_demo_active else None),
            "district": employer_info.get("district") if has_employer else ("Maharashtra" if is_demo_active else None),
        }

        if status and status != "all" and item.get("status", "").lower() != status.lower():
            continue
        if district and district != "all":
            if not item.get("district") or item.get("district", "").lower() != district.lower():
                continue
        if industry and industry != "all":
            if not item.get("industry") or item.get("industry", "").lower() != industry.lower():
                continue
        if demand_level and demand_level != "all" and item.get("demand_level", "").lower() != demand_level.lower():
            continue

        results.append(item)

    return results


@router.post("/employer/feedback")
async def submit_feedback(
    submission: FeedbackSubmission,
    current_user: dict = Depends(get_current_user),
):
    """Submit employer validation (confirm/correct/reject) with authentication, role enforcement, and ownership isolation."""
    user_role = (current_user.get("role") or "").upper()
    if user_role not in ("EMPLOYER", "ADMIN"):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Insufficient role permissions. Required one of: ['EMPLOYER', 'ADMIN']",
        )

    try:
        matched = get_employer_feedback(submission.feedback_id)
    except SupabaseRepositoryError as e:
        logger.exception("[Employer] Database query error for feedback '%s': %s", submission.feedback_id, e)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database query error.",
        ) from e

    if not matched:
        return {"error": "feedback not found"}

    if user_role == "EMPLOYER":
        user_org = current_user.get("organization_id")
        user_id = current_user.get("id")
        user_email = current_user.get("email")
        f_employer_id = matched.get("employer_id")
        f_user_id = matched.get("user_id")
        f_user_email = matched.get("user_email")

        is_authorized = (
            (user_org and f_employer_id and user_org.lower() == f_employer_id.lower())
            or (user_id and f_user_id and user_id == f_user_id)
            or (user_email and f_user_email and user_email.lower() == f_user_email.lower())
            or (f_employer_id and user_id and f_employer_id == f"emp-{user_id}")
        )
        if not is_authorized:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You do not have permission to modify another employer's feedback.",
            )

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    updates = {
        "status": submission.status,
        "updated_at": now_iso,
        "source": "USER_SUBMITTED",
        "is_demo": False,
    }
    if submission.notes is not None:
        updates["notes"] = submission.notes
    if submission.proficiency_required is not None:
        updates["proficiency_required"] = submission.proficiency_required
    if current_user.get("id"):
        updates["user_id"] = current_user.get("id")
    if current_user.get("email"):
        updates["user_email"] = current_user.get("email")

    try:
        updated = update_employer_feedback(submission.feedback_id, updates)
    except FeedbackNotFoundError:
        return {"error": "feedback not found"}
    except SupabaseRepositoryError as e:
        logger.exception("[Employer] Database update failed for feedback '%s': %s", submission.feedback_id, e)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database update failed.",
        ) from e

    return {"status": "updated", "feedback": updated}


from app.core.security import get_current_user, get_optional_current_user, require_roles
from fastapi import Depends


class DemandUpdate(BaseModel):
    company_name: str | None = None
    industry: str | None = None
    district: str | None = None
    job_role: str | None = None
    required_skills: list[str] | None = None
    preferred_proficiency: str | None = None
    openings_count: int | None = None
    experience_level: str | None = None
    hiring_timeline: str | None = None
    additional_requirements: str | None = None
    nsqf_level: int | None = None


@router.post("/employer/demand")
@router.post("/employer/demands")
async def submit_demand(
    submission: EmployerDemandSubmission,
    current_user: dict = Depends(require_roles(["EMPLOYER", "ADMIN"])),
):
    """Submit new employer hiring requirements and skill demand signal into intelligence loop."""
    user_role = (current_user.get("role") or "").upper()
    user_org = current_user.get("organization_id")
    user_id = current_user.get("id")

    # Reject client spoofing: If user is EMPLOYER and client supplies an employer_id that does not match authenticated identity
    if user_role == "EMPLOYER":
        auth_employer_id = user_org or f"emp-{user_id}"
        if submission.employer_id and user_org and submission.employer_id.strip().lower() != user_org.strip().lower():
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Cannot submit hiring demand on behalf of another organization.",
            )
        company = (submission.company_name or submission.employer_name or user_org or current_user.get("full_name") or "").strip()
    else:
        auth_employer_id = submission.employer_id or user_org or f"emp-{user_id}"
        company = (submission.company_name or submission.employer_name or user_org or current_user.get("full_name") or "").strip()

    role = (submission.job_role or submission.role_title or "").strip()
    skills_list = submission.required_skills or submission.skills or []

    if not company:
        raise HTTPException(status_code=422, detail="Company / Employer name is required.")
    if not role:
        raise HTTPException(status_code=422, detail="Target Job Role is required.")
    if not skills_list:
        raise HTTPException(status_code=422, detail="At least one required skill must be specified.")

    demand_id = f"ed-{uuid.uuid4().hex[:8]}"
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    now_date = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    prof = submission.preferred_proficiency or submission.proficiency_required or "intermediate"
    openings = submission.openings_count or submission.positions_count or 5
    timeline = submission.hiring_timeline or submission.urgency or "Immediate (0-30 days)"
    notes = submission.additional_requirements or submission.hiring_challenge or ""

    # Phase 34: Employer Identity & Corporate Pedigree verification
    verification = verify_employer_credentials(
        email=current_user.get("email"),
        gstin=submission.gstin,
        company_name=company,
    )
    admin_verification_note = f"[{verification['badge']}] {verification['description']}"

    demand_record = {
        "id": demand_id,
        "demand_id": demand_id,
        "employer_id": auth_employer_id,
        "company_name": company,
        "employer_name": company,
        "industry": submission.industry.strip(),
        "district": submission.district.strip(),
        "job_role": role,
        "role_title": role,
        "required_skills": skills_list,
        "skills": skills_list,
        "preferred_proficiency": prof,
        "proficiency_required": prof,
        "openings_count": max(1, openings),
        "positions_count": max(1, openings),
        "experience_level": submission.experience_level,
        "hiring_timeline": timeline,
        "urgency": timeline.lower().replace(" ", "_"),
        "additional_requirements": notes,
        "hiring_challenge": notes,
        "nsqf_level": submission.nsqf_level,
        "source": "EMPLOYER_SUBMITTED",
        "validation_status": "PENDING",
        "provenance_label": "Employer Submitted — Pending Validation",
        "is_demo": False,
        "submitted_at": now_iso,
        "submitted_date": now_date,
        "updated_at": now_iso,
        "status": "pending",
        "admin_notes": admin_verification_note,
        "user_id": current_user.get("id"),
        "user_email": current_user.get("email"),
    }

    try:
        saved = create_employer_demand(demand_record)
    except SupabaseRepositoryError as e:
        logger.exception("[Employer] Database insertion failed: %s", e)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database insertion failed.",
        ) from e

    return {
        "status": "created",
        "message": "Hiring requirement submitted for validation.",
        "demand": {
            **saved,
            "gstin": submission.gstin.strip().upper() if submission.gstin else None,
            "verification_tier": verification["verification_tier"],
            "verification_badge": verification["badge"],
            "is_verified": verification["verified"],
            "verification_details": verification,
        },
    }


class EmployerIdentityVerifyRequest(BaseModel):
    email: str | None = None
    gstin: str | None = None
    company_name: str | None = None


@router.post("/employer/verify-identity")
async def verify_employer_identity_endpoint(
    payload: EmployerIdentityVerifyRequest,
    current_user: dict | None = Depends(get_optional_current_user),
):
    """Verify an employer's corporate email domain and GSTIN registration credentials."""
    target_email = payload.email or (current_user.get("email") if current_user else None)
    target_company = payload.company_name or (current_user.get("organization_id") if current_user else None)
    return verify_employer_credentials(
        email=target_email,
        gstin=payload.gstin,
        company_name=target_company,
    )


@router.get("/employer/me/demands")
@router.get("/employer/my-demands")
@router.get("/employer/demands/mine")
async def list_my_demands(current_user: dict = Depends(require_roles(["EMPLOYER", "ADMIN"]))):
    """Retrieve hiring requirements submitted by the current authenticated employer account."""
    try:
        all_demands = list_employer_demands()
    except SupabaseRepositoryError as e:
        logger.exception("[Employer] Database query error for my demands: %s", e)
        raise HTTPException(status_code=500, detail="Database query error.") from e

    user_id = current_user.get("id")
    org_id = current_user.get("organization_id")
    email = current_user.get("email")

    if current_user.get("role", "").upper() == "ADMIN":
        my_demands = [d for d in all_demands if d.get("source") in ("USER_SUBMITTED", "EMPLOYER_SUBMITTED") or d.get("is_demo") is False]
    else:
        my_demands = [
            d for d in all_demands
            if d.get("user_id") == user_id or (org_id and d.get("employer_id") == org_id) or (email and d.get("user_email") == email)
        ]

    return {
        "status": "success",
        "total": len(my_demands),
        "demands": my_demands,
    }


@router.patch("/employer/demands/{demand_id}")
async def update_my_demand(
    demand_id: str,
    updates: DemandUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update employer demand record with ownership isolation."""
    try:
        matched = get_employer_demand(demand_id)
    except SupabaseRepositoryError as e:
        logger.exception("[Employer] Database query error for demand '%s': %s", demand_id, e)
        raise HTTPException(status_code=500, detail="Database query error.") from e

    if not matched:
        raise HTTPException(status_code=404, detail=f"Employer demand '{demand_id}' not found.")

    user_role = (current_user.get("role") or "").upper()
    is_owner = (
        matched.get("user_id") == current_user.get("id")
        or (current_user.get("organization_id") and matched.get("employer_id") == current_user.get("organization_id"))
        or (current_user.get("email") and matched.get("user_email") == current_user.get("email"))
    )

    if user_role != "ADMIN" and not is_owner:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to modify another employer's demand record.",
        )

    patch_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    if not patch_data:
        raise HTTPException(status_code=422, detail="No fields provided for update.")

    patch_data["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        updated = update_employer_demand(demand_id, patch_data)
    except DemandNotFoundError:
        raise HTTPException(status_code=404, detail=f"Employer demand '{demand_id}' not found.")
    except SupabaseRepositoryError as e:
        logger.exception("[Employer] Database update failed for demand '%s': %s", demand_id, e)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database update failed.",
        ) from e

    return {"status": "success", "message": "Employer demand updated.", "demand": updated}


@router.delete("/employer/demands/{demand_id}")
async def delete_my_demand(
    demand_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete employer demand record with ownership check."""
    try:
        matched = get_employer_demand(demand_id)
    except SupabaseRepositoryError as e:
        logger.exception("[Employer] Database query error for demand '%s': %s", demand_id, e)
        raise HTTPException(status_code=500, detail="Database query error.") from e

    if not matched:
        raise HTTPException(status_code=404, detail=f"Employer demand '{demand_id}' not found.")

    user_role = (current_user.get("role") or "").upper()
    is_owner = (
        matched.get("user_id") == current_user.get("id")
        or (current_user.get("organization_id") and matched.get("employer_id") == current_user.get("organization_id"))
        or (current_user.get("email") and matched.get("user_email") == current_user.get("email"))
    )

    if user_role != "ADMIN" and not is_owner:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to delete another employer's demand record.",
        )

    try:
        delete_employer_demand_repo(demand_id)
    except SupabaseRepositoryError as e:
        logger.exception("[Employer] Database deletion failed for demand '%s': %s", demand_id, e)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database deletion failed.",
        ) from e

    return {"status": "success", "message": f"Employer demand '{demand_id}' deleted."}


@router.get("/employer/demands")
async def list_demands(
    district: str | None = None,
    industry: str | None = None,
    role: str | None = None,
    status: str | None = None,
    validation_status: str | None = None,
    source: str | None = None,
):
    """List employer-submitted skill demands with multi-parameter filtering."""
    try:
        demands = list_employer_demands()
    except SupabaseRepositoryError:
        demands = []
    results = demands

    if district and district.lower() != "all":
        d_clean = district.strip().lower()
        results = [d for d in results if d_clean in d.get("district", "").lower()]

    if industry and industry.lower() != "all":
        i_clean = industry.strip().lower()
        results = [d for d in results if i_clean in d.get("industry", "").lower()]

    if role and role.lower() != "all":
        r_clean = role.strip().lower()
        results = [
            d for d in results
            if r_clean in d.get("job_role", "").lower() or r_clean in d.get("role_title", "").lower()
        ]

    # Status / validation_status filter
    target_status = validation_status or status
    if target_status and target_status.lower() != "all":
        s_clean = target_status.strip().lower()
        results = [
            d for d in results
            if s_clean == d.get("validation_status", "").lower() or s_clean == d.get("status", "").lower()
        ]

    if source and source.lower() != "all":
        src_clean = source.strip().lower()
        results = [d for d in results if src_clean == d.get("source", "").lower()]

    return results


@router.get("/employer/demands/{demand_id}")
async def get_demand_detail(demand_id: str):
    """Retrieve detailed individual employer hiring demand record."""
    try:
        d = get_employer_demand(demand_id)
    except SupabaseRepositoryError as e:
        logger.exception("[Employer] Database query error for demand '%s': %s", demand_id, e)
        raise HTTPException(status_code=500, detail="Database query error.") from e
    if d:
        return {"status": "success", "demand": d}

    raise HTTPException(status_code=404, detail=f"Employer demand '{demand_id}' not found.")


@router.get("/employer/difficult-skills")
async def list_difficult_skills(
    is_demo: bool | None = Query(None, description="Explicit demo/real mode selector"),
):
    """Retrieve hard-to-hire skills telemetry, shortage indices, and intervention recommendations."""
    if is_explicit_demo_mode(is_demo):
        difficult = get_demo("difficult_skills")
        if not difficult:
            # Fallback dynamic calculation from gaps if table not loaded
            gaps = get_demo("skill_gaps")
            skills_map = {s["id"]: s["name"] for s in get_demo("skills")}
            difficult = [
                {
                    "skill_id": g.get("skill_id", "sk-001"),
                    "skill_name": skills_map.get(g.get("skill_id"), "Advanced Technology"),
                    "deficit_score": int(g.get("gap_pct", 75)),
                    "avg_days_to_fill": 45,
                    "top_districts": ["Pune", "Mumbai"],
                    "industries": ["Technology", "Manufacturing"],
                    "shortage_reason": "High industry demand outpacing current academic pass-outs.",
                    "hiring_challenge": "Candidate skills do not match modern production specifications.",
                    "suggested_intervention": "Upgrade laboratory syllabus and sponsor faculty development programs.",
                }
                for g in gaps[:6]
            ]
        return difficult

    from app.services.gap_engine import compute_gaps
    try:
        from app.repositories.supabase_repository import list_skills
        repo_skills = list_skills(limit=10000) or []
        skills_map = {s["id"]: s.get("name", s["id"]) for s in repo_skills if "id" in s}
    except Exception:
        skills_map = {}
    gaps = compute_gaps(is_demo=False)
    shortages = sorted(gaps, key=lambda g: g.get("gap_pct", 0), reverse=True)
    return [
        {
            "skill_id": g.get("skill_id"),
            "skill_name": skills_map.get(g.get("skill_id"), g.get("skill_name", "Critical Skill")),
            "deficit_score": int(g.get("gap_pct", 0)),
            "avg_days_to_fill": None,
            "top_districts": [g.get("district").capitalize()] if g.get("district") else [],
            "industries": [g.get("category")] if g.get("category") else [],
            "shortage_reason": f"Elevated industry demand ({g.get('demand_pct', 0)}%) exceeding academic coverage ({g.get('coverage_pct', 0)}%)." if g.get("demand_pct") is not None else None,
            "hiring_challenge": None,
            "suggested_intervention": None,
        }
        for g in shortages[:6] if g.get("gap_pct", 0) > 0
    ]


@router.get("/employer/summary")
async def employer_summary():
    """Get high-level employer validation KPIs, approval rates, and industry participation."""
    try:
        feedback = list_employer_feedback()
    except SupabaseRepositoryError:
        feedback = []
    try:
        demands = list_employer_demands()
    except SupabaseRepositoryError:
        demands = []
    employers = get_demo("employers")
    difficult = get_demo("difficult_skills")

    total_validations = len(feedback)
    confirmed_count = sum(1 for f in feedback if f.get("status") == "confirmed")
    pending_count = sum(1 for f in feedback if f.get("status") == "pending")
    corrected_count = sum(1 for f in feedback if f.get("status") == "corrected")
    rejected_count = sum(1 for f in feedback if f.get("status") == "rejected")

    reviewed_count = confirmed_count + corrected_count + rejected_count
    approval_rate = round((confirmed_count / max(1, reviewed_count)) * 100, 1) if reviewed_count > 0 else 0.0

    industry_counts = Counter(e.get("industry", "General") for e in employers)
    top_industries = [{"industry": k, "count": v} for k, v in industry_counts.most_common(6)]

    return {
        "total_validations": total_validations,
        "reviewed_count": reviewed_count,
        "confirmed_count": confirmed_count,
        "pending_count": pending_count,
        "corrected_count": corrected_count,
        "rejected_count": rejected_count,
        "approval_rate": approval_rate,
        "active_employers_count": len(employers),
        "active_demands_count": len(demands),
        "hard_to_hire_count": len(difficult),
        "top_industries": top_industries,
    }


class EmployerVerificationSubmitRequest(BaseModel):
    company_name: str = Field(..., min_length=2, max_length=200)
    industry: str = Field(..., min_length=2, max_length=150)
    district: str = Field(..., min_length=2, max_length=100)
    gstin: str | None = Field(default=None, max_length=15)
    corporate_website: str | None = Field(default=None, max_length=500)
    official_documents: list[str] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=1000)


def _resolve_authenticated_employer_id(current_user: dict) -> str:
    user_org = current_user.get("organization_id")
    user_id = current_user.get("id")
    return (user_org or f"emp-{user_id}").strip()


@router.get("/employer/verification")
async def get_my_verification_status(current_user: dict = Depends(require_roles(["EMPLOYER", "ADMIN"]))):
    employer_id = _resolve_authenticated_employer_id(current_user)
    emp = None
    try:
        emp = get_employer(employer_id)
    except Exception:
        pass

    if not emp:
        from app.db import _cache
        for e in _cache.get("employers", []):
            if e.get("id") == employer_id or e.get("user_id") == current_user.get("id"):
                emp = e
                break

    if not emp:
        return {
            "status": "success",
            "employer_id": employer_id,
            "verification_status": "UNVERIFIED",
            "is_verified": False,
            "company_name": current_user.get("full_name") or current_user.get("organization_id") or "Employer",
            "industry": None,
            "district": current_user.get("district"),
            "email": current_user.get("email"),
            "gstin": None,
            "corporate_website": None,
            "verification_source": None,
            "verification_method": None,
            "verified_at": None,
            "verified_by": None,
            "rejection_reason": None,
            "data_provenance": "UNVERIFIED",
            "confidence": 0,
            "evidence": {},
            "is_demo": False,
            "updated_at": None,
        }

    status_val = (emp.get("verification_status") or "UNVERIFIED").upper()
    return {
        "status": "success",
        "employer_id": emp.get("id", employer_id),
        "verification_status": status_val,
        "is_verified": (status_val == "VERIFIED"),
        "company_name": emp.get("company_name") or emp.get("name") or current_user.get("full_name"),
        "industry": emp.get("industry"),
        "district": emp.get("district") or current_user.get("district"),
        "email": emp.get("email") or current_user.get("email"),
        "gstin": emp.get("gstin"),
        "corporate_website": emp.get("corporate_website"),
        "verification_source": emp.get("verification_source"),
        "verification_method": emp.get("verification_method"),
        "verified_at": emp.get("verified_at"),
        "verified_by": emp.get("verified_by"),
        "rejection_reason": emp.get("rejection_reason"),
        "data_provenance": emp.get("data_provenance", "UNVERIFIED"),
        "confidence": emp.get("confidence", 0),
        "evidence": emp.get("evidence", {}),
        "is_demo": emp.get("is_demo", False),
        "updated_at": emp.get("updated_at"),
    }


@router.post("/employer/verification/submit")
async def submit_employer_verification(
    submission: EmployerVerificationSubmitRequest,
    current_user: dict = Depends(require_roles(["EMPLOYER", "ADMIN"])),
):
    employer_id = _resolve_authenticated_employer_id(current_user)
    existing_emp = None
    try:
        existing_emp = get_employer(employer_id)
    except Exception:
        pass

    if not existing_emp:
        from app.db import _cache
        for e in _cache.get("employers", []):
            if e.get("id") == employer_id or e.get("user_id") == current_user.get("id"):
                existing_emp = e
                break

    if existing_emp and (existing_emp.get("verification_status") or "").upper() == "VERIFIED":
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Employer is already verified. Re-verification not allowed unless status reset by Admin.",
        )

    clean_gstin = None
    if submission.gstin and submission.gstin.strip():
        gstin_res = validate_gstin(submission.gstin.strip())
        if not gstin_res.get("valid"):
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid GSTIN format: {gstin_res.get('reason')}",
            )
        clean_gstin = gstin_res.get("gstin")

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    company_clean = submission.company_name.strip()
    evidence_payload = {
        "company_name": company_clean,
        "industry": submission.industry.strip(),
        "district": submission.district.strip(),
        "gstin": clean_gstin,
        "corporate_website": submission.corporate_website.strip() if submission.corporate_website else None,
        "official_documents": submission.official_documents,
        "notes": submission.notes.strip() if submission.notes else None,
        "submitted_by_user_id": current_user.get("id"),
        "submitted_by_email": current_user.get("email"),
        "self_declared_at": now_iso,
    }

    emp_record = {
        "id": employer_id,
        "user_id": current_user.get("id"),
        "name": company_clean,
        "company_name": company_clean,
        "industry": submission.industry.strip(),
        "district": submission.district.strip(),
        "email": current_user.get("email"),
        "gstin": clean_gstin,
        "corporate_website": submission.corporate_website.strip() if submission.corporate_website else None,
        "verification_status": "PENDING",
        "verification_source": "EMPLOYER_SUBMISSION",
        "verification_method": "SELF_DECLARATION_PENDING_REVIEW",
        "verified_at": None,
        "verified_by": None,
        "rejection_reason": None,
        "evidence": evidence_payload,
        "data_provenance": "EMPLOYER_SELF_DECLARED",
        "source": "USER_SUBMITTED",
        "source_label": "Employer Self-Declaration",
        "confidence": 25,
        "is_demo": False,
        "created_at": existing_emp.get("created_at", now_iso) if existing_emp else now_iso,
        "updated_at": now_iso,
    }

    try:
        saved_emp = save_employer_record(emp_record)
    except Exception as e:
        logger.exception("[Employer] Failed saving employer verification submission: %s", e)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database persistence failed for employer verification.",
        ) from e

    v_record = {
        "id": f"ev-{uuid.uuid4().hex[:12]}",
        "employer_id": employer_id,
        "user_id": current_user.get("id"),
        "company_name": company_clean,
        "email": current_user.get("email"),
        "gstin": clean_gstin,
        "corporate_website": submission.corporate_website.strip() if submission.corporate_website else None,
        "official_documents": submission.official_documents,
        "notes": submission.notes.strip() if submission.notes else None,
        "status": "PENDING",
        "action": "SUBMIT",
        "submitted_at": now_iso,
        "reviewed_at": None,
        "reviewed_by": None,
        "admin_notes": None,
        "rejection_reason": None,
        "data_provenance": "EMPLOYER_SELF_DECLARED",
        "source": "USER_SUBMITTED",
        "is_demo": False,
        "evidence_payload": evidence_payload,
        "confidence": 25,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    try:
        create_employer_verification(v_record)
    except Exception as e:
        if existing_emp:
            try:
                save_employer_record(existing_emp)
            except Exception:
                pass
        logger.exception("[Employer] Failed inserting employer_verifications row: %s", e)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database persistence failed for employer verification evidence.",
        ) from e

    return {
        "status": "submitted",
        "message": "Verification evidence submitted for administrative review.",
        "employer_id": employer_id,
        "verification_status": "PENDING",
        "is_verified": False,
        "data_provenance": "EMPLOYER_SELF_DECLARED",
        "employer": saved_emp,
    }


@router.get("/employer/verification/{employer_id}")
async def get_employer_verification_by_id(
    employer_id: str,
    current_user: dict = Depends(get_current_user),
):
    user_role = (current_user.get("role") or "").upper()
    if user_role == "STUDENT":
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Students do not have permission to access employer verification records.",
        )

    if user_role == "EMPLOYER":
        my_emp_id = _resolve_authenticated_employer_id(current_user)
        if my_emp_id.lower() != employer_id.strip().lower():
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You do not have permission to access another employer's verification record.",
            )
    elif user_role != "ADMIN":
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Insufficient role permissions.",
        )

    emp = None
    try:
        emp = get_employer(employer_id.strip())
    except Exception:
        pass

    if not emp:
        from app.db import _cache
        for e in _cache.get("employers", []):
            if e.get("id") == employer_id.strip():
                emp = e
                break

    if not emp:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Employer '{employer_id}' not found.",
        )

    status_val = (emp.get("verification_status") or "UNVERIFIED").upper()
    return {
        "status": "success",
        "employer_id": emp.get("id", employer_id),
        "verification_status": status_val,
        "is_verified": (status_val == "VERIFIED"),
        "company_name": emp.get("company_name") or emp.get("name"),
        "industry": emp.get("industry"),
        "district": emp.get("district"),
        "email": emp.get("email"),
        "gstin": emp.get("gstin"),
        "corporate_website": emp.get("corporate_website"),
        "verification_source": emp.get("verification_source"),
        "verification_method": emp.get("verification_method"),
        "verified_at": emp.get("verified_at"),
        "verified_by": emp.get("verified_by"),
        "rejection_reason": emp.get("rejection_reason"),
        "data_provenance": emp.get("data_provenance", "UNVERIFIED"),
        "confidence": emp.get("confidence", 0),
        "evidence": emp.get("evidence", {}),
        "is_demo": emp.get("is_demo", False),
        "updated_at": emp.get("updated_at"),
    }


