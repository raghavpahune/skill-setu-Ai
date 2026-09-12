import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Query, HTTPException, Depends, status
from pydantic import BaseModel, Field
from app.core.data_mode import is_explicit_demo_mode
from app.core.security import get_current_user, get_optional_current_user, is_demo_student_id
from app.db import get_demo, save_student_assessment, _cache

logger = logging.getLogger("skillsetu.student")


from app.services.student_service import (
    list_alert_domains,
    get_personalized_industry_alerts,
    get_skill_explainability,
    get_diagnostic_quiz_questions,
    get_personalized_diagnostic_questions,
    evaluate_student_assessment,
)

router = APIRouter()


class SkillProficiencyInput(BaseModel):
    skill_name: str = Field(..., min_length=1, max_length=100)
    proficiency: str = Field(default="intermediate", description="beginner, intermediate, advanced")


class AssessmentSubmission(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Candidate full name")
    education: str = Field(..., min_length=2, max_length=150, description="Current course, degree, or ITI trade")
    career_goal: str = Field(..., min_length=2, max_length=100, description="Desired target career role")
    current_skills: list[SkillProficiencyInput] = Field(default_factory=list, description="Self-assessed skills")
    interests: list[str] = Field(default_factory=list, description="Domains of interest")
    quiz_answers: dict[str, str] = Field(default_factory=dict, description="Key-value mapping of question ID to chosen option key")
    district: str | None = Field(default="Maharashtra", description="District in Maharashtra")


@router.get("/student/alert-domains")
async def alert_domains():
    """Return all supported industry alert domains for student interest filtering."""
    return {"domains": list_alert_domains()}


@router.get("/student/industry-alerts")
async def student_industry_alerts(
    domain: str | None = Query(None, description="Domain key (ai_ml, cloud, ev, etc.) or 'all'"),
    student_id: str | None = Query(None, description="Optional student user ID for personalized skill strengthening suggestions"),
    current_user: dict | None = Depends(get_optional_current_user),
):
    """Retrieve personalized technology and labour-market signals for selected domain."""
    resolved_id = student_id
    if student_id == "me" and current_user:
        resolved_id = current_user.get("id")
    is_demo_id = is_demo_student_id(resolved_id)
    is_demo_fixture = False
    if not is_demo_id and resolved_id:
        demo_profiles = get_demo("student_profiles") or []
        is_demo_fixture = any((p.get("user_id") or p.get("id")) == resolved_id for p in demo_profiles)
    is_demo_req = is_demo_id or is_demo_fixture
    if resolved_id and not is_demo_req:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to view personalized industry alerts.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_id = current_user.get("id")
        user_role = (current_user.get("role") or "").upper()
        if user_id != resolved_id and user_role != "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You cannot access industry alerts for another user.",
            )
    return get_personalized_industry_alerts(domain_id=domain, student_id=resolved_id, current_user=current_user)


@router.get("/student/skill-explainability/{skill}")
async def skill_explainability(
    skill: str,
    student_id: str | None = Query(None, description="Optional student user ID for target career alignment"),
    current_user: dict | None = Depends(get_optional_current_user),
):
    """Return transparent 5-dimension evidence-based explainability breakdown for a skill."""
    resolved_id = student_id
    if student_id == "me" and current_user:
        resolved_id = current_user.get("id")
    is_demo_id = is_demo_student_id(resolved_id)
    is_demo_fixture = False
    if not is_demo_id and resolved_id:
        demo_profiles = get_demo("student_profiles") or []
        is_demo_fixture = any((p.get("user_id") or p.get("id")) == resolved_id for p in demo_profiles)
    is_demo_req = is_demo_id or is_demo_fixture
    if resolved_id and not is_demo_req:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to view personalized skill explainability.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_id = current_user.get("id")
        user_role = (current_user.get("role") or "").upper()
        if user_id != resolved_id and user_role != "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You cannot access skill explainability for another user.",
            )
    return get_skill_explainability(skill_query=skill, student_id=resolved_id)



def _is_private_user_record(record: dict) -> bool:
    if not record or not isinstance(record, dict):
        return False
    if record.get("source") in ("DEMO_SYNTHETIC", "BENCHMARK_NATIONAL") or record.get("is_demo") is True:
        return False
    if is_demo_student_id(record.get("id")) or is_demo_student_id(record.get("user_id")):
        return False
    return True


