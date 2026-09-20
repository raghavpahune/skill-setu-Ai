from datetime import datetime, timezone
import logging
from typing import Any, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.data_mode import is_explicit_demo_mode
from app.core.security import get_current_user, get_optional_current_user, require_roles
from app.db import (
    _cache,
    init_db,
    get_institution_audit_notice_by_id,
    save_institution_audit_notice_record,
    update_institution_audit_notice_record,
)
from app.repositories.supabase_repository import (
    list_courses,
    list_institution_accreditations,
    list_institution_audit_notices,
)
from app.services.accreditation_service import (
    compute_institute_scorecard,
    evaluate_and_persist_institute_accreditation,
    compute_district_roi_analytics,
)

logger = logging.getLogger("skillsetu.accreditation")
router = APIRouter()


class AuditNoticeCreate(BaseModel):
    notice_type: str = Field(..., pattern="^(PERFORMANCE_WARNING|CURRICULUM_DEFICIT|COMPLIANCE_REVIEW|EXCELLENCE_COMMENDATION)$")
    severity: str = Field(default="HIGH", pattern="^(CRITICAL|HIGH|MEDIUM|INFO)$")
    title: str = Field(..., min_length=3, max_length=250)
    description: str = Field(..., min_length=5, max_length=2000)
    mandated_action: Optional[str] = Field(None, max_length=2000)
    deadline_date: Optional[str] = None


class AuditNoticeUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern="^(ISSUED|IN_REMEDIATION|RESOLVED|ESCALATED)$")
    mandated_action: Optional[str] = Field(None, max_length=2000)
    deadline_date: Optional[str] = None
    remediation_notes: Optional[str] = Field(None, max_length=2000)


