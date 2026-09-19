from datetime import datetime, timezone
import logging
from typing import Any, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from app.core.security import require_roles
from app.db import (
    save_curriculum_proposal_record,
    get_curriculum_proposal_by_id,
    update_curriculum_proposal_record,
)
from app.repositories.supabase_repository import (
    get_course,
    update_course_repo,
    list_curriculum_proposals,
)
from app.services.curriculum_engine import (
    audit_all_courses,
    get_course_modernization_blueprint,
)

logger = logging.getLogger("skillsetu.curriculum")
router = APIRouter()


class CurriculumProposalCreate(BaseModel):
    course_id: str = Field(..., min_length=1, max_length=100)
    title: Optional[str] = Field(None, max_length=250)
    academic_cycle: Optional[str] = None
    target_academic_cycle: Optional[str] = Field(default="2026-2027 Academic Batch", max_length=100)
    proposed_skills_to_add: Optional[list[str]] = None
    proposed_skills_to_remove: Optional[list[str]] = None
    proposed_changes_summary: Optional[str] = None
    modules_to_add: list[Any] = Field(default_factory=list)
    modules_to_prune: list[str] = Field(default_factory=list)
    equipment_requirements: list[dict[str, Any]] = Field(default_factory=list)
    total_equipment_budget_inr: int = Field(default=0, ge=0)
    trainer_upskilling: list[dict[str, Any]] = Field(default_factory=list)
    status: str = Field(default="DRAFT")


class CurriculumProposalUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=250)
    academic_cycle: Optional[str] = None
    target_academic_cycle: Optional[str] = Field(None, max_length=100)
    proposed_skills_to_add: Optional[list[str]] = None
    proposed_skills_to_remove: Optional[list[str]] = None
    proposed_changes_summary: Optional[str] = None
    modules_to_add: Optional[list[Any]] = None
    modules_to_prune: Optional[list[str]] = None
    equipment_requirements: Optional[list[dict[str, Any]]] = None
    total_equipment_budget_inr: Optional[int] = Field(None, ge=0)
    trainer_upskilling: Optional[list[dict[str, Any]]] = None


class CurriculumProposalReview(BaseModel):
    review_action: Optional[str] = None
    status: Optional[str] = None
    review_notes: Optional[str] = None


@router.get("/curriculum/audit")
async def get_curriculum_audit(
    district: Optional[str] = Query(None, description="Filter by district"),
    risk: Optional[str] = Query(None, description="Filter by obsolescence risk"),
    category: Optional[str] = Query(None, description="Filter by sector category"),
    is_demo: Optional[bool] = Query(None, description="Filter by demo/authoritative data source"),
):
    try:
        courses = audit_all_courses(is_demo=is_demo)
    except Exception as e:
        logger.error("[CurriculumAudit] Course audit failure: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to complete curriculum audit due to database or analytical service failure.",
        ) from e

    if district:
        d_clean = district.strip().lower()
        courses = [c for c in courses if d_clean in c.get("district", "").lower()]

    if risk:
        r_clean = risk.strip().upper()
        courses = [c for c in courses if c.get("obsolescence_risk") == r_clean]

    if category:
        c_clean = category.strip().lower()
        courses = [c for c in courses if c_clean in c.get("category", "").lower()]

    return {
        "status": "success",
        "total_courses_audited": len(courses),
        "courses": courses,
    }


@router.get("/curriculum/summary")
async def get_curriculum_summary(
    is_demo: Optional[bool] = Query(None, description="Filter by demo/authoritative data source"),
):
    try:
        courses = audit_all_courses(is_demo=is_demo)
    except Exception as e:
        logger.error("[CurriculumSummary] Course summary failure: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to compute curriculum summary due to database or analytical service failure.",
        ) from e
    total = len(courses)

    critical_obsolete = sum(1 for c in courses if c["obsolescence_risk"] == "CRITICAL_OBSOLETE")
    high_risk = sum(1 for c in courses if c["obsolescence_risk"] == "HIGH_RISK")
    oversupply_count = sum(1 for c in courses if "OVERSUPPLY" in c["oversupply_status"])
    avg_health = round(sum(c["health_score"] for c in courses) / max(1, total), 1)
    avg_modernity = round(sum(c["modernity_score"] for c in courses) / max(1, total), 1)
    total_equip_budget = sum(c["total_equipment_budget_inr"] for c in courses)

    return {
        "status": "success",
        "total_courses": total,
        "critical_obsolete_count": critical_obsolete,
        "high_risk_count": high_risk,
        "oversupply_count": oversupply_count,
        "avg_health_score": avg_health,
        "avg_modernity_score": avg_modernity,
        "total_equipment_budget_estimate_inr": total_equip_budget,
    }