@router.get("/student/me/passport")
async def my_skill_passport(
    current_user: dict = Depends(get_current_user),
):
    """Retrieve the authenticated student's personalized Skill Passport from their real assessment."""
    user_id = current_user.get("id")
    user_email = current_user.get("email")
    try:
        from app.repositories.supabase_repository import list_skills
        repo_skills = list_skills(limit=10000) or []
        skills_map = {s["id"]: s for s in repo_skills}
        skills_name_map = {s.get("name", "").lower(): s for s in repo_skills if s.get("name")}
    except Exception:
        skills_map = {}
        skills_name_map = {}

    matched_assessment = None
    try:
        from app.repositories.supabase_repository import get_student_assessment_by_user
        matched_assessment = get_student_assessment_by_user(user_id=user_id, user_email=user_email)
    except Exception as e:
        logger.exception("[StudentPassport] Supabase error fetching assessment for %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database query failed for student user '{user_id}'.",
        ) from e

    matched_profile = None
    try:
        from app.repositories.supabase_repository import get_student_profile, get_employee_profile
        matched_profile = get_student_profile(user_id) or get_employee_profile(user_id)
    except Exception as e:
        logger.exception("[StudentPassport] Supabase error fetching profile for %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database query failed for student profile '{user_id}'.",
        ) from e

    from app.core.time import parse_iso_timestamp
    demo_skills_id_map = {s["id"]: s.get("name", "") for s in (get_demo("skills") or [])}
    prof_time = parse_iso_timestamp((matched_profile.get("updated_at") or matched_profile.get("created_at") or "") if matched_profile else "")
    asst_time = parse_iso_timestamp((matched_assessment.get("updated_at") or matched_assessment.get("created_at") or "") if matched_assessment else "")
    if matched_assessment:
        use_profile = bool(matched_profile and matched_profile.get("skills") and prof_time >= asst_time)
    else:
        use_profile = bool(matched_profile)

    if use_profile and matched_profile:
        current = []
        curr_sids = set()
        for sk in matched_profile.get("skills", []):
            sid = sk.get("skill_id")
            s_name = sk.get("skill_name") or sk.get("name") or ""
            if not sid and s_name.lower() in skills_name_map:
                sid = skills_name_map[s_name.lower()]["id"]
            if sid:
                curr_sids.add(sid)
            sk_meta = skills_map.get(sid, {}) if sid else {}
            current.append({
                **sk,
                "skill_id": sid or sk.get("skill_id") or f"sk-custom-{len(current)+1}",
                "skill_name": s_name or sk_meta.get("name", "Custom Skill"),
                "proficiency": sk.get("proficiency", "intermediate"),
                "category": sk.get("category") or sk_meta.get("category", "General"),
                "nsqf_level": sk.get("nsqf_level") or sk_meta.get("nsqf_level", 5),
            })

        from app.services.student_service import ROLE_REQUIREMENTS_MAP
        target_role = matched_profile.get("target_role") or matched_profile.get("desired_role") or "Software Engineer"
        role_key = target_role.lower().strip()
        req_sids = ROLE_REQUIREMENTS_MAP.get(role_key)
        if not req_sids:
            for r_k, sids in ROLE_REQUIREMENTS_MAP.items():
                if r_k in role_key or role_key in r_k:
                    req_sids = sids
                    break
        if not req_sids:
            req_sids = ["sk-001", "sk-002", "sk-003", "sk-004", "sk-005", "sk-006"]

        required = []
        for sid in req_sids:
            auth_sid = sid
            if auth_sid not in skills_map:
                d_name = demo_skills_id_map.get(sid, "")
                if d_name and d_name.lower() in skills_name_map:
                    auth_sid = skills_name_map[d_name.lower()]["id"]
                elif sid.lower() in skills_name_map:
                    auth_sid = skills_name_map[sid.lower()]["id"]
            sk_meta = skills_map.get(auth_sid, {})
            required.append({
                "skill_id": auth_sid,
                "skill_name": sk_meta.get("name", sid),
                "category": sk_meta.get("category", "General"),
                "nsqf_level": sk_meta.get("nsqf_level", 5),
            })
        missing = [r for r in required if r["skill_id"] not in curr_sids]
        match_pct = int((len(required) - len(missing)) / max(1, len(required)) * 100) if required else 0
        if matched_profile.get("skill_match_pct") is not None:
            match_pct = matched_profile["skill_match_pct"]

        return {
            "user_id": user_id,
            "name": matched_profile.get("full_name") or current_user.get("full_name") or matched_profile.get("name", "Student Candidate"),
            "target_role": target_role,
            "skill_match_pct": match_pct,
            "current_skills": current,
            "required_skills": required,
            "missing_skills": missing,
            "source": matched_profile.get("source", "USER_SUBMITTED"),
            "is_personalized": True,
        }

    if matched_assessment:
        target_role = matched_assessment.get("career_goal", "AI Engineer")
        from app.services.student_service import ROLE_REQUIREMENTS_MAP
        req_sids = ROLE_REQUIREMENTS_MAP.get(target_role.lower(), ["sk-001", "sk-002", "sk-003", "sk-004", "sk-005", "sk-006"])

        curr_skills = []
        curr_sids = set()
        for cs in matched_assessment.get("current_skills", []):
            s_name = cs.get("skill_name", "")
            sid = cs.get("skill_id")
            if not sid and s_name.lower() in skills_name_map:
                sid = skills_name_map[s_name.lower()]["id"]
            if sid:
                curr_sids.add(sid)
            sk_obj = skills_map.get(sid, {})
            curr_skills.append({
                "skill_id": sid or f"sk-custom-{len(curr_skills)+1}",
                "skill_name": s_name or sk_obj.get("name", "Custom Skill"),
                "proficiency": cs.get("proficiency", "intermediate"),
                "category": cs.get("category") or sk_obj.get("category", "General"),
                "nsqf_level": cs.get("nsqf_level") or sk_obj.get("nsqf_level", 5),
            })

        required = []
        for sid in req_sids:
            auth_sid = sid
            if auth_sid not in skills_map:
                d_name = demo_skills_id_map.get(sid, "")
                if d_name and d_name.lower() in skills_name_map:
                    auth_sid = skills_name_map[d_name.lower()]["id"]
                elif sid.lower() in skills_name_map:
                    auth_sid = skills_name_map[sid.lower()]["id"]
            sk_obj = skills_map.get(auth_sid, {})
            required.append({
                "skill_id": auth_sid,
                "skill_name": sk_obj.get("name", sid),
                "category": sk_obj.get("category", "General"),
                "nsqf_level": sk_obj.get("nsqf_level", 5),
            })
        missing = [r for r in required if r["skill_id"] not in curr_sids]

        return {
            "user_id": user_id,
            "name": matched_assessment.get("name") or current_user.get("full_name", "Student Candidate"),
            "target_role": target_role,
            "skill_match_pct": matched_assessment.get("skill_match_pct", 65),
            "current_skills": curr_skills,
            "required_skills": required,
            "missing_skills": missing,
            "source": "USER_SUBMITTED",
            "is_personalized": True,
        }

    return {
        "user_id": user_id,
        "name": current_user.get("full_name", "Student Candidate"),
        "has_assessment": False,
        "is_personalized": False,
        "source": "NO_SUBMISSION",
        "message": "No personal assessment completed yet. Take the 3-minute diagnostic to generate your personalized Skill Passport.",
        "target_role": None,
        "skill_match_pct": 0,
        "current_skills": [],
        "required_skills": [],
        "missing_skills": [],
    }


