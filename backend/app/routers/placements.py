from datetime import datetime, timezone
import logging
from typing import Any, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.security import get_current_user, require_roles
from app.db import (
    get_placement_outcome_by_id,
    save_placement_outcome_record,
    update_placement_outcome_record,
    get_placement_employer_feedback_by_id,
    save_placement_employer_feedback_record,
)
from app.repositories.supabase_repository import (
    get_course,
    get_employer,
    list_placement_outcomes,
    list_placement_employer_feedback,
)
from app.services.placement_service import (
    validate_placement_lifecycle_transition,
    compute_course_placement_performance,
    compute_skill_placement_signals,
    compute_statewide_placement_analytics,
)

logger = logging.getLogger("skillsetu.placements")
router = APIRouter()


class PlacementOutcomeCreate(BaseModel):
    course_id: str = Field(..., min_length=1, max_length=100)
    candidate_id: Optional[str] = Field(None, max_length=100)
    candidate_name: str = Field(..., min_length=1, max_length=150)
    role_title: str = Field(..., min_length=1, max_length=150)
    district: Optional[str] = Field(None, max_length=100)
    industry: Optional[str] = Field(None, max_length=100)
    employer_id: Optional[str] = Field(None, max_length=100)
    employer_name: Optional[str] = Field(None, max_length=150)
    status: Optional[str] = Field(default="TRAINING_COMPLETED")
    placement_date: Optional[str] = None
    salary_annual_inr: Optional[int] = Field(None, ge=0)
    skills_utilized: Optional[list[str]] = None


class PlacementOutcomeUpdate(BaseModel):
    employer_id: Optional[str] = Field(None, max_length=100)
    employer_name: Optional[str] = Field(None, max_length=150)
    role_title: Optional[str] = Field(None, max_length=150)
    status: Optional[str] = None
    placement_date: Optional[str] = None
    salary_annual_inr: Optional[int] = Field(None, ge=0)
    skills_utilized: Optional[list[str]] = None


class PlacementEmployerFeedbackCreate(BaseModel):
    skill_adequacy_score: int = Field(..., ge=1, le=5)
    practical_readiness: str = Field(..., pattern="^(PRODUCTION_READY|NEEDS_SUPERVISION|UNPREPARED)$")
    missing_skills: list[str] = Field(default_factory=list)
    training_relevance: str = Field(default="HIGHLY_RELEVANT", pattern="^(HIGHLY_RELEVANT|PARTIALLY_RELEVANT|OUTDATED)$")
    hiring_difficulty: str = Field(default="MODERATE", pattern="^(LOW|MODERATE|EXTREME)$")
    feedback_notes: Optional[str] = None


