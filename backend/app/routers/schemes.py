"""Schemes API — student welfare and government schemes."""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from app.core.data_mode import is_explicit_demo_mode, is_demo_scheme_id
from app.core.security import get_optional_current_user, is_demo_student_id
from app.db import get_demo
from app.repositories.supabase_repository import SupabaseRepositoryError

logger = logging.getLogger(__name__)

router = APIRouter()



@router.get("/schemes")
async def list_schemes(
    category: str | None = None,
    scheme_type: str | None = None,
    course_type: str | None = None,
    district: str | None = None,
    max_income: int | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    is_demo: bool | None = Query(None, description="Explicit demo/real mode selector"),
):
    """List available student welfare, scholarship, and government schemes with optional filters."""
    if is_explicit_demo_mode(is_demo):
        schemes = get_demo("schemes")
    else:
        try:
            from app.repositories.supabase_repository import list_schemes as list_schemes_repo
            schemes = list_schemes_repo(scheme_type=scheme_type, status=status, limit=1000) or []
        except SupabaseRepositoryError as e:
            logger.warning("[Schemes] Supabase unavailable: %s", e)
            raise HTTPException(
                status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Schemes repository is temporarily unavailable.",
            ) from e
        except Exception as e:
            logger.warning("[Schemes] Unexpected failure listing schemes: %s", e)
            schemes = []

    filtered = []
    for s in schemes:
        # Active status filter
        if status and s.get("status", "active").lower() != status.lower():
            continue

        # Beneficiary category filter (e.g. SC, ST, OBC, EWS, Women)
        if category:
            cat_upper = category.upper()
            cats = [c.upper() for c in s.get("beneficiary_category", [])]
            # Match if requested category is in beneficiary list, or if scheme is Open/All
            if cat_upper not in cats and "OPEN" not in cats and "ALL" not in cats:
                continue

        # Scheme type filter (e.g. scholarship, fee_waiver, hostel_allowance, stipend)
        if scheme_type and s.get("scheme_type", "").lower() != scheme_type.lower():
            continue

        # Eligible course type filter (e.g. ITI, Polytechnic, Diploma, Engineering)
        if course_type:
            ct_lower = course_type.lower()
            course_types = [c.lower() for c in s.get("eligible_course_types", [])]
            if ct_lower not in course_types:
                continue

        # District filter: if scheme specifies districts, check; otherwise it is state-wide
        if district:
            scheme_districts = s.get("districts")
            if scheme_districts and district.lower() not in [d.lower() for d in scheme_districts]:
                continue

        # Income ceiling filter (student eligible if family income <= scheme ceiling)
        if max_income is not None:
            ceiling = s.get("income_ceiling_annual")
            if ceiling is not None and ceiling < max_income:
                continue

        # Search query (title, department, benefit description)
        if q:
            q_lower = q.lower()
            text_corpus = f"{s.get('title', '')} {s.get('department', '')} {s.get('benefit_description', '')}".lower()
            if q_lower not in text_corpus:
                continue

        filtered.append(s)

    return filtered[offset : offset + limit]


@router.get("/schemes/categories")
async def get_scheme_metadata(
    is_demo: bool | None = Query(None, description="Explicit demo/real mode selector"),
):
    """Return distinct categories, scheme types, and course types for UI filtering."""
    if is_explicit_demo_mode(is_demo):
        schemes = get_demo("schemes")
    else:
        try:
            from app.repositories.supabase_repository import list_schemes as list_schemes_repo
            schemes = list_schemes_repo(limit=1000) or []
        except SupabaseRepositoryError as e:
            logger.warning("[Schemes] Supabase unavailable for metadata: %s", e)
            raise HTTPException(
                status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Schemes metadata is temporarily unavailable.",
            ) from e
        except Exception as e:
            logger.warning("[Schemes] Unexpected failure fetching metadata: %s", e)
            schemes = []
    categories = set()
    scheme_types = set()
    course_types = set()

    for s in schemes:
        for cat in s.get("beneficiary_category", []):
            categories.add(cat)
        if s.get("scheme_type"):
            scheme_types.add(s["scheme_type"])
        for ct in s.get("eligible_course_types", []):
            course_types.add(ct)

    return {
        "categories": sorted(list(categories)),
        "scheme_types": sorted(list(scheme_types)),
        "course_types": sorted(list(course_types)),
        "total_schemes": len(schemes),
    }