@router.get("/student/{student_id}/passport")
async def skill_passport(
    student_id: str,
    current_user: dict | None = Depends(get_optional_current_user),
):
    if student_id == "me" and current_user:
        return await my_skill_passport(current_user=current_user)

    demo_profiles = get_demo("student_profiles") or []
    demo_assessments = get_demo("student_assessments") or []
    is_demo_fixture = any(
        (item.get("user_id") or item.get("id")) == student_id
        for item in (demo_profiles + demo_assessments)
        if item.get("source") in ("DEMO_SYNTHETIC", "BENCHMARK_NATIONAL") or item.get("is_demo") is True or is_demo_student_id(item.get("user_id") or item.get("id"))
    )
    is_demo_req = is_demo_student_id(student_id) or is_demo_fixture

    if is_demo_req:
        profiles = demo_profiles
        skills_map = {s["id"]: s for s in get_demo("skills")}
        skills_name_map = {s["name"].lower(): s for s in get_demo("skills")}
    else:
        profiles = []
        try:
            from app.repositories.supabase_repository import list_skills
            repo_skills = list_skills(limit=10000) or []
            skills_map = {s["id"]: s for s in repo_skills}
            skills_name_map = {s.get("name", "").lower(): s for s in repo_skills if s.get("name")}
        except Exception:
            skills_map = {}
            skills_name_map = {}

    a = None
    try:
        from app.repositories.supabase_repository import get_student_assessment, get_student_assessment_by_user
        a = get_student_assessment(student_id) or get_student_assessment_by_user(student_id)
    except Exception as e:
        logger.exception("[StudentPassport] Supabase error for %s: %s", student_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database query failed for student assessment '{student_id}'.",
        ) from e

    if not a and is_demo_req:
        for item in demo_assessments:
            if item.get("id") == student_id or item.get("user_id") == student_id:
                a = item
                break

    p = None
    try:
        from app.repositories.supabase_repository import get_student_profile, get_employee_profile
        p = get_student_profile(student_id) or get_employee_profile(student_id)
    except Exception as e:
        logger.exception("[StudentPassport] Supabase error for profile %s: %s", student_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database query failed for student profile '{student_id}'.",
        ) from e

    if not p and is_demo_req:
        for item in demo_profiles:
            if item.get("user_id") == student_id or item.get("id") == student_id:
                p = item
                break

    from app.core.time import parse_iso_timestamp
    demo_skills_id_map = {s["id"]: s.get("name", "") for s in (get_demo("skills") or [])}
    p_time = parse_iso_timestamp((p.get("updated_at") or p.get("created_at") or "") if p else "")
    a_time = parse_iso_timestamp((a.get("updated_at") or a.get("created_at") or "") if a else "")
    if a:
        use_p = bool(p and p.get("skills") and p_time >= a_time)
    else:
        use_p = bool(p)

    if use_p and p:
        if _is_private_user_record(p):
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required to view candidate profile.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            user_id = current_user.get("id")
            user_role = (current_user.get("role") or "").upper()
            if (p.get("user_id") or p.get("id")) != user_id and user_role != "ADMIN":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: You cannot access another student's profile.",
                )
        current = []
        curr_sids = set()
        for sk in p.get("skills", []):
            sid = sk.get("skill_id")
            s_name = sk.get("skill_name") or sk.get("name") or ""
            if not sid and s_name.lower() in skills_name_map:
                sid = skills_name_map[s_name.lower()]["id"]
            if sid:
                curr_sids.add(sid)
            sk_meta = skills_map.get(sid, {}) if sid else {}
            current.append({
                **sk,
                "skill_id": sid or sk.get("skill_id") or f"sk-custom-{len(current)+1}",
                "skill_name": s_name or sk_meta.get("name", "Custom Skill"),
                "proficiency": sk.get("proficiency", "intermediate"),
                "category": sk.get("category") or sk_meta.get("category", "General"),
                "nsqf_level": sk.get("nsqf_level") or sk_meta.get("nsqf_level", 5),
            })

        from app.services.student_service import ROLE_REQUIREMENTS_MAP
        target_role = p.get("target_role") or p.get("desired_role") or "Software Engineer"
        role_key = target_role.lower().strip()
        req_sids = ROLE_REQUIREMENTS_MAP.get(role_key)
        if not req_sids:
            for r_k, sids in ROLE_REQUIREMENTS_MAP.items():
                if r_k in role_key or role_key in r_k:
                    req_sids = sids
                    break
        if not req_sids:
            req_sids = ["sk-001", "sk-002", "sk-003", "sk-004", "sk-005", "sk-006"]

        required = []
        for sid in req_sids:
            auth_sid = sid
            if auth_sid not in skills_map:
                d_name = demo_skills_id_map.get(sid, "")
                if d_name and d_name.lower() in skills_name_map:
                    auth_sid = skills_name_map[d_name.lower()]["id"]
                elif sid.lower() in skills_name_map:
                    auth_sid = skills_name_map[sid.lower()]["id"]
            sk_meta = skills_map.get(auth_sid, {})
            required.append({
                "skill_id": auth_sid,
                "skill_name": sk_meta.get("name", sid),
                "category": sk_meta.get("category", "General"),
                "nsqf_level": sk_meta.get("nsqf_level", 5),
            })
        missing = [r for r in required if r["skill_id"] not in curr_sids]
        match_pct = int((len(required) - len(missing)) / max(1, len(required)) * 100) if required else 0
        if p.get("skill_match_pct") is not None:
            match_pct = p["skill_match_pct"]

        return {
            "user_id": p.get("user_id") or p.get("id"),
            "name": p.get("full_name") or p.get("name", "Student Candidate"),
            "target_role": target_role,
            "skill_match_pct": match_pct,
            "current_skills": current,
            "required_skills": required,
            "missing_skills": missing,
            "source": p.get("source", "USER_SUBMITTED"),
            "is_personalized": True,
        }

    if a:
        if _is_private_user_record(a):
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required to view candidate assessment.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            user_id = current_user.get("id")
            user_email = current_user.get("email")
            user_role = (current_user.get("role") or "").upper()
            is_owner = (
                (a.get("user_id") and a.get("user_id") == user_id)
                or (a.get("id") and a.get("id") == user_id)
                or (user_email and a.get("user_email") == user_email)
            )
            if not is_owner and user_role != "ADMIN":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: You cannot access another student's personal assessment.",
                )

        target_role = a.get("career_goal", "AI Engineer")
        from app.services.student_service import ROLE_REQUIREMENTS_MAP
        role_key = target_role.lower().strip()
        req_sids = ROLE_REQUIREMENTS_MAP.get(role_key)
        if not req_sids:
            for r_k, sids in ROLE_REQUIREMENTS_MAP.items():
                if r_k in role_key or role_key in r_k:
                    req_sids = sids
                    break
        if not req_sids:
            req_sids = ["sk-001", "sk-002", "sk-003", "sk-004", "sk-005", "sk-006"]

        curr_skills = []
        curr_sids = set()
        for cs in a.get("current_skills", []):
            s_name = cs.get("skill_name", "")
            sid = cs.get("skill_id")
            if not sid and s_name.lower() in skills_name_map:
                sid = skills_name_map[s_name.lower()]["id"]
            if sid:
                curr_sids.add(sid)
            sk_obj = skills_map.get(sid, {})
            curr_skills.append({
                "skill_id": sid or f"sk-custom-{len(curr_skills)+1}",
                "skill_name": s_name or sk_obj.get("name", "Custom Skill"),
                "proficiency": cs.get("proficiency", "intermediate"),
                "category": cs.get("category") or sk_obj.get("category", "General"),
                "nsqf_level": cs.get("nsqf_level") or sk_obj.get("nsqf_level", 5),
            })

        required = []
        for sid in req_sids:
            auth_sid = sid
            if auth_sid not in skills_map:
                d_name = demo_skills_id_map.get(sid, "")
                if d_name and d_name.lower() in skills_name_map:
                    auth_sid = skills_name_map[d_name.lower()]["id"]
                elif sid.lower() in skills_name_map:
                    auth_sid = skills_name_map[sid.lower()]["id"]
            sk_meta = skills_map.get(auth_sid, {})
            required.append({
                "skill_id": auth_sid,
                "skill_name": sk_meta.get("name", sid),
                "category": sk_meta.get("category", "General"),
                "nsqf_level": sk_meta.get("nsqf_level", 5),
            })
        missing = [r for r in required if r["skill_id"] not in curr_sids]

        return {
            "user_id": a.get("user_id") or a.get("id"),
            "name": a.get("name", "Student Candidate"),
            "target_role": target_role,
            "skill_match_pct": a.get("skill_match_pct", 50),
            "current_skills": curr_skills,
            "required_skills": required,
            "missing_skills": missing,
            "source": a.get("source", "USER_SUBMITTED"),
            "is_personalized": True,
        }

    raise HTTPException(status_code=404, detail=f"Student record '{student_id}' not found.")



