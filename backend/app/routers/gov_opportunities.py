import logging
from datetime import datetime, timezone
from typing import Any
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from pydantic import BaseModel, Field, field_validator
from app.core.data_mode import is_explicit_demo_mode
from app.core.security import require_roles, get_optional_current_user, is_demo_student_id
from app.core.time import parse_iso_timestamp, UTC_MIN
from app.db import get_demo, save_gov_opportunity
from app.repositories.supabase_repository import generate_gov_opportunity_id

logger = logging.getLogger(__name__)


router = APIRouter()


class GovOpportunitySubmission(BaseModel):
    name: str = Field(..., min_length=3, max_length=250)
    department: str = Field(..., min_length=2, max_length=200)
    description: str = Field(..., min_length=5, max_length=3000)
    eligibility_criteria: str | None = Field(None, max_length=1000)
    target_skills: list[str] = Field(default_factory=list)
    district_coverage: list[str] | str = Field(default="Maharashtra")
    opportunity_type: str = Field(default="APPRENTICESHIP")
    application_url: str | None = None
    deadline: str | None = None
    status: str = Field(default="active")

    @field_validator("name", "department", "description", mode="before")
    @classmethod
    def validate_non_empty_strings(cls, v: object) -> object:
        if isinstance(v, str):
            clean = v.strip()
            if not clean:
                raise ValueError("Field cannot be empty")
            return clean
        return v

    @field_validator("application_url")
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        if not v or not v.strip():
            return "https://mahaswayam.gov.in"
        clean = v.strip()
        if not (clean.startswith("http://") or clean.startswith("https://")):
            return f"https://{clean}"
        return clean

    @field_validator("deadline")
    @classmethod
    def validate_deadline(cls, v: str | None) -> str | None:
        if not v or not isinstance(v, str) or not v.strip():
            return None
        dt = parse_iso_timestamp(v)
        if dt == UTC_MIN:
            raise ValueError("Invalid deadline format. Must be a valid ISO timestamp.")
        return v.strip()


@router.post("/gov/opportunities", status_code=http_status.HTTP_201_CREATED)
async def create_gov_opportunity(
    data: GovOpportunitySubmission,
    current_user: dict = Depends(require_roles(["GOVERNMENT", "ADMIN"])),
):
    now_iso = datetime.now(timezone.utc).isoformat()
    opp_id = generate_gov_opportunity_id(data.name, data.department)

    coverage = data.district_coverage
    if isinstance(coverage, str):
        coverage = [c.strip() for c in coverage.split(",") if c.strip()]

    record = {
        "id": opp_id,
        "name": data.name.strip(),
        "department": data.department.strip(),
        "description": data.description.strip(),
        "eligibility_criteria": data.eligibility_criteria,
        "target_skills": data.target_skills,
        "district_coverage": coverage or ["Maharashtra"],
        "opportunity_type": data.opportunity_type,
        "application_url": data.application_url or "https://mahaswayam.gov.in",
        "deadline": data.deadline,
        "status": data.status,
        "source": "USER_SUBMITTED",
        "data_provenance": "GOVERNMENT_OFFICIAL",
        "is_demo": False,
        "created_at": now_iso,
        "updated_at": now_iso,
        "user_id": current_user.get("id"),
        "user_email": current_user.get("email"),
    }

    try:
        saved = save_gov_opportunity(record)
    except Exception as e:
        logger.exception("[Gov] Failed persisting government opportunity: %s", e)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database persistence failed for government opportunity.",
        ) from e

    return {
        "status": "created",
        "message": f"Government opportunity '{saved['id']}' created successfully.",
        "opportunity": saved,
    }


def _is_expired(deadline: Any) -> bool:
    if not deadline or not isinstance(deadline, str) or not deadline.strip():
        return False
    dt = parse_iso_timestamp(deadline)
    if dt == UTC_MIN:
        return True
    return dt < datetime.now(timezone.utc)


