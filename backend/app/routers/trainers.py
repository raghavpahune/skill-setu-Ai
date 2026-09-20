from datetime import datetime, timezone
import logging
from typing import Any, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.security import get_current_user, require_roles
from app.db import (
    get_faculty_nomination_by_id,
    get_institution_trainer_by_id,
    save_faculty_nomination_record,
    save_institution_trainer_record,
    update_faculty_nomination_record,
    update_institution_trainer_record,
)
from app.repositories.supabase_repository import (
    get_faculty_nomination,
    get_institution_trainer,
    list_faculty_nominations,
    list_institution_trainers,
)
from app.services.curriculum_engine import TRAINER_UPGRADE_CATALOG
from app.services.trainer_service import (
    compute_institute_faculty_scorecard,
    compute_statewide_trainer_analytics,
)

logger = logging.getLogger("skillsetu.trainers")
router = APIRouter()


class TrainerCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    employee_id: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=150)
    phone: Optional[str] = Field(None, max_length=30)
    institute_id: Optional[str] = Field(None, max_length=100)
    institute_name: Optional[str] = Field(None, max_length=150)
    district: Optional[str] = Field(None, max_length=100)
    primary_trade: str = Field(..., min_length=2, max_length=100)
    skills: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    experience_years: float = Field(default=0.0, ge=0.0)
    industry_experience_years: float = Field(default=0.0, ge=0.0)
    highest_qualification: Optional[str] = Field(None, max_length=150)
    assigned_course_ids: list[str] = Field(default_factory=list)
    status: Optional[str] = Field(default="ACTIVE", pattern="^(ACTIVE|IN_TRAINING|ON_LEAVE|TRANSFERRED|RETIRED)$")


class TrainerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    employee_id: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=150)
    phone: Optional[str] = Field(None, max_length=30)
    primary_trade: Optional[str] = Field(None, min_length=2, max_length=100)
    skills: Optional[list[str]] = None
    certifications: Optional[list[str]] = None
    experience_years: Optional[float] = Field(None, ge=0.0)
    industry_experience_years: Optional[float] = Field(None, ge=0.0)
    highest_qualification: Optional[str] = Field(None, max_length=150)
    assigned_course_ids: Optional[list[str]] = None
    status: Optional[str] = Field(None, pattern="^(ACTIVE|IN_TRAINING|ON_LEAVE|TRANSFERRED|RETIRED)$")


class FacultyNominationCreate(BaseModel):
    trainer_id: str = Field(..., min_length=1, max_length=100)
    course_id: Optional[str] = Field(None, max_length=100)
    program_code: str = Field(..., min_length=1, max_length=100)
    program_title: str = Field(..., min_length=2, max_length=200)
    domain: str = Field(..., min_length=2, max_length=100)
    partner_agency: str = Field(..., min_length=2, max_length=150)
    duration_weeks: int = Field(default=2, ge=1, le=52)
    budget_inr: int = Field(default=25000, ge=0)
    rationale: Optional[str] = None


class FacultyNominationUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern="^(NOMINATED|SUBMITTED|SANCTIONED|REJECTED|IN_PROGRESS|COMPLETED|FAILED)$")
    sanction_reference: Optional[str] = Field(None, max_length=100)
    sanction_amount_inr: Optional[int] = Field(None, ge=0)
    completion_date: Optional[str] = None
    certification_earned: Optional[str] = Field(None, max_length=200)
    feedback: Optional[str] = None


def _resolve_user_institute_id(user: dict[str, Any]) -> str:
    org_id = user.get("organization_id") or user.get("institute_id")
    if org_id:
        return str(org_id)
    uid = user.get("id") or "inst-anon"
    return f"inst-{uid}"


@router.get("/trainers/catalog/programs")
async def get_trainer_upgrade_catalog_endpoint(
    current_user: dict = Depends(get_current_user),
):
    return {"catalog": TRAINER_UPGRADE_CATALOG, "total": len(TRAINER_UPGRADE_CATALOG)}