@router.get("/curriculum/recommendations/{course_id}")
async def get_course_recommendations(
    course_id: str,
    is_demo: Optional[bool] = Query(None, description="Filter by demo/authoritative data source"),
):
    clean_course_id = course_id.strip()
    if not clean_course_id or len(clean_course_id) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid course ID format",
        )
    blueprint = get_course_modernization_blueprint(clean_course_id, is_demo=is_demo)
    if not blueprint:
        raise HTTPException(status_code=404, detail=f"Course '{clean_course_id}' not found")
    return blueprint


@router.post("/curriculum/proposals", status_code=status.HTTP_201_CREATED)
async def create_curriculum_proposal_endpoint(
    data: CurriculumProposalCreate,
    current_user: dict = Depends(require_roles(["INSTITUTE", "ADMIN"])),
):
    course = get_course(data.course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Course '{data.course_id}' not found")

    user_role = (current_user.get("role") or "").upper()
    user_id = current_user.get("id")
    org_id = current_user.get("organization_id")
    c_user_id = course.get("user_id")
    c_inst_id = course.get("institute_id")

    if user_role != "ADMIN":
        c_inst_name = (course.get("institute") or course.get("institute_name") or "").lower()
        org_slug = (org_id or "").replace("inst-", "").lower()
        is_owner = bool(
            (user_id and c_user_id == user_id)
            or (org_id and c_inst_id and c_inst_id.lower() == org_id.lower())
            or (org_slug and org_slug in c_inst_name)
            or (not c_user_id and not c_inst_id and not c_inst_name)
        )
        if not is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You do not have permission to propose modernizations for another institute's course offering.",
            )

    inst_id = org_id or c_inst_id or f"inst-{user_id}"
    inst_name = course.get("institute") or course.get("institute_name") or current_user.get("organization_id") or current_user.get("full_name") or "Government Technical Institute"
    district = course.get("district") or current_user.get("district") or "Maharashtra"

    target_status = data.status.strip().upper() if data.status else "DRAFT"
    if target_status not in ("DRAFT", "SUBMITTED"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Initial proposal status must be DRAFT or SUBMITTED")

    now_iso = datetime.now(timezone.utc).isoformat()
    proposal_id = f"prop-{uuid.uuid4().hex[:10]}"

    is_demo = bool(course.get("is_demo") or current_user.get("is_demo"))
    blueprint = get_course_modernization_blueprint(data.course_id, is_demo=is_demo)
    evidence = blueprint.get("evidence_summary", {}) if blueprint else {}

    cycle = (data.academic_cycle or data.target_academic_cycle or "2026-2027").strip()
    title = (data.title or f"Curriculum Modernization Proposal — {course.get('name', 'Course')}").strip()

    skills_add = data.proposed_skills_to_add if data.proposed_skills_to_add is not None else data.modules_to_add
    skills_prune = data.proposed_skills_to_remove if data.proposed_skills_to_remove is not None else data.modules_to_prune

    if not skills_add and blueprint:
        top_missing = blueprint.get("modernization_blueprint", {}).get("top_missing_skills", []) or blueprint.get("proposal_ready_blueprint", {}).get("modules_to_add", [])
        skills_add = [m.get("skill_name") if isinstance(m, dict) else str(m) for m in top_missing]

    if not skills_add:
        skills_add = ["Advanced Industry Systems", "Applied Analytics"]

    if not skills_prune and blueprint:
        skills_prune = blueprint.get("modernization_blueprint", {}).get("skills_to_remove", []) or blueprint.get("proposal_ready_blueprint", {}).get("modules_to_prune", [])

    equip_reqs = data.equipment_requirements if data.equipment_requirements else (blueprint.get("proposal_ready_blueprint", {}).get("equipment_requirements", []) if blueprint else [])
    budget = data.total_equipment_budget_inr if data.total_equipment_budget_inr > 0 else (blueprint.get("proposal_ready_blueprint", {}).get("total_equipment_budget_inr", 0) if blueprint else 0)
    trainers = data.trainer_upskilling if data.trainer_upskilling else (blueprint.get("proposal_ready_blueprint", {}).get("trainer_upskilling", []) if blueprint else [])
    lift = blueprint.get("modernization_blueprint", {}).get("target_placement_lift", "+25% to +35%") if blueprint else "+25% to +35%"

    proposal_record = {
        "id": proposal_id,
        "proposal_id": proposal_id,
        "course_id": course["id"],
        "course_name": course.get("name") or course.get("title", "Technical Course"),
        "institute_id": inst_id,
        "institute_name": inst_name,
        "district": district,
        "title": title,
        "status": target_status,
        "academic_cycle": cycle,
        "target_academic_cycle": cycle,
        "proposed_changes_summary": (data.proposed_changes_summary or f"Curriculum modernization for {course.get('name', 'Course')}").strip(),
        "proposed_skills_to_add": skills_add,
        "proposed_skills_to_remove": skills_prune,
        "modules_to_add": skills_add,
        "modules_to_prune": skills_prune,
        "equipment_requirements": equip_reqs,
        "total_equipment_budget_inr": budget,
        "trainer_upskilling": trainers,
        "target_placement_lift": lift,
        "supporting_evidence": evidence,
        "evidence_summary": evidence,
        "previous_curriculum_snapshot": {},
        "adopted_curriculum_snapshot": {},
        "adoption_metadata": {},
        "data_provenance": "DEMO_SYNTHETIC" if is_demo else "INSTITUTE_SUBMITTED",
        "is_demo": is_demo,
        "user_id": user_id,
        "created_by": user_id,
        "user_email": current_user.get("email"),
        "submitted_at": now_iso if target_status == "SUBMITTED" else None,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    saved = save_curriculum_proposal_record(proposal_record)
    return {"status": "success", "message": f"Curriculum proposal '{proposal_id}' created successfully.", "proposal": saved}


@router.get("/curriculum/proposals")
async def list_curriculum_proposals_endpoint(
    status_filter: Optional[str] = Query(None, alias="status"),
    district: Optional[str] = Query(None),
    course_id: Optional[str] = Query(None),
    is_demo: Optional[bool] = Query(None),
    current_user: dict = Depends(require_roles(["INSTITUTE", "GOVERNMENT", "GOVERNMENT_OFFICIAL", "ADMIN"])),
):
    user_role = (current_user.get("role") or "").upper()
    inst_id_filter = None
    if user_role == "INSTITUTE":
        inst_id_filter = current_user.get("organization_id") or f"inst-{current_user.get('id')}"

    try:
        proposals = list_curriculum_proposals(
            institute_id=inst_id_filter,
            district=district,
            status=status_filter,
            course_id=course_id,
            is_demo=is_demo,
            limit=1000,
        )
    except Exception as e:
        logger.error("[CurriculumProposals] Failed listing proposals: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to list curriculum proposals.",
        ) from e

    if user_role == "INSTITUTE" and not inst_id_filter:
        user_id = current_user.get("id")
        proposals = [p for p in proposals if p.get("user_id") == user_id]

    return {
        "status": "success",
        "total": len(proposals),
        "proposals": proposals,
    }


@router.get("/curriculum/proposals/{proposal_id}")
async def get_curriculum_proposal_endpoint(
    proposal_id: str,
    current_user: dict = Depends(require_roles(["INSTITUTE", "GOVERNMENT", "GOVERNMENT_OFFICIAL", "ADMIN"])),
):
    proposal = get_curriculum_proposal_by_id(proposal_id)
    if not proposal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Curriculum proposal '{proposal_id}' not found")

    user_role = (current_user.get("role") or "").upper()
    if user_role == "INSTITUTE":
        user_id = current_user.get("id")
        org_id = current_user.get("organization_id")
        p_inst_id = proposal.get("institute_id")
        p_user_id = proposal.get("user_id")
        is_owner = bool(
            (user_id and p_user_id == user_id)
            or (org_id and p_inst_id == org_id)
            or (p_inst_id == f"inst-{user_id}")
        )
        if not is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You do not have permission to access this proposal.",
            )

    return {"status": "success", "proposal": proposal}


@router.patch("/curriculum/proposals/{proposal_id}")
async def update_curriculum_proposal_endpoint(
    proposal_id: str,
    updates: CurriculumProposalUpdate,
    current_user: dict = Depends(require_roles(["INSTITUTE", "ADMIN"])),
):
    proposal = get_curriculum_proposal_by_id(proposal_id)
    if not proposal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Curriculum proposal '{proposal_id}' not found")

    user_role = (current_user.get("role") or "").upper()
    if user_role != "ADMIN":
        user_id = current_user.get("id")
        org_id = current_user.get("organization_id")
        p_inst_id = proposal.get("institute_id")
        p_user_id = proposal.get("user_id")
        is_owner = bool(
            (user_id and p_user_id == user_id)
            or (org_id and p_inst_id == org_id)
            or (p_inst_id == f"inst-{user_id}")
        )
        if not is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You do not have permission to modify this proposal.",
            )

    curr_status = proposal.get("status", "DRAFT").upper()
    if curr_status not in ("DRAFT", "REJECTED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot edit proposal in '{curr_status}' status. Only DRAFT or REJECTED proposals can be modified.",
        )

    patch_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    if not patch_data:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No fields provided for update")

    if "proposed_skills_to_add" in patch_data:
        patch_data["modules_to_add"] = patch_data["proposed_skills_to_add"]
    if "modules_to_add" in patch_data and "proposed_skills_to_add" not in patch_data:
        patch_data["proposed_skills_to_add"] = patch_data["modules_to_add"]

    if "proposed_skills_to_remove" in patch_data:
        patch_data["modules_to_prune"] = patch_data["proposed_skills_to_remove"]
    if "modules_to_prune" in patch_data and "proposed_skills_to_remove" not in patch_data:
        patch_data["proposed_skills_to_remove"] = patch_data["modules_to_prune"]

    if "academic_cycle" in patch_data:
        patch_data["target_academic_cycle"] = patch_data["academic_cycle"]

    patch_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    saved = update_curriculum_proposal_record(proposal_id, patch_data)
    return {"status": "success", "message": "Proposal updated successfully.", "proposal": saved}