@router.get("/student/me/roadmap")
async def my_learning_roadmap(
    current_user: dict = Depends(get_current_user),
):
    return await learning_roadmap(student_id=current_user.get("id"), current_user=current_user)


@router.get("/student/{student_id}/roadmap")
async def learning_roadmap(
    student_id: str,
    current_user: dict | None = Depends(get_optional_current_user),
):
    if student_id == "me" and current_user:
        student_id = current_user.get("id")
    is_demo_id = is_demo_student_id(student_id)
    is_demo_fixture = False
    if not is_demo_id:
        demo_profiles = get_demo("student_profiles") or []
        is_demo_fixture = any(
            (p.get("user_id") or p.get("id")) == student_id
            for p in demo_profiles
            if p.get("source") in ("DEMO_SYNTHETIC", "BENCHMARK_NATIONAL") or p.get("is_demo") is True or is_demo_student_id(p.get("user_id") or p.get("id"))
        )
        if not is_demo_fixture:
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required to view candidate learning roadmap.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            user_id = current_user.get("id")
            user_role = (current_user.get("role") or "").upper()
            if user_id != student_id and user_role != "ADMIN":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: You do not have permission to view another student's learning roadmap.",
                )
    is_demo_req = is_demo_id or is_demo_fixture
    from app.services.roadmap_service import compute_adaptive_roadmap
    from app.repositories.supabase_repository import SupabaseRepositoryError
    try:
        return compute_adaptive_roadmap(student_id=student_id, is_demo=is_demo_req, persist=False)
    except SupabaseRepositoryError as e:
        logger.exception("[Student] Supabase repository error retrieving roadmap: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database failure retrieving student roadmap.",
        )
    except RuntimeError as e:
        logger.warning("[Student] Roadmap computation unavailable: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Roadmap service temporarily unavailable.",
        )