@router.post("/placements/outcomes", status_code=status.HTTP_201_CREATED)
async def create_placement_outcome_endpoint(
    data: PlacementOutcomeCreate,
    current_user: dict = Depends(require_roles(["INSTITUTE", "ADMIN"])),
):
    course = get_course(data.course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Course '{data.course_id}' not found")

    user_role = (current_user.get("role") or "").upper()
    user_id = current_user.get("id")
    org_id = current_user.get("organization_id") or current_user.get("institute_id")
    c_user_id = course.get("user_id")
    c_inst_id = course.get("institute_id")
    c_inst_name = (course.get("institute") or course.get("institute_name") or "").strip().lower()

    known_institute_ids = {
        "coep technological university": "inst-coep",
        "vjti mumbai": "inst-vjti",
        "government polytechnic nagpur": "inst-gp-nagpur",
        "government polytechnic pune": "inst-gp-pune",
        "government polytechnic aurangabad": "inst-gp-aurangabad",
    }
    resolved_c_inst_id = c_inst_id or known_institute_ids.get(c_inst_name)

    if user_role != "ADMIN":
        is_owner = bool(
            (user_id and c_user_id == user_id)
            or (org_id and resolved_c_inst_id and resolved_c_inst_id.lower() == org_id.lower())
            or (not c_user_id and not c_inst_id and not c_inst_name)
        )
        if not is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You do not have permission to record placement outcomes for another institute's course.",
            )

    inst_id = org_id or resolved_c_inst_id or f"inst-{user_id}"
    inst_name = course.get("institute") or course.get("institute_name") or current_user.get("organization_id") or "Government Technical Institute"
    district = data.district or course.get("district") or current_user.get("district") or "Maharashtra"
    industry = data.industry or course.get("category") or "General Technical"

    init_status = (data.status or "TRAINING_COMPLETED").strip().upper()
    if not validate_placement_lifecycle_transition("TRAINING_COMPLETED", init_status):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid initial placement outcome status: '{init_status}'",
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    outcome_id = f"po-{uuid.uuid4().hex[:12]}"
    is_demo = bool(course.get("is_demo") or current_user.get("is_demo"))

    record_data = {
        "id": outcome_id,
        "course_id": course["id"],
        "course_name": course.get("name") or course.get("title", "Technical Course"),
        "institute_id": inst_id,
        "institute_name": inst_name,
        "employer_id": data.employer_id,
        "employer_name": data.employer_name,
        "candidate_id": data.candidate_id or f"cand-{uuid.uuid4().hex[:8]}",
        "candidate_name": data.candidate_name.strip(),
        "role_title": data.role_title.strip(),
        "district": district,
        "industry": industry,
        "status": init_status,
        "placement_date": data.placement_date,
        "salary_annual_inr": data.salary_annual_inr,
        "skills_utilized": data.skills_utilized or [],
        "source": "INSTITUTE_REPORTED",
        "data_provenance": "INSTITUTE_AUTHORITATIVE",
        "verification_status": "VERIFIED" if user_role == "ADMIN" else "PENDING",
        "is_demo": is_demo,
        "user_id": user_id,
        "user_email": current_user.get("email"),
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    try:
        saved = save_placement_outcome_record(record_data)
    except Exception as e:
        logger.error("[PlacementsRouter] Failed creating outcome: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed saving placement outcome to database.",
        ) from e

    return {"status": "success", "placement_outcome": saved}


@router.get("/placements/outcomes")
async def list_placement_outcomes_endpoint(
    course_id: Optional[str] = Query(None),
    institute_id: Optional[str] = Query(None),
    employer_id: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    is_demo: Optional[bool] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: Optional[dict] = Depends(get_current_user),
):
    user_role = (current_user.get("role") or "").upper() if current_user else "ANONYMOUS"
    user_inst = current_user.get("organization_id") or current_user.get("institute_id") if current_user else None
    user_emp = current_user.get("organization_id") or current_user.get("employer_id") if current_user else None

    scoped_inst = institute_id
    scoped_emp = employer_id

    if user_role == "INSTITUTE" and user_inst:
        scoped_inst = user_inst
    elif user_role == "EMPLOYER" and user_emp:
        scoped_emp = user_emp

    try:
        outcomes = list_placement_outcomes(
            course_id=course_id,
            institute_id=scoped_inst,
            employer_id=scoped_emp,
            district=district,
            status=status_filter,
            is_demo=is_demo,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        logger.error("[PlacementsRouter] Error listing outcomes: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed fetching placement outcomes.",
        ) from e

    return {
        "status": "success",
        "total_count": len(outcomes),
        "limit": limit,
        "offset": offset,
        "placement_outcomes": outcomes,
    }


@router.get("/placements/outcomes/{outcome_id}")
async def get_placement_outcome_endpoint(
    outcome_id: str,
    current_user: Optional[dict] = Depends(get_current_user),
):
    outcome = get_placement_outcome_by_id(outcome_id)
    if not outcome:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Placement outcome '{outcome_id}' not found")

    if current_user:
        user_role = (current_user.get("role") or "").upper()
        user_org = current_user.get("organization_id")
        user_id = current_user.get("id")

        if user_role == "INSTITUTE" and user_org and outcome.get("institute_id"):
            if outcome["institute_id"].lower() != user_org.lower() and outcome.get("user_id") != user_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: IDOR restriction")
        elif user_role == "EMPLOYER" and user_org and outcome.get("employer_id"):
            if outcome["employer_id"].lower() != user_org.lower():
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: IDOR restriction")
        elif user_role == "STUDENT" and user_id and outcome.get("candidate_id"):
            if outcome["candidate_id"] != user_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: IDOR restriction")

    return {"status": "success", "placement_outcome": outcome}


@router.patch("/placements/outcomes/{outcome_id}")
async def update_placement_outcome_endpoint(
    outcome_id: str,
    data: PlacementOutcomeUpdate,
    current_user: dict = Depends(require_roles(["INSTITUTE", "ADMIN"])),
):
    outcome = get_placement_outcome_by_id(outcome_id)
    if not outcome:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Placement outcome '{outcome_id}' not found")

    user_role = (current_user.get("role") or "").upper()
    user_inst = current_user.get("organization_id") or current_user.get("institute_id")
    user_id = current_user.get("id")

    if user_role != "ADMIN":
        is_owner = bool(
            (user_inst and outcome.get("institute_id") and outcome["institute_id"].lower() == user_inst.lower())
            or (user_id and outcome.get("user_id") == user_id)
        )
        if not is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You do not have permission to modify this placement outcome.",
            )

    updates: dict[str, Any] = {}
    if data.status:
        target_status = data.status.strip().upper()
        current_status = outcome.get("status", "TRAINING_COMPLETED")
        if not validate_placement_lifecycle_transition(current_status, target_status):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid lifecycle transition from '{current_status}' to '{target_status}'.",
            )
        updates["status"] = target_status

    if data.employer_id is not None:
        updates["employer_id"] = data.employer_id
    if data.employer_name is not None:
        updates["employer_name"] = data.employer_name.strip()
    if data.role_title is not None:
        updates["role_title"] = data.role_title.strip()
    if data.placement_date is not None:
        updates["placement_date"] = data.placement_date
    if data.salary_annual_inr is not None:
        updates["salary_annual_inr"] = data.salary_annual_inr
    if data.skills_utilized is not None:
        updates["skills_utilized"] = data.skills_utilized

    try:
        updated = update_placement_outcome_record(outcome_id, updates)
    except Exception as e:
        logger.error("[PlacementsRouter] Failed updating outcome '%s': %s", outcome_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed updating placement outcome.",
        ) from e

    return {"status": "success", "placement_outcome": updated}