def _is_authoritative_gov_opp(o: dict) -> bool:
    return (
        isinstance(o, dict)
        and o.get("is_demo") is False
        and o.get("source_type") not in ("SANDBOX_SIMULATION", "DEMO_SYNTHETIC")
        and o.get("source") != "DEMO_SYNTHETIC"
        and o.get("data_provenance") != "DEMO_SYNTHETIC"
        and o.get("verification_status") != "REJECTED"
        and (
            o.get("data_provenance") in ("GOVERNMENT_OFFICIAL", "VERIFIED_SNAPSHOT")
            or o.get("source") in ("DATAGOV_IN", "OGD_DATAGOV_IN", "USER_SUBMITTED", "ADMIN_CREATED")
        )
    )


def _match_student_to_opportunities(opportunities: list[dict], profile: dict) -> list[dict]:
    student_skills = set()
    for s in profile.get("skills", []) + profile.get("current_skills", []):
        if isinstance(s, dict):
            sname = s.get("skill_name") or s.get("name")
            if sname:
                student_skills.add(str(sname).lower())
            sid = s.get("skill_id")
            if sid:
                student_skills.add(str(sid).lower())
        elif s:
            student_skills.add(str(s).lower())

    student_district = (profile.get("district") or profile.get("preferred_location") or "").lower()
    student_career = (profile.get("target_role") or profile.get("desired_role") or profile.get("career_goal") or "").lower()
    student_education = (profile.get("education") or profile.get("degree") or profile.get("education_level") or "").lower()
    student_interests_list = profile.get("career_interests") or profile.get("interests") or []
    student_interests = {str(i).lower() for i in student_interests_list if i}

    scored = []
    for opp in opportunities:
        if opp.get("status", "active").lower() != "active":
            continue
        if opp.get("verification_status") == "REJECTED":
            continue
        if _is_expired(opp.get("deadline")):
            continue

        score = 0
        reasons = []

        # Skill match: opportunity target_skills vs student current skills
        opp_skills = {s.lower() for s in (opp.get("target_skills") or [])}
        matched_skills = student_skills & opp_skills
        if matched_skills:
            score += len(matched_skills) * 3
            reasons.append(f"Direct match with your skills: {', '.join(sorted(matched_skills)[:3])}")

        # District match: statewide always matches, local district gets boost
        districts = opp.get("district_coverage", [])
        if isinstance(districts, str):
            districts = [districts]
        districts_lower = [d.lower() for d in districts]

        if any("maharashtra" in d or "state-wide" in d or d.strip() == "all" or "all districts" in d for d in districts_lower):
            score += 1
            reasons.append("Statewide opportunity (open to all districts)")
        elif student_district and any(student_district in d for d in districts_lower):
            score += 3
            reasons.append(f"Available locally in {student_district.title()}")

        # Interest / Career Goal keyword match in name or description
        opp_text = f"{opp.get('name', '')} {opp.get('description', '')}".lower()
        if student_career and any(w in opp_text for w in student_career.split() if len(w) > 3):
            score += 2
            reasons.append(f"Aligns with your career goal '{profile.get('target_role') or profile.get('career_goal')}'")

        for interest in student_interests:
            if interest in opp_text:
                score += 1
                reasons.append(f"Matches your interest in '{interest.title()}'")
                break

        # Education level suitability
        eligibility = (opp.get("eligibility_criteria") or "").lower()
        if student_education and student_education in eligibility:
            score += 2
            reasons.append(f"Eligible for your education level ({student_education.title()})")

        if score > 0:
            opp_type = (opp.get("opportunity_type") or "APPRENTICESHIP").upper()
            if opp_type == "APPRENTICESHIP":
                score += 2
                reasons.append("State-prioritized apprenticeship pathway")
            elif opp_type == "VOCATIONAL_TRAINING":
                score += 1
                reasons.append("Accredited vocational training program")

        if score > 0:
            scored.append({
                **opp,
                "relevance_score": score,
                "match_reasons": reasons,
            })

    scored.sort(key=lambda x: x["relevance_score"], reverse=True)
    return scored