@router.post("/student/me/roadmap/recalculate")
async def recalculate_my_roadmap(
    current_user: dict = Depends(get_current_user),
):
    return await recalculate_student_roadmap(student_id=current_user.get("id"), current_user=current_user)


@router.post("/student/{student_id}/roadmap/recalculate")
async def recalculate_student_roadmap(
    student_id: str,
    current_user: dict | None = Depends(get_optional_current_user),
):
    if student_id == "me" and current_user:
        student_id = current_user.get("id")
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to recalculate learning roadmap.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = current_user.get("id")
    user_role = (current_user.get("role") or "").upper()
    if user_id != student_id and user_role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You cannot recalculate another student's learning roadmap.",
        )
    is_demo_id = is_demo_student_id(student_id)
    demo_profiles = get_demo("student_profiles") or []
    is_demo_fixture = any(
        (p.get("user_id") or p.get("id")) == student_id
        for p in demo_profiles
        if p.get("source") in ("DEMO_SYNTHETIC", "BENCHMARK_NATIONAL") or p.get("is_demo") is True or is_demo_student_id(p.get("user_id") or p.get("id"))
    )
    is_demo_req = is_demo_id or is_demo_fixture
    from app.services.roadmap_service import compute_adaptive_roadmap
    from app.repositories.supabase_repository import SupabaseRepositoryError
    try:
        return compute_adaptive_roadmap(student_id=student_id, is_demo=is_demo_req, persist=True)
    except SupabaseRepositoryError as e:
        logger.exception("[Student] Supabase repository error recalculating roadmap: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database failure recalculating student roadmap.",
        )
    except RuntimeError as e:
        logger.warning("[Student] Roadmap recalculation unavailable: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Roadmap recalculation currently unavailable.",
        )