@router.get("/trainers/analytics/statewide")
async def get_statewide_trainer_analytics_endpoint(
    is_demo: Optional[bool] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    demo_flag = is_demo if is_demo is not None else current_user.get("is_demo")
    analytics = compute_statewide_trainer_analytics(is_demo=demo_flag)
    return analytics


@router.get("/trainers/institutes/{institute_id}/scorecard")
async def get_institute_faculty_scorecard_endpoint(
    institute_id: str,
    is_demo: Optional[bool] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    user_role = (current_user.get("role") or "").upper()
    user_inst_id = _resolve_user_institute_id(current_user)

    if user_role == "INSTITUTE" and user_inst_id.lower() != institute_id.lower():
        known_aliases = {
            "inst-coep": ["coep technological university", "coep"],
            "inst-vjti": ["vjti mumbai", "vjti"],
            "inst-gp-pune": ["government polytechnic pune", "gp pune"],
            "inst-gp-nagpur": ["government polytechnic nagpur", "gp nagpur"],
        }
        allowed_aliases = known_aliases.get(user_inst_id.lower(), [])
        if institute_id.lower() not in [a.lower() for a in allowed_aliases]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You can only access faculty capacity analytics for your own institution.",
            )

    demo_flag = is_demo if is_demo is not None else current_user.get("is_demo")
    scorecard = compute_institute_faculty_scorecard(institute_id=institute_id, is_demo=demo_flag)
    return scorecard


@router.get("/trainers")
async def list_trainers_endpoint(
    institute_id: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    trade: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    is_demo: Optional[bool] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    user_role = (current_user.get("role") or "").upper()
    user_inst_id = _resolve_user_institute_id(current_user)

    target_institute_id = institute_id
    if user_role == "INSTITUTE":
        target_institute_id = user_inst_id

    demo_flag = is_demo if is_demo is not None else current_user.get("is_demo")

    records = list_institution_trainers(
        institute_id=target_institute_id,
        district=district,
        trade=trade,
        is_demo=demo_flag,
        limit=limit,
        offset=offset,
    )
    if status_filter:
        records = [r for r in records if (r.get("status") or "").upper() == status_filter.strip().upper()]

    return {
        "trainers": records,
        "count": len(records),
        "limit": limit,
        "offset": offset,
    }


@router.post("/trainers", status_code=status.HTTP_201_CREATED)
async def create_trainer_endpoint(
    data: TrainerCreate,
    current_user: dict = Depends(require_roles(["INSTITUTE", "ADMIN"])),
):
    user_role = (current_user.get("role") or "").upper()
    user_inst_id = _resolve_user_institute_id(current_user)

    if user_role == "INSTITUTE":
        assigned_inst_id = user_inst_id
        assigned_inst_name = current_user.get("institute_name") or current_user.get("organization_id") or "Technical Institute"
    else:
        assigned_inst_id = data.institute_id or user_inst_id
        assigned_inst_name = data.institute_name or "Technical Institute"

    now_iso = datetime.now(timezone.utc).isoformat()
    trainer_id = f"tr-{uuid.uuid4().hex[:10]}"
    demo_flag = bool(current_user.get("is_demo"))

    record_data = {
        "id": trainer_id,
        "name": data.name.strip(),
        "employee_id": data.employee_id,
        "email": data.email,
        "phone": data.phone,
        "institute_id": assigned_inst_id,
        "institute_name": assigned_inst_name,
        "district": data.district or current_user.get("district") or "Maharashtra",
        "primary_trade": data.primary_trade.strip(),
        "skills": data.skills,
        "certifications": data.certifications,
        "experience_years": data.experience_years,
        "industry_experience_years": data.industry_experience_years,
        "highest_qualification": data.highest_qualification,
        "assigned_course_ids": data.assigned_course_ids,
        "status": (data.status or "ACTIVE").upper(),
        "data_provenance": "INSTITUTE_AUTHORITATIVE",
        "is_demo": demo_flag,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    saved = save_institution_trainer_record(record_data)
    return saved


@router.get("/trainers/{trainer_id}")
async def get_trainer_detail_endpoint(
    trainer_id: str,
    current_user: dict = Depends(get_current_user),
):
    trainer = get_institution_trainer(trainer_id) or get_institution_trainer_by_id(trainer_id)
    if not trainer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Trainer '{trainer_id}' not found")

    user_role = (current_user.get("role") or "").upper()
    user_inst_id = _resolve_user_institute_id(current_user)

    if user_role == "INSTITUTE":
        t_inst_id = str(trainer.get("institute_id") or "").lower()
        if t_inst_id and t_inst_id != user_inst_id.lower():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: You cannot access another institute's faculty record.")

    return trainer


@router.patch("/trainers/{trainer_id}")
async def update_trainer_endpoint(
    trainer_id: str,
    data: TrainerUpdate,
    current_user: dict = Depends(require_roles(["INSTITUTE", "ADMIN"])),
):
    trainer = get_institution_trainer(trainer_id) or get_institution_trainer_by_id(trainer_id)
    if not trainer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Trainer '{trainer_id}' not found")

    user_role = (current_user.get("role") or "").upper()
    user_inst_id = _resolve_user_institute_id(current_user)

    if user_role == "INSTITUTE":
        t_inst_id = str(trainer.get("institute_id") or "").lower()
        if t_inst_id and t_inst_id != user_inst_id.lower():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: You cannot modify another institute's faculty record.")

    updates = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        return trainer

    updated = update_institution_trainer_record(trainer_id, updates)
    return updated


@router.get("/trainers/nominations/list")
@router.get("/trainers/nominations")
async def list_faculty_nominations_endpoint(
    institute_id: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    is_demo: Optional[bool] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    user_role = (current_user.get("role") or "").upper()
    user_inst_id = _resolve_user_institute_id(current_user)

    target_institute_id = institute_id
    if user_role == "INSTITUTE":
        target_institute_id = user_inst_id

    demo_flag = is_demo if is_demo is not None else current_user.get("is_demo")

    records = list_faculty_nominations(
        institute_id=target_institute_id,
        district=district,
        status=status_filter,
        is_demo=demo_flag,
        limit=limit,
        offset=offset,
    )

    return {
        "nominations": records,
        "count": len(records),
        "limit": limit,
        "offset": offset,
    }


@router.post("/trainers/nominations", status_code=status.HTTP_201_CREATED)
async def create_faculty_nomination_endpoint(
    data: FacultyNominationCreate,
    current_user: dict = Depends(require_roles(["INSTITUTE", "ADMIN"])),
):
    trainer = get_institution_trainer(data.trainer_id) or get_institution_trainer_by_id(data.trainer_id)
    if not trainer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Trainer '{data.trainer_id}' not found")

    user_role = (current_user.get("role") or "").upper()
    user_inst_id = _resolve_user_institute_id(current_user)

    if user_role == "INSTITUTE":
        t_inst_id = str(trainer.get("institute_id") or "").lower()
        if t_inst_id and t_inst_id != user_inst_id.lower():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: You cannot nominate faculty from another institute.")

    nom_id = f"nom-{uuid.uuid4().hex[:10]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    demo_flag = bool(trainer.get("is_demo") or current_user.get("is_demo"))

    record_data = {
        "id": nom_id,
        "trainer_id": trainer["id"],
        "trainer_name": trainer["name"],
        "institute_id": trainer["institute_id"],
        "institute_name": trainer["institute_name"],
        "course_id": data.course_id,
        "program_code": data.program_code.strip(),
        "program_title": data.program_title.strip(),
        "domain": data.domain.strip(),
        "partner_agency": data.partner_agency.strip(),
        "duration_weeks": data.duration_weeks,
        "budget_inr": data.budget_inr,
        "status": "NOMINATED",
        "nominated_at": now_iso,
        "rationale": data.rationale,
        "data_provenance": "INSTITUTE_AUTHORITATIVE",
        "is_demo": demo_flag,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    saved = save_faculty_nomination_record(record_data)
    return saved


@router.get("/trainers/nominations/{nomination_id}")
async def get_faculty_nomination_detail_endpoint(
    nomination_id: str,
    current_user: dict = Depends(get_current_user),
):
    nomination = get_faculty_nomination(nomination_id) or get_faculty_nomination_by_id(nomination_id)
    if not nomination:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Nomination '{nomination_id}' not found")

    user_role = (current_user.get("role") or "").upper()
    user_inst_id = _resolve_user_institute_id(current_user)

    if user_role == "INSTITUTE":
        n_inst_id = str(nomination.get("institute_id") or "").lower()
        if n_inst_id and n_inst_id != user_inst_id.lower():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: You cannot access another institute's nomination record.")

    return nomination


@router.patch("/trainers/nominations/{nomination_id}")
async def update_faculty_nomination_endpoint(
    nomination_id: str,
    data: FacultyNominationUpdate,
    current_user: dict = Depends(require_roles(["GOVERNMENT", "ADMIN", "INSTITUTE"])),
):
    nomination = get_faculty_nomination(nomination_id) or get_faculty_nomination_by_id(nomination_id)
    if not nomination:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Nomination '{nomination_id}' not found")

    user_role = (current_user.get("role") or "").upper()
    user_inst_id = _resolve_user_institute_id(current_user)

    updates = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        return nomination

    new_status = (updates.get("status") or "").upper()

    if user_role == "INSTITUTE":
        n_inst_id = str(nomination.get("institute_id") or "").lower()
        if n_inst_id and n_inst_id != user_inst_id.lower():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: You cannot modify another institute's nomination record.")

        if new_status in ("SANCTIONED", "REJECTED"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: Only Government administrators can sanction or reject FDP nominations.")

        allowed_keys = {"completion_date", "certification_earned", "feedback", "status"}
        for k in list(updates.keys()):
            if k not in allowed_keys:
                del updates[k]
        if new_status and new_status not in ("IN_PROGRESS", "COMPLETED", "FAILED"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid status transition for institute: {new_status}")

    elif user_role in ("GOVERNMENT", "ADMIN"):
        if new_status == "SANCTIONED":
            updates.setdefault("sanctioned_at", datetime.now(timezone.utc).isoformat())
            updates.setdefault("approved_by", current_user.get("id") or current_user.get("email") or "GOVERNMENT_AUTHORITY")
            updates.setdefault("data_provenance", "STATE_SANCTIONED_FDP")
            if not updates.get("sanction_amount_inr"):
                updates["sanction_amount_inr"] = nomination.get("budget_inr", 25000)
            if not updates.get("sanction_reference"):
                updates["sanction_reference"] = f"MSDE/Maha-FDP/2026/{uuid.uuid4().hex[:6].upper()}"

    updated = update_faculty_nomination_record(nomination_id, updates)

    if updated.get("status") == "COMPLETED" and updated.get("certification_earned"):
        trainer_id = updated.get("trainer_id")
        cert_name = updated.get("certification_earned")
        if trainer_id and cert_name:
            trainer = get_institution_trainer(trainer_id) or get_institution_trainer_by_id(trainer_id)
            if trainer:
                curr_certs = list(trainer.get("certifications") or [])
                if cert_name not in curr_certs:
                    curr_certs.append(cert_name)
                    update_institution_trainer_record(trainer_id, {"certifications": curr_certs})

    return updated