@router.post("/curriculum/proposals/{proposal_id}/submit")
async def submit_curriculum_proposal_endpoint(
    proposal_id: str,
    current_user: dict = Depends(require_roles(["INSTITUTE", "ADMIN"])),
):
    proposal = get_curriculum_proposal_by_id(proposal_id)
    if not proposal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Curriculum proposal '{proposal_id}' not found")

    user_role = (current_user.get("role") or "").upper()
    if user_role != "ADMIN":
        user_id = current_user.get("id")
        org_id = current_user.get("organization_id")
        p_inst_id = proposal.get("institute_id")
        p_user_id = proposal.get("user_id")
        is_owner = bool(
            (user_id and p_user_id == user_id)
            or (org_id and p_inst_id == org_id)
            or (p_inst_id == f"inst-{user_id}")
        )
        if not is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You do not have permission to submit this proposal.",
            )

    curr_status = proposal.get("status", "DRAFT").upper()
    if curr_status not in ("DRAFT", "REJECTED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot submit proposal from '{curr_status}' status. Must be DRAFT or REJECTED.",
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    patch_data = {
        "status": "SUBMITTED",
        "submitted_at": now_iso,
        "updated_at": now_iso,
    }
    saved = update_curriculum_proposal_record(proposal_id, patch_data)
    return {"status": "success", "message": "Proposal submitted to State Review Board.", "proposal": saved}


@router.post("/curriculum/proposals/{proposal_id}/review")
async def review_curriculum_proposal_endpoint(
    proposal_id: str,
    review_data: CurriculumProposalReview,
    current_user: dict = Depends(require_roles(["GOVERNMENT", "GOVERNMENT_OFFICIAL", "ADMIN"])),
):
    proposal = get_curriculum_proposal_by_id(proposal_id)
    if not proposal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Curriculum proposal '{proposal_id}' not found")

    curr_status = proposal.get("status", "DRAFT").upper()
    target_status = (review_data.review_action or review_data.status or "").strip().upper()

    if target_status not in ("UNDER_STATE_REVIEW", "APPROVED", "REJECTED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid target review status '{target_status}'. Must be UNDER_STATE_REVIEW, APPROVED, or REJECTED.",
        )

    if curr_status in ("DRAFT",):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot review a DRAFT proposal. Proposal must be SUBMITTED first.",
        )

    if curr_status in ("ADOPTED",):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot review an ADOPTED proposal. Curriculum revision has already been finalized.",
        )

    if target_status == "REJECTED":
        notes = (review_data.review_notes or "").strip()
        if not notes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Review notes explaining the rejection reason are mandatory when rejecting a proposal.",
            )

    now_iso = datetime.now(timezone.utc).isoformat()
    reviewer_name = current_user.get("id") or current_user.get("full_name") or current_user.get("email") or "State Review Board"
    patch_data = {
        "status": target_status,
        "reviewed_by": reviewer_name,
        "reviewed_at": now_iso,
        "review_notes": (review_data.review_notes or "").strip(),
        "updated_at": now_iso,
    }
    saved = update_curriculum_proposal_record(proposal_id, patch_data)
    return {"status": "success", "message": f"Proposal status updated to '{target_status}'.", "proposal": saved}