@router.get("/students")
async def list_students(
    is_demo: bool | None = Query(None, description="Explicit demo/real mode selector"),
    current_user: dict | None = Depends(get_optional_current_user),
):
    """List all students (real profiles + user submitted assessments, or demo students in explicit demo mode)."""
    user_role = (current_user.get("role") or "").upper() if current_user else ""
    if is_explicit_demo_mode(is_demo) or user_role != "ADMIN":
        profiles = get_demo("student_profiles")
        assessments = get_demo("student_assessments")
    else:
        try:
            from app.repositories.supabase_repository import list_student_profiles, list_student_assessments
            profiles = list_student_profiles() or []
            assessments = list_student_assessments() or []
        except Exception as e:
            logger.warning("[ListStudents] Supabase query failed: %s", e)
            profiles = []
            assessments = []
    results = [
        {"user_id": p.get("user_id") or p.get("id"), "name": p.get("name", "Student"), "target_role": p.get("target_role", "Target Career"),
         "skill_match_pct": p.get("skill_match_pct", 50), "source": p.get("source", "DEMO_SYNTHETIC")}
        for p in profiles
    ]
    for a in assessments:
        if a.get("source") == "USER_SUBMITTED" or a.get("id", "").startswith("ast-usr-"):
            aid = a.get("id")
            if not any(r["user_id"] == aid for r in results):
                results.append({
                    "user_id": aid,
                    "name": f"{a.get('name', 'Candidate')} (Self-Assessed)",
                    "target_role": a.get("career_goal", "Target Career"),
                    "skill_match_pct": a.get("skill_match_pct", 50),
                    "source": "USER_SUBMITTED",
                })
    return results


@router.get("/student/assessment/quiz-questions")
async def get_quiz_questions(
    student_id: str | None = Query(None),
    current_user: dict | None = Depends(get_optional_current_user),
):
    if current_user:
        user_role = (current_user.get("role") or "").upper()
        target_id = student_id if (user_role == "ADMIN" and student_id) else current_user.get("id")
        user_email = current_user.get("email")
        res = get_personalized_diagnostic_questions(target_id, user_email)
        if res.get("status") == "profile_incomplete":
            return {
                "status": "profile_incomplete",
                "domain": "general",
                "message": res.get("message"),
                "questions": get_diagnostic_quiz_questions(),
            }
        return res
    return {
        "status": "unauthenticated",
        "domain": "general",
        "questions": get_diagnostic_quiz_questions(),
    }