@router.get("/accreditation/institutes")
async def list_accredited_institutes(
    district: Optional[str] = Query(None),
    tier: Optional[str] = Query(None),
    is_demo: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    if not _cache:
        init_db()

    is_demo_mode = is_explicit_demo_mode(is_demo)

    if is_demo_mode:
        cached_acc = _cache.get("institution_accreditations", [])
        accreditations = [
            a for a in cached_acc
            if (not district or district.lower() in (a.get("district") or "").lower())
            and (not tier or (a.get("accreditation_tier") or "").upper() == tier.upper())
        ]
    else:
        try:
            accreditations = list_institution_accreditations(
                district=district,
                tier=tier,
                is_demo=is_demo,
                limit=None,
                offset=0,
            ) or []
        except Exception as e:
            logger.warning("[AccreditationRouter] Repo query fallback: %s", e)
            accreditations = [
                a for a in _cache.get("institution_accreditations", [])
                if (is_demo is None or a.get("is_demo") == is_demo)
                and (not district or district.lower() in (a.get("district") or "").lower())
                and (not tier or (a.get("accreditation_tier") or "").upper() == tier.upper())
            ]

    known_ids = {a.get("institute_id") for a in accreditations if a.get("institute_id")}

    if is_demo_mode:
        courses = _cache.get("courses", [])
    else:
        try:
            courses = list_courses(is_demo=is_demo) or []
        except Exception:
            courses = [c for c in _cache.get("courses", []) if is_demo is None or c.get("is_demo") == is_demo]

    seen_insts: dict[str, dict[str, str]] = {}
    for c in courses:
        inst_id = c.get("institute_id") or f"inst-{c.get('institute', 'unknown').strip().lower().replace(' ', '-')}"
        if inst_id not in known_ids and inst_id not in seen_insts:
            seen_insts[inst_id] = {
                "id": inst_id,
                "name": c.get("institute") or c.get("institute_name") or inst_id,
                "district": c.get("district") or "Maharashtra",
            }

    computed_fallbacks = []
    for inst_id, meta in seen_insts.items():
        if district and district.lower() not in meta["district"].lower():
            continue
        scorecard = compute_institute_scorecard(
            institute_id=inst_id,
            institute_name=meta["name"],
            district=meta["district"],
            is_demo=is_demo,
        )
        if tier and scorecard["accreditation_tier"] != tier.upper():
            continue
        computed_fallbacks.append({
            "id": f"acc-{uuid.uuid4().hex[:8]}",
            "institute_id": scorecard["institute_id"],
            "institute_name": scorecard["institute_name"],
            "district": scorecard["district"],
            "composite_score": scorecard["composite_score"],
            "accreditation_tier": scorecard["accreditation_tier"],
            "placement_score": scorecard["dimension_breakdown"]["placement_employment_rate"]["score"],
            "curriculum_score": scorecard["dimension_breakdown"]["curriculum_modernity"]["score"],
            "employer_satisfaction_score": scorecard["dimension_breakdown"]["employer_readiness_feedback"]["score"],
            "wage_premium_score": scorecard["dimension_breakdown"]["wage_premium"]["score"],
            "evidence_confidence": scorecard["evidence_confidence"],
            "total_candidates_evaluated": scorecard["dimension_breakdown"]["placement_employment_rate"]["total_candidates_tracked"],
            "placed_candidates": scorecard["dimension_breakdown"]["placement_employment_rate"]["placed_candidates"],
            "average_salary_inr": scorecard["dimension_breakdown"]["wage_premium"]["average_salary_inr"],
            "roi_multiplier": scorecard["roi_metrics"]["roi_multiplier"],
            "is_demo": bool(is_demo),
            "data_provenance": "STATE_DETERMINISTIC_ACCREDITATION",
        })

    all_results = accreditations + computed_fallbacks

    if search and search.strip():
        q = search.strip().lower()
        all_results = [
            r for r in all_results
            if q in (r.get("institute_name") or "").lower()
            or q in (r.get("district") or "").lower()
            or q in (r.get("accreditation_tier") or "").lower()
        ]

    all_results.sort(key=lambda x: x.get("composite_score", 0), reverse=True)
    paginated = all_results[offset : offset + limit]

    tier_counts = {
        "TIER_1_EXCELLENCE": sum(1 for r in all_results if r.get("accreditation_tier") == "TIER_1_EXCELLENCE"),
        "TIER_2_ACCREDITED": sum(1 for r in all_results if r.get("accreditation_tier") == "TIER_2_ACCREDITED"),
        "TIER_3_PROVISIONAL": sum(1 for r in all_results if r.get("accreditation_tier") == "TIER_3_PROVISIONAL"),
        "TIER_4_PERFORMANCE_WATCH": sum(1 for r in all_results if r.get("accreditation_tier") == "TIER_4_PERFORMANCE_WATCH"),
    }

    return {
        "status": "success",
        "total_count": len(all_results),
        "limit": limit,
        "offset": offset,
        "tier_distribution": tier_counts,
        "accreditations": paginated,
    }


@router.get("/accreditation/institutes/{institute_id}")
async def get_institute_accreditation_scorecard(
    institute_id: str,
    is_demo: Optional[bool] = Query(None),
):
    try:
        scorecard = compute_institute_scorecard(institute_id=institute_id, is_demo=is_demo)
    except Exception as e:
        logger.error("[AccreditationRouter] Scorecard compute failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed computing institutional accreditation scorecard.",
        ) from e

    return {"status": "success", "scorecard": scorecard}


@router.post("/accreditation/institutes/{institute_id}/evaluate", status_code=status.HTTP_200_OK)
async def evaluate_institute_endpoint(
    institute_id: str,
    is_demo: Optional[bool] = Query(None),
    current_user: dict = Depends(require_roles(["GOVERNMENT", "ADMIN"])),
):
    evaluator_id = current_user.get("id")
    try:
        result = evaluate_and_persist_institute_accreditation(
            institute_id=institute_id,
            evaluator_user_id=evaluator_id,
            is_demo=is_demo,
        )
    except Exception as e:
        logger.error("[AccreditationRouter] Evaluation persistence failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed evaluating and persisting institutional accreditation.",
        ) from e

    return {"status": "success", "accreditation": result}


@router.get("/accreditation/institutes/{institute_id}/notices")
async def list_institute_audit_notices_endpoint(
    institute_id: str,
    status_filter: Optional[str] = Query(None, alias="status"),
    severity: Optional[str] = Query(None),
    is_demo: Optional[bool] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    user_role = (current_user.get("role") or "").upper()
    user_org = current_user.get("organization_id") or current_user.get("institute_id")

    if user_role == "INSTITUTE":
        if not user_org or user_org.strip().lower() != institute_id.strip().lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You do not have authorization to view audit notices for another institution.",
            )
    elif user_role not in ("GOVERNMENT", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Unauthorized to inspect state audit directives.",
        )

    is_demo_mode = is_explicit_demo_mode(is_demo)

    if is_demo_mode:
        all_cached = _cache.get("institution_audit_notices", [])
        notices = [
            n for n in all_cached
            if (institute_id.lower() in ("all", "*") or n.get("institute_id", "").lower() == institute_id.lower())
            and (not status_filter or (n.get("status") or "").upper() == status_filter.upper())
            and (not severity or (n.get("severity") or "").upper() == severity.upper())
        ]
    else:
        try:
            notices = list_institution_audit_notices(
                institute_id=None if institute_id.lower() in ("all", "*") else institute_id,
                status=status_filter,
                severity=severity,
                is_demo=is_demo,
                limit=500,
            ) or []
        except Exception as e:
            logger.warning("[AccreditationRouter] Notice list fallback: %s", e)
            all_cached = _cache.get("institution_audit_notices", [])
            notices = [
                n for n in all_cached
                if (institute_id.lower() in ("all", "*") or n.get("institute_id", "").lower() == institute_id.lower())
                and (is_demo is None or n.get("is_demo") == is_demo)
                and (not status_filter or (n.get("status") or "").upper() == status_filter.upper())
                and (not severity or (n.get("severity") or "").upper() == severity.upper())
            ]

    return {
        "status": "success",
        "institute_id": institute_id,
        "total_notices": len(notices),
        "audit_notices": notices,
    }


@router.post("/accreditation/institutes/{institute_id}/notices", status_code=status.HTTP_201_CREATED)
async def create_institute_audit_notice_endpoint(
    institute_id: str,
    data: AuditNoticeCreate,
    current_user: dict = Depends(require_roles(["GOVERNMENT", "ADMIN"])),
):
    scorecard = compute_institute_scorecard(institute_id=institute_id)
    institute_name = scorecard.get("institute_name") or institute_id
    district = scorecard.get("district") or "Maharashtra"

    now_iso = datetime.now(timezone.utc).isoformat()
    notice_id = f"not-{uuid.uuid4().hex[:12]}"
    issued_by = current_user.get("organization_id") or current_user.get("full_name") or "Directorate of Vocational Education, Maharashtra"

    notice_record = {
        "id": notice_id,
        "institute_id": institute_id,
        "institute_name": institute_name,
        "district": district,
        "notice_type": data.notice_type,
        "severity": data.severity,
        "title": data.title.strip(),
        "description": data.description.strip(),
        "mandated_action": data.mandated_action.strip() if data.mandated_action else None,
        "deadline_date": data.deadline_date,
        "status": "ISSUED",
        "issued_by": issued_by,
        "is_demo": bool(current_user.get("is_demo")),
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    try:
        saved = save_institution_audit_notice_record(notice_record)
    except Exception as e:
        logger.error("[AccreditationRouter] Failed saving audit notice: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed saving institution audit notice.",
        ) from e

    return {"status": "success", "audit_notice": saved}


@router.patch("/accreditation/notices/{notice_id}")
async def update_audit_notice_endpoint(
    notice_id: str,
    data: AuditNoticeUpdate,
    current_user: dict = Depends(get_current_user),
):
    notice = get_institution_audit_notice_by_id(notice_id)
    if not notice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Audit notice '{notice_id}' not found")

    user_role = (current_user.get("role") or "").upper()
    user_org = current_user.get("organization_id") or current_user.get("institute_id")
    target_inst = notice.get("institute_id")

    if user_role == "INSTITUTE":
        if not user_org or not target_inst or user_org.lower() != target_inst.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You cannot modify audit notices issued to another institution.",
            )
        if data.status and data.status.upper() not in ("IN_REMEDIATION", "ISSUED"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Institutions can only mark notices as IN_REMEDIATION. Formal resolution requires Government authority.",
            )
    elif user_role not in ("GOVERNMENT", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Unauthorized to update audit notice status.",
        )

    updates: dict[str, Any] = {}
    if data.status:
        updates["status"] = data.status.upper()
    if data.mandated_action is not None:
        updates["mandated_action"] = data.mandated_action.strip()
    if data.deadline_date is not None:
        updates["deadline_date"] = data.deadline_date
    if data.remediation_notes is not None:
        updates["remediation_notes"] = data.remediation_notes.strip()

    try:
        updated = update_institution_audit_notice_record(notice_id, updates)
    except Exception as e:
        logger.error("[AccreditationRouter] Failed updating notice: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed updating audit notice.",
        ) from e

    return {"status": "success", "audit_notice": updated}


@router.get("/analytics/roi/districts")
async def get_district_roi_analytics_endpoint(
    district: Optional[str] = Query(None),
    is_demo: Optional[bool] = Query(None),
):
    try:
        analytics = compute_district_roi_analytics(district_filter=district, is_demo=is_demo)
    except Exception as e:
        logger.error("[AccreditationRouter] Failed computing district ROI: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed computing district training-to-employment ROI analytics.",
        ) from e

    return {"status": "success", "roi_analytics": analytics}


@router.get("/analytics/roi/districts/{district}")
async def get_single_district_roi_endpoint(
    district: str,
    is_demo: Optional[bool] = Query(None),
):
    try:
        analytics = compute_district_roi_analytics(district_filter=district, is_demo=is_demo)
    except Exception as e:
        logger.error("[AccreditationRouter] Failed computing single district ROI: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed computing ROI analytics for district '{district}'.",
        ) from e

    matched = next((d for d in analytics.get("district_leaderboard", []) if d["district"].lower() == district.lower()), None)
    if not matched:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No training data recorded for district '{district}'")

    return {"status": "success", "district_roi": matched}


@router.get("/analytics/roi/statewide")
async def get_statewide_roi_endpoint(
    is_demo: Optional[bool] = Query(None),
    current_user: Optional[dict] = Depends(get_optional_current_user),
):
    try:
        analytics = compute_district_roi_analytics(is_demo=is_demo)
    except Exception as e:
        logger.error("[AccreditationRouter] Failed computing statewide ROI: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed computing statewide training ROI scorecard.",
        ) from e

    return {
        "status": "success",
        "statewide_summary": analytics.get("statewide_summary", {}),
        "computed_at": analytics.get("computed_at"),
    }