@router.post("/curriculum/proposals/{proposal_id}/adopt")
async def adopt_curriculum_proposal_endpoint(
    proposal_id: str,
    current_user: dict = Depends(require_roles(["INSTITUTE", "ADMIN"])),
):
    proposal = get_curriculum_proposal_by_id(proposal_id)
    if not proposal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Curriculum proposal '{proposal_id}' not found")

    user_role = (current_user.get("role") or "").upper()
    if user_role != "ADMIN":
        user_id = current_user.get("id")
        org_id = current_user.get("organization_id")
        p_inst_id = proposal.get("institute_id")
        p_user_id = proposal.get("user_id")
        is_owner = bool(
            (user_id and p_user_id == user_id)
            or (org_id and p_inst_id == org_id)
            or (p_inst_id == f"inst-{user_id}")
        )
        if not is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You do not have permission to adopt this proposal.",
            )

    curr_status = proposal.get("status", "").upper()
    if curr_status != "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot adopt proposal in '{curr_status}' status. Only APPROVED proposals can be adopted.",
        )

    course_id = proposal.get("course_id")
    course = get_course(course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Course '{course_id}' not found")

    now_iso = datetime.now(timezone.utc).isoformat()
    old_skills = list(course.get("skills") or course.get("skills_taught") or [])
    curr_version = int(course.get("curriculum_version") or 1)

    prev_snapshot = {
        "course_id": course["id"],
        "name": course.get("name") or course.get("title"),
        "skills": old_skills,
        "curriculum_version": curr_version,
        "nsqf_level": course.get("nsqf_level", 5),
        "enrolment_capacity": course.get("enrolment_capacity", 60),
        "archived_at": now_iso,
    }

    modules_to_add = proposal.get("modules_to_add", [])
    new_skill_names = []
    for m in modules_to_add:
        if isinstance(m, dict):
            s_name = m.get("skill_name") or m.get("name") or m.get("title")
        else:
            s_name = str(m)
        if s_name and str(s_name).strip():
            new_skill_names.append(str(s_name).strip())

    prune_set = {str(m).strip().lower() for m in proposal.get("modules_to_prune", []) if str(m).strip()}

    retained_skills = [s for s in old_skills if str(s).strip().lower() not in prune_set]
    for nsk in new_skill_names:
        if not any(r.lower() == nsk.lower() for r in retained_skills):
            retained_skills.append(nsk)

    new_version = curr_version + 1

    course_updates = {
        "skills": retained_skills,
        "skills_taught": retained_skills,
        "curriculum_version": new_version,
        "last_curriculum_modernization_at": now_iso,
        "modernization_proposal_id": proposal_id,
        "status": "active",
        "updated_at": now_iso,
    }

    try:
        updated_course = update_course_repo(course["id"], course_updates)
    except Exception as e:
        logger.error("[CurriculumAdopt] Failed updating course '%s': %s", course["id"], e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed adopting curriculum updates into course registry.",
        ) from e

    adopted_snapshot = {
        "course_id": course["id"],
        "skills": retained_skills,
        "curriculum_version": new_version,
        "effective_academic_cycle": proposal.get("target_academic_cycle"),
        "adopted_at": now_iso,
    }

    proposal_updates = {
        "status": "ADOPTED",
        "adopted_at": now_iso,
        "adopted_by": current_user.get("id") or current_user.get("full_name") or current_user.get("email"),
        "previous_curriculum_snapshot": prev_snapshot,
        "adopted_curriculum_snapshot": adopted_snapshot,
        "adoption_metadata": {
            "effective_academic_cycle": proposal.get("target_academic_cycle"),
            "previous_version": curr_version,
            "adopted_version": new_version,
            "adopter_id": current_user.get("id"),
        },
        "updated_at": now_iso,
    }
    updated_proposal = update_curriculum_proposal_record(proposal_id, proposal_updates)

    return {
        "status": "success",
        "message": f"Curriculum proposal '{proposal_id}' adopted. Course '{course['id']}' upgraded to version {new_version}.",
        "proposal": updated_proposal,
        "course": updated_course,
    }