@router.post("/student/assessment")
async def submit_student_assessment(
    submission: AssessmentSubmission,
    current_user: dict | None = Depends(get_optional_current_user),
):
    submission_data = {
        "name": submission.name,
        "education": submission.education,
        "career_goal": submission.career_goal,
        "district": submission.district or "Maharashtra",
        "current_skills": [
            {"skill_name": s.skill_name, "proficiency": s.proficiency}
            for s in submission.current_skills
        ],
        "interests": submission.interests,
        "quiz_answers": submission.quiz_answers,
    }

    if current_user:
        submission_data["user_id"] = current_user.get("id")

    assessment_record = evaluate_student_assessment(submission_data)

    if current_user:
        assessment_record["user_id"] = current_user.get("id")
        assessment_record["user_email"] = current_user.get("email")

    now_iso = datetime.now(timezone.utc).isoformat()
    assessment_record.setdefault("created_at", now_iso)
    assessment_record["updated_at"] = now_iso
    uid = current_user.get("id") if current_user else None
    is_demo = is_demo_student_id(uid) if uid else assessment_record.get("is_demo", False)
    assessment_record["is_demo"] = is_demo
    if is_demo:
        assessment_record["source"] = "DEMO_SYNTHETIC"
        assessment_record["source_label"] = "Demo Assessment Simulation"
        assessment_record["data_provenance"] = "DEMO_SYNTHETIC"
    else:
        assessment_record.setdefault("source", "USER_SUBMITTED")
        assessment_record.setdefault("data_provenance", "SELF_REPORTED_ASSESSMENT")

    try:
        from app.repositories.supabase_repository import create_student_assessment
        saved_record = create_student_assessment(assessment_record)
    except Exception as e:
        logger.exception("[StudentRouter] Supabase persistence failed for assessment: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database insertion failed for student assessment.",
        ) from e

    if current_user:
        try:
            from app.repositories.supabase_repository import get_student_profile, upsert_student_profile
            from app.routers.profile import resolve_taxonomy_skill_ids
            user_id = current_user.get("id")
            existing_prof = get_student_profile(user_id) or {}
            merged_skills = list(existing_prof.get("skills") or [])
            existing_indices = {
                (s.get("skill_name") or s.get("name") or "").lower(): idx
                for idx, s in enumerate(merged_skills)
                if isinstance(s, dict)
            }
            for sk in submission_data.get("current_skills", []):
                s_name = (sk.get("skill_name") or "").strip()
                if not s_name:
                    continue
                if s_name.lower() in existing_indices:
                    merged_skills[existing_indices[s_name.lower()]]["proficiency"] = sk.get("proficiency", "intermediate")
                else:
                    merged_skills.append({
                        "skill_name": s_name,
                        "proficiency": sk.get("proficiency", "intermediate"),
                    })
            candidate_name = submission.name or existing_prof.get("name") or existing_prof.get("full_name") or current_user.get("full_name") or current_user.get("name")
            resolved_skills = resolve_taxonomy_skill_ids(merged_skills)
            profile_sync_payload = {
                "user_id": user_id,
                "name": candidate_name,
                "full_name": candidate_name,
                "preferred_location": submission.district or existing_prof.get("preferred_location"),
                "target_role": submission.career_goal or existing_prof.get("target_role"),
                "desired_role": submission.career_goal or existing_prof.get("desired_role"),
                "degree": existing_prof.get("degree") or submission.education,
                "education_level": existing_prof.get("education_level") or "Undergraduate",
                "institution": existing_prof.get("institution") or "Not Specified",
                "career_interests": list(dict.fromkeys((existing_prof.get("career_interests") or []) + (submission.interests or []))),
                "skills": resolved_skills,
                "skill_match_pct": assessment_record.get("skill_match_pct", existing_prof.get("skill_match_pct", 50)),
                "source": "USER_SUBMITTED",
                "is_demo": False,
                "updated_at": now_iso,
            }
            if not existing_prof:
                profile_sync_payload["created_at"] = now_iso
            upsert_student_profile(profile_sync_payload)
        except Exception as e:
            logger.exception("[StudentRouter] Profile sync failed during assessment submission: %s", e)

    try:
        if "student_assessments" in _cache:
            _cache["student_assessments"].insert(0, saved_record)
        from app.db import _flush_real_table
        _flush_real_table("student_assessments")
    except Exception:
        pass

    return {
        "status": "success",
        "message": "Self-reported student assessment received and evaluated.",
        "assessment": saved_record,
    }


@router.get("/student/assessments")
async def list_student_assessments(
    source: str | None = Query(None, description="'USER_SUBMITTED' or 'DEMO_SYNTHETIC' or 'all'"),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict | None = Depends(get_optional_current_user),
):
    """List all student assessments with clear separation of user-submitted vs demo data."""
    try:
        from app.repositories.supabase_repository import list_student_assessments as repo_list_assessments
        assessments = repo_list_assessments(source=source, limit=limit)
    except Exception as e:
        logger.exception("[StudentAssessments] Supabase query failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database query failed listing student assessments.",
        ) from e

    user_role = (current_user.get("role") or "").upper() if current_user else ""
    user_id = current_user.get("id") if current_user else None
    if user_role != "ADMIN":
        filtered = []
        for a in assessments:
            if not _is_private_user_record(a):
                filtered.append(a)
            elif user_id and (a.get("user_id") == user_id or a.get("id") == user_id):
                filtered.append(a)
        assessments = filtered

    return {
        "status": "success",
        "total": len(assessments),
        "assessments": assessments,
    }





@router.get("/student/assessment/{assessment_id}")
async def get_student_assessment(
    assessment_id: str,
    current_user: dict | None = Depends(get_optional_current_user),
):
    """Retrieve detailed assessment report by ID with ownership verification."""
    a = None
    try:
        from app.repositories.supabase_repository import get_student_assessment as repo_get_assessment
        a = repo_get_assessment(assessment_id)
    except Exception as e:
        logger.exception("[StudentAssessment] Supabase query failed for %s: %s", assessment_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database query failed for student assessment '{assessment_id}'.",
        ) from e

    if not a and is_demo_student_id(assessment_id):
        assessments = get_demo("student_assessments")
        for item in assessments:
            if item.get("id") == assessment_id:
                a = item
                break

    if a:
        if _is_private_user_record(a):
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required to view candidate assessment report.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            user_id = current_user.get("id")
            user_email = current_user.get("email")
            user_role = (current_user.get("role") or "").upper()
            record_user_id = a.get("user_id")
            is_owner = (
                (record_user_id and user_id == record_user_id)
                or (a.get("id") and user_id == a.get("id"))
                or (user_email and a.get("user_email") == user_email)
            )
            if not is_owner and user_role != "ADMIN":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: You do not have permission to view another student's assessment report.",
                )
        return {"status": "success", "assessment": a}

    raise HTTPException(status_code=404, detail=f"Student assessment record '{assessment_id}' not found.")