@router.get("/schemes/recommended/{student_id}")
async def recommended_schemes(
    student_id: str,
    limit: int = Query(10, ge=1, le=50),
    current_user: dict | None = Depends(get_optional_current_user),
):
    """Return schemes ranked by relevance to a student profile or assessment record."""
    resolved_id = student_id
    if student_id == "me" and current_user:
        resolved_id = current_user.get("id") or "me"

    from app.routers.student import _verify_student_recommendations_access
    _verify_student_recommendations_access(resolved_id, current_user)

    profile = None
    try:
        from app.repositories.supabase_repository import get_student_profile, get_student_assessment, get_student_assessment_by_user
        from app.core.time import parse_iso_timestamp
        p = get_student_profile(resolved_id)
        a = get_student_assessment(resolved_id) or get_student_assessment_by_user(resolved_id)
        p_time = parse_iso_timestamp((p.get("updated_at") or p.get("created_at") or "") if p else "")
        a_time = parse_iso_timestamp((a.get("updated_at") or a.get("created_at") or "") if a else "")
        if p and (p.get("skills") or not a or p_time >= a_time):
            profile = p
        elif a:
            profile = a
        else:
            profile = None
    except Exception as e:
        logger.exception("[RecommendedSchemes] Supabase error for %s: %s", resolved_id, e)
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
            return {"schemes": [], "student_id": resolved_id, "status": "unassessed"}
        raise HTTPException(status_code=404, detail=f"Student profile '{student_id}' not found.")

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
    student_education = (profile.get("education") or profile.get("degree") or profile.get("education_level") or "").lower()

    if is_demo_student_id(resolved_id) or profile.get("is_demo") or profile.get("source") == "DEMO_SYNTHETIC":
        schemes = get_demo("schemes")
        note = "Recommendations based on skill/education/district overlap with demo dataset. Verify eligibility on official portals before applying."
    else:
        try:
            from app.repositories.supabase_repository import list_schemes as list_schemes_repo
            db_schemes = list_schemes_repo(status="active", limit=100)
            schemes = db_schemes or []
        except SupabaseRepositoryError as e:
            logger.warning("Failed listing authoritative schemes for student '%s': %s", student_id, e)
            raise HTTPException(
                status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Schemes repository is temporarily unavailable for recommendations.",
            ) from e
        except Exception as e:
            logger.warning("Failed listing schemes for student '%s': %s", student_id, e)
            schemes = []
        note = "Recommendations based on official government schemes repository. Verify eligibility on official portals before applying."
    scored = []
    for s in schemes:
        if s.get("status", "active").lower() != "active":
            continue

        score = 0
        reasons = []

        # Skill/domain match
        scheme_skills = {sk.lower() for sk in (s.get("target_skills") or [])}
        matched = student_skills & scheme_skills
        if matched:
            score += len(matched) * 3
            reasons.append(f"Matches skills: {', '.join(sorted(matched)[:3])}")

        # Course type match against education
        if student_education:
            for ct in s.get("eligible_course_types", []):
                if ct.lower() in student_education:
                    score += 2
                    reasons.append(f"Eligible for {ct} students")
                    break

        # District availability (state-wide schemes always match)
        coverage = s.get("district_coverage", "State-wide (Maharashtra)")
        if "state-wide" in coverage.lower():
            score += 1
            reasons.append("Available state-wide")
        elif student_district and student_district in coverage.lower():
            score += 3
            reasons.append(f"Available in {student_district.title()}")

        # Open category matches all students
        cats = [c.lower() for c in s.get("beneficiary_category", [])]
        if "open" in cats:
            score += 1
            reasons.append("Open to all categories")

        if score > 0:
            scored.append({
                **s,
                "relevance_score": score,
                "match_reasons": reasons,
            })

    scored.sort(key=lambda x: x["relevance_score"], reverse=True)

    return {
        "student_id": student_id,
        "total_matches": len(scored),
        "schemes": scored[:limit],
        "provenance_note": note,
    }


@router.get("/schemes/{scheme_id}")
async def get_scheme(scheme_id: str, is_demo: bool | None = None):
    """Get single scheme details by ID or scheme code."""
    # 1. Explicit demo requested or demo ID prefix
    if is_demo is not False and (is_explicit_demo_mode(is_demo) or is_demo_scheme_id(scheme_id)):
        schemes = get_demo("schemes")
        for s in schemes:
            if s.get("id") == scheme_id or s.get("scheme_code", "").lower() == scheme_id.lower():
                return s
        raise HTTPException(status_code=404, detail="Scheme not found")

    # 2. Query authoritative repository
    try:
        from app.repositories.supabase_repository import get_scheme as get_scheme_repo
        record = get_scheme_repo(scheme_id)
        if record:
            return record
    except Exception as e:
        logger.warning("Repository error fetching scheme '%s': %s", scheme_id, e)
        if is_demo is False:
            raise HTTPException(status_code=503, detail="Authoritative scheme database unavailable")

    # 3. Fallback to demo fixtures when is_demo was not explicitly False
    if is_demo is None:
        schemes = get_demo("schemes")
        for s in schemes:
            if s.get("id") == scheme_id or s.get("scheme_code", "").lower() == scheme_id.lower():
                return s

    raise HTTPException(status_code=404, detail="Scheme not found")