@router.get("/gov/opportunities")
async def list_gov_opportunities(
    district: str | None = None,
    domain: str | None = None,
    skill: str | None = None,
    opportunity_type: str | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    is_demo: bool | None = Query(None, description="Explicit demo/real mode selector"),
):
    if is_explicit_demo_mode(is_demo):
        raw_records = [r for r in get_demo("gov_opportunities") if r.get("is_demo") is not False]
    else:
        try:
            from app.repositories.supabase_repository import list_gov_opportunities as list_gov_opps_repo
            db_records = list_gov_opps_repo(
                opportunity_type=opportunity_type,
                district=district,
                status=status,
                is_demo=False,
                limit=1000,
            ) or []
            raw_records = [r for r in db_records if _is_authoritative_gov_opp(r) and not _is_expired(r.get("deadline"))]
        except Exception as e:
            logger.exception("[GovOpps] Supabase error listing opportunities: %s", e)
            raise HTTPException(
                status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Government opportunities repository is temporarily unavailable.",
            ) from e

    deduped_records = []
    seen_keys = {}
    for r in raw_records:
        key = (
            (r.get("name") or "").strip().lower(),
            (r.get("department") or "").strip().lower(),
        )
        if not key[0]:
            deduped_records.append(r)
            continue
        if key in seen_keys:
            idx = seen_keys[key]
            existing = deduped_records[idx]
            existing_desc = (existing.get("description") or "").strip()
            curr_desc = (r.get("description") or "").strip()
            existing_time = existing.get("updated_at") or existing.get("created_at") or ""
            curr_time = r.get("updated_at") or r.get("created_at") or ""
            if curr_time > existing_time or (curr_time == existing_time and len(curr_desc) > len(existing_desc)):
                deduped_records[idx] = r
        else:
            seen_keys[key] = len(deduped_records)
            deduped_records.append(r)
    records = deduped_records

    filtered = []
    for r in records:
        if status and r.get("status", "active").lower() != status.lower():
            continue

        if district and district.strip().lower() not in ("all", "all districts"):
            d_lower = district.strip().lower()
            coverage = r.get("district_coverage", "")
            if isinstance(coverage, list):
                districts = [d.strip().lower() for d in coverage]
            else:
                districts = [coverage.strip().lower()] if coverage else []
            if d_lower not in districts and not any("state-wide" in d or "maharashtra" in d or d in ("all", "all districts") or "all districts" in d for d in districts):
                continue

        if domain or skill:
            target = {s.lower() for s in (r.get("target_skills") or [])}
            if domain and domain.lower() not in target:
                continue
            if skill and skill.lower() not in target:
                continue

        if opportunity_type and r.get("opportunity_type", "").lower() != opportunity_type.lower():
            continue

        if q:
            q_lower = q.lower()
            corpus = f"{r.get('name', '')} {r.get('department', '')} {r.get('description', '')} {' '.join(r.get('target_skills', []))}".lower()
            if q_lower not in corpus:
                continue

        filtered.append(r)

    return filtered[offset: offset + limit]


@router.get("/gov/opportunities/types")
async def gov_opportunity_types(
    is_demo: bool | None = Query(None, description="Explicit demo/real mode selector"),
):
    if is_explicit_demo_mode(is_demo):
        records = [r for r in get_demo("gov_opportunities") if r.get("is_demo") is not False]
    else:
        try:
            from app.repositories.supabase_repository import list_gov_opportunities as list_gov_opps_repo
            db_records = list_gov_opps_repo(limit=1000, is_demo=False) or []
            records = [r for r in db_records if _is_authoritative_gov_opp(r)]
        except Exception as e:
            logger.exception("[GovOpps] Supabase error fetching types: %s", e)
            raise HTTPException(
                status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Government opportunities metadata is temporarily unavailable.",
            ) from e

    types = set()
    districts = set()
    skills = set()
    for r in records:
        if r.get("opportunity_type"):
            types.add(r["opportunity_type"])
        coverage = r.get("district_coverage", "")
        if isinstance(coverage, list):
            districts.update(coverage)
        elif coverage:
            districts.add(coverage)
        for s in r.get("target_skills", []):
            skills.add(s)

    return {
        "opportunity_types": sorted(types),
        "districts": sorted(districts),
        "skills": sorted(skills),
        "total": len(records),
    }