# ---------------------------------------------------------------------------
# Phase 16 Endpoints: AI-Powered Career Recommendation & Skill-Gap Engine
# ---------------------------------------------------------------------------

class ExplainAiQuery(BaseModel):
    prompt: str | None = None


def _verify_student_recommendations_access(target_id: str, current_user: dict | None) -> None:
    """Ensure that access to private registered student recommendations requires ownership or admin role.

    No authorization decision is made solely based on ID prefix.
    """
    a = None
    try:
        from app.repositories.supabase_repository import (
            get_student_assessment,
            get_student_assessment_by_user,
            get_student_profile,
            get_employee_profile,
        )
        a = (
            get_student_assessment(target_id)
            or get_student_assessment_by_user(target_id)
            or get_student_profile(target_id)
            or get_employee_profile(target_id)
        )
    except Exception as e:
        logger.exception("[VerifyAccess] Supabase query failed for %s: %s", target_id, e)
        if not is_demo_student_id(target_id):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database query failed verifying candidate permissions.",
            ) from e
        # Degrade gracefully to demo data if available for explicit demo fixtures
        assessments = get_demo("student_assessments")
        for item in assessments:
            if item.get("id") == target_id or item.get("user_id") == target_id:
                a = item
                break
        if not a:
            profiles = get_demo("student_profiles")
            for item in profiles:
                if item.get("id") == target_id or item.get("user_id") == target_id:
                    a = item
                    break

    if not a and is_demo_student_id(target_id):
        assessments = get_demo("student_assessments")
        for item in assessments:
            if item.get("id") == target_id or item.get("user_id") == target_id:
                a = item
                break
        if not a:
            profiles = get_demo("student_profiles")
            for item in profiles:
                if item.get("id") == target_id or item.get("user_id") == target_id:
                    a = item
                    break

    if is_demo_student_id(target_id):
        return

    if a and _is_private_user_record(a):
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to view personalized career recommendations.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_id = current_user.get("id")
        user_email = current_user.get("email")
        user_role = (current_user.get("role") or "").upper()
        record_user_id = a.get("user_id")
        is_owner = (
            (target_id and user_id == target_id)
            or (record_user_id and user_id == record_user_id)
            or (a.get("id") and user_id == a.get("id"))
            or (user_email and a.get("user_email") == user_email)
        )
        if not is_owner and user_role != "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You cannot view another candidate's recommendations.",
            )


@router.get("/student/recommendations/{student_id}")
@router.get("/student/{student_id}/recommendations")
async def get_student_recommendations(
    student_id: str,
    current_user: dict | None = Depends(get_optional_current_user),
):
    """Generate explainable career recommendations connecting student assessment, validated employer demand, and gov opportunities."""
    from app.services.career_recommendation_engine import compute_career_recommendations
    resolved_id = student_id
    if student_id == "me" and current_user:
        resolved_id = current_user.get("id") or "me"
    
    _verify_student_recommendations_access(resolved_id, current_user)

    try:
        recommendations = compute_career_recommendations(resolved_id)
        return recommendations
    except ValueError as e:
        if student_id == "me" or (current_user and resolved_id == current_user.get("id")):
            return {
                "status": "unassessed",
                "has_assessment": False,
                "message": "Complete your diagnostic assessment to receive personalized career recommendations.",
                "recommended_careers": [],
            }
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("[Recommendations] Failed for student %s: %s", resolved_id, e)
        raise HTTPException(status_code=500, detail="Recommendation engine error processing request.")


@router.post("/student/recommendations/{student_id}/explain-ai")
async def explain_student_recommendations_ai(
    student_id: str,
    query: ExplainAiQuery | None = None,
    current_user: dict | None = Depends(get_optional_current_user),
):
    """Generate conversational, encouraging AI Copilot explanation for the student's career recommendation."""
    from app.services.career_recommendation_engine import generate_ai_copilot_explanation
    resolved_id = student_id
    if student_id == "me" and current_user:
        resolved_id = current_user.get("id") or "me"

    _verify_student_recommendations_access(resolved_id, current_user)

    try:
        custom_prompt = query.prompt if query else None
        res = await generate_ai_copilot_explanation(resolved_id, custom_prompt)
        return res
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("[AiExplanation] Failed for student %s: %s", resolved_id, e)
        raise HTTPException(status_code=500, detail="AI explanation error processing request.")