@router.post("/placements/outcomes/{outcome_id}/feedback", status_code=status.HTTP_201_CREATED)
async def submit_placement_employer_feedback_endpoint(
    outcome_id: str,
    data: PlacementEmployerFeedbackCreate,
    current_user: dict = Depends(require_roles(["EMPLOYER", "ADMIN"])),
):
    outcome = get_placement_outcome_by_id(outcome_id)
    if not outcome:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Placement outcome '{outcome_id}' not found")

    user_role = (current_user.get("role") or "").upper()
    user_emp_id = current_user.get("organization_id") or current_user.get("employer_id")
    user_emp_name = current_user.get("company_name") or current_user.get("full_name") or "Employer Partner"

    if user_role != "ADMIN":
        if outcome.get("employer_id") and user_emp_id:
            if outcome["employer_id"].lower() != user_emp_id.lower():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: You can only provide post-hire feedback for candidates employed by your organization.",
                )

    employer_id = user_emp_id or outcome.get("employer_id") or f"emp-{current_user.get('id')}"
    employer_name = outcome.get("employer_name") or user_emp_name

    is_verified_employer = False
    data_provenance = "UNVERIFIED_EMPLOYER"
    try:
        emp_record = get_employer(employer_id)
        if emp_record and emp_record.get("verification_status") == "VERIFIED":
            is_verified_employer = True
            data_provenance = "EMPLOYER_VERIFIED"
    except Exception:
        pass

    if user_role == "ADMIN":
        is_verified_employer = True
        data_provenance = "EMPLOYER_VERIFIED"

    now_iso = datetime.now(timezone.utc).isoformat()
    feedback_id = f"pef-{uuid.uuid4().hex[:12]}"
    is_demo = bool(outcome.get("is_demo") or current_user.get("is_demo"))

    feedback_record = {
        "id": feedback_id,
        "placement_outcome_id": outcome_id,
        "employer_id": employer_id,
        "employer_name": employer_name,
        "skill_adequacy_score": data.skill_adequacy_score,
        "practical_readiness": data.practical_readiness,
        "missing_skills": [s.strip() for s in data.missing_skills if s.strip()],
        "training_relevance": data.training_relevance,
        "hiring_difficulty": data.hiring_difficulty,
        "feedback_notes": data.feedback_notes.strip() if data.feedback_notes else None,
        "is_verified_employer": is_verified_employer,
        "source": "EMPLOYER_SUBMITTED",
        "data_provenance": data_provenance,
        "is_demo": is_demo,
        "user_id": current_user.get("id"),
        "user_email": current_user.get("email"),
        "created_at": now_iso,
    }

    try:
        saved_feedback = save_placement_employer_feedback_record(feedback_record)
        update_placement_outcome_record(outcome_id, {
            "status": "FEEDBACK_RECEIVED",
            "employer_id": employer_id,
            "employer_name": employer_name,
        })
    except Exception as e:
        logger.error("[PlacementsRouter] Failed saving feedback for outcome '%s': %s", outcome_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed saving employer placement feedback.",
        ) from e

    return {"status": "success", "feedback": saved_feedback}


@router.get("/placements/course/{course_id}/performance")
async def get_course_placement_performance_endpoint(
    course_id: str,
    is_demo: Optional[bool] = Query(None),
):
    try:
        performance = compute_course_placement_performance(course_id=course_id, is_demo=is_demo)
    except Exception as e:
        logger.error("[PlacementsRouter] Failed computing course performance: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed computing course placement performance analytics.",
        ) from e

    return {"status": "success", "performance": performance}


@router.get("/placements/analytics/skills")
async def get_skill_placement_signals_endpoint(
    is_demo: Optional[bool] = Query(None),
):
    try:
        signals = compute_skill_placement_signals(is_demo=is_demo)
    except Exception as e:
        logger.error("[PlacementsRouter] Failed computing skill signals: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed computing skill placement signals.",
        ) from e

    return {"status": "success", "skill_signals": signals}


@router.get("/placements/analytics/statewide")
async def get_statewide_placement_analytics_endpoint(
    district: Optional[str] = Query(None),
    is_demo: Optional[bool] = Query(None),
    current_user: dict = Depends(require_roles(["GOVERNMENT", "ADMIN"])),
):
    try:
        analytics = compute_statewide_placement_analytics(district=district, is_demo=is_demo)
    except Exception as e:
        logger.error("[PlacementsRouter] Failed computing statewide analytics: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed computing statewide placement analytics.",
        ) from e

    return {"status": "success", "analytics": analytics}