@router.get("/gov/opportunities/recommended/{student_id}")
async def recommended_gov_opportunities(
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

    profile = None
    try:
        from app.repositories.supabase_repository import get_student_profile, get_student_assessment_by_user
        from app.core.time import parse_iso_timestamp
        p = get_student_profile(resolved_id)
        a = get_student_assessment_by_user(resolved_id)
        p_time = parse_iso_timestamp((p.get("updated_at") or p.get("created_at") or "") if p else "")
        a_time = parse_iso_timestamp((a.get("updated_at") or a.get("created_at") or "") if a else "")
        if p and (p.get("skills") or not a or p_time >= a_time):
            profile = p
        elif a:
            profile = a
        else:
            profile = None
    except Exception as e:
        logger.exception("[RecommendedGovOpps] Supabase error for %s: %s", resolved_id, e)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database query failed fetching student profile for recommendations.",
        ) from e

    if not profile and is_demo_student_id(resolved_id):
        profiles = get_demo("student_profiles")
        for p in profiles:
            if p.get("user_id") == resolved_id or p.get("id") == resolved_id:
                profile = p
                break
        if not profile:
            assessments = get_demo("student_assessments")
            for a in assessments:
                if a.get("id") == resolved_id or a.get("user_id") == resolved_id:
                    profile = a
                    break

    if not profile:
        if student_id == "me" or (current_user and resolved_id == current_user.get("id")):
            return {"opportunities": [], "student_id": resolved_id, "status": "unassessed"}
        raise HTTPException(status_code=404, detail=f"Student profile '{student_id}' not found.")

    if is_demo is True:
        use_demo = True
    elif is_demo is False:
        use_demo = False
    else:
        use_demo = is_demo_student_id(resolved_id) or profile.get("is_demo") or profile.get("source") == "DEMO_SYNTHETIC"

    if use_demo:
        opportunities = get_demo("gov_opportunities")
        note = "Recommendations are based on skill/district/interest overlap with demo dataset. Verify eligibility on official portals before applying."
    else:
        try:
            from app.repositories.supabase_repository import list_gov_opportunities as list_gov_opps_repo
            db_opps = list_gov_opps_repo(status="active", is_demo=False, limit=1000) or []
        except Exception as e:
            logger.exception("[RecommendedGovOpps] Supabase error listing active opportunities: %s", e)
            raise HTTPException(
                status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Government opportunities repository is temporarily unavailable for recommendations.",
            ) from e

        valid_db_opps = [o for o in db_opps if _is_authoritative_gov_opp(o)]
        opportunities = valid_db_opps
        note = "Recommendations are based on official government opportunities and schemes. Verify eligibility on official portals before applying."

    ranked = _match_student_to_opportunities(opportunities, profile)

    return {
        "student_id": student_id,
        "total_matches": len(ranked),
        "opportunities": ranked[:limit],
        "provenance_note": note,
    }


@router.get("/gov/opportunities/{opp_id}")
async def get_gov_opportunity(
    opp_id: str,
    is_demo: bool | None = Query(None, description="Explicit demo/real mode selector"),
):
    if is_explicit_demo_mode(is_demo):
        records = get_demo("gov_opportunities")
        for r in records:
            if r.get("id") == opp_id:
                return r
    else:
        try:
            from app.repositories.supabase_repository import get_gov_opportunity as get_gov_opp_repo
            record = get_gov_opp_repo(opp_id)
            if record and _is_authoritative_gov_opp(record):
                return record
        except Exception as e:
            logger.exception("[GovOpps] Supabase error fetching %s: %s", opp_id, e)
            raise HTTPException(
                status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Government opportunities repository is temporarily unavailable.",
            ) from e

    raise HTTPException(status_code=404, detail="Government opportunity not found")
