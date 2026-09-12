from datetime import datetime, timezone
import logging
from typing import Any
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.core.security import get_current_user
from app.repositories import supabase_repository
from app.repositories.supabase_repository import SupabaseRepositoryError, _is_valid_uuid

logger = logging.getLogger("skillsetu.profile")
router = APIRouter()

ALLOWED_PROFICIENCIES = {"beginner", "intermediate", "advanced", "expert"}


def normalize_proficiency(val: Any) -> str:
    if not isinstance(val, str):
        raise ValueError("Proficiency must be a string")
    clean = val.strip().lower()
    if clean not in ALLOWED_PROFICIENCIES:
        raise ValueError(f"Invalid proficiency '{val}'. Allowed values: {sorted(list(ALLOWED_PROFICIENCIES))}")
    return clean


def deduplicate_skills(skills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for sk in skills:
        name = (sk.get("skill_name") or sk.get("name") or "").strip()
        if not name:
            continue
        key = name.lower()
        seen[key] = {
            "skill_id": sk.get("skill_id") or seen.get(key, {}).get("skill_id"),
            "skill_name": name,
            "proficiency": normalize_proficiency(sk.get("proficiency", "beginner")),
        }
    return list(seen.values())


class SkillItem(BaseModel):
    skill_id: str | None = None
    skill_name: str = Field(..., min_length=1, max_length=100)
    proficiency: str = Field(..., description="beginner, intermediate, advanced, expert")

    @field_validator("proficiency")
    @classmethod
    def validate_proficiency(cls, v: str) -> str:
        return normalize_proficiency(v)

    @field_validator("skill_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Skill name cannot be empty")
        return clean


class ProjectItem(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    description: str = Field("", max_length=2000)
    skills: list[str] = Field(default_factory=list)
    url: str | None = Field(None, max_length=500)

    @field_validator("name")
    @classmethod
    def validate_project_name(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Project name cannot be empty")
        return clean


class CertificationItem(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    issuer: str = Field(..., min_length=1, max_length=150)
    issue_date: str | None = Field(None, max_length=50)
    url: str | None = Field(None, max_length=500)

    @field_validator("name", "issuer")
    @classmethod
    def validate_text(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Field cannot be empty")
        return clean


class CourseItem(BaseModel):
    course_name: str = Field(..., min_length=1, max_length=150)
    provider: str | None = Field(None, max_length=150)
    status: str | None = Field("completed", max_length=50)

    @field_validator("course_name")
    @classmethod
    def validate_course_name(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Course name cannot be empty")
        return clean


class ExperienceItem(BaseModel):
    company: str = Field(..., min_length=1, max_length=150)
    role: str = Field(..., min_length=1, max_length=150)
    duration: str | None = Field(None, max_length=100)
    description: str = Field("", max_length=2000)

    @field_validator("company", "role")
    @classmethod
    def validate_exp_text(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Field cannot be empty")
        return clean


class StudentProfilePayload(BaseModel):
    full_name: str | None = Field(None, max_length=150)
    institution: str | None = Field(None, max_length=200)
    degree: str | None = Field(None, max_length=150)
    education_level: str | None = Field(None, max_length=100)
    academic_year: str | None = Field(None, max_length=50)
    graduation_year: int | None = Field(None, ge=1970, le=2100)
    desired_role: str | None = Field(None, max_length=150)
    target_role: str | None = Field(None, max_length=150)
    preferred_location: str | None = Field(None, max_length=100)
    career_interests: list[str] = Field(default_factory=list)
    skills: list[SkillItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    certifications: list[CertificationItem] = Field(default_factory=list)
    courses: list[CourseItem] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)


class StudentProfilePatchPayload(BaseModel):
    full_name: str | None = Field(None, max_length=150)
    institution: str | None = Field(None, max_length=200)
    degree: str | None = Field(None, max_length=150)
    education_level: str | None = Field(None, max_length=100)
    academic_year: str | None = Field(None, max_length=50)
    graduation_year: int | None = Field(None, ge=1970, le=2100)
    desired_role: str | None = Field(None, max_length=150)
    target_role: str | None = Field(None, max_length=150)
    preferred_location: str | None = Field(None, max_length=100)
    career_interests: list[str] | None = None
    skills: list[SkillItem] | None = None
    projects: list[ProjectItem] | None = None
    certifications: list[CertificationItem] | None = None
    courses: list[CourseItem] | None = None
    experience: list[ExperienceItem] | None = None


class EmployeeProfilePayload(BaseModel):
    full_name: str | None = Field(None, max_length=150)
    current_role: str = Field(..., min_length=1, max_length=150)
    years_of_experience: float = Field(0.0, ge=0.0, le=70.0)
    industry: str | None = Field(None, max_length=100)
    education: str | None = Field(None, max_length=200)
    target_role: str | None = Field(None, max_length=150)
    preferred_location: str | None = Field(None, max_length=100)
    skills: list[SkillItem] = Field(default_factory=list)
    certifications: list[CertificationItem] = Field(default_factory=list)

    @field_validator("current_role")
    @classmethod
    def validate_current_role(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Current role cannot be empty")
        return clean


class EmployeeProfilePatchPayload(BaseModel):
    full_name: str | None = Field(None, max_length=150)
    current_role: str | None = Field(None, min_length=1, max_length=150)
    years_of_experience: float | None = Field(None, ge=0.0, le=70.0)
    industry: str | None = Field(None, max_length=100)
    education: str | None = Field(None, max_length=200)
    target_role: str | None = Field(None, max_length=150)
    preferred_location: str | None = Field(None, max_length=100)
    skills: list[SkillItem] | None = None
    certifications: list[CertificationItem] | None = None


def resolve_taxonomy_skill_ids(skills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tax_skills = supabase_repository.list_skills(limit=2000) or []
    if not tax_skills:
        from app.db import _cache
        tax_skills = _cache.get("skills", []) or []
    name_map = {}
    is_authoritative = {}
    for s in tax_skills:
        sname = s.get("name")
        sid = s.get("id")
        if not sname or not sid:
            continue
        canon_key = sname.strip().lower()
        if _is_valid_uuid(sid):
            valid_id = str(sid)
            auth_flag = True
        else:
            valid_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"skill.{canon_key}"))
            auth_flag = False

        keys_to_set = [canon_key]
        for syn in s.get("synonyms", []) or []:
            if syn and isinstance(syn, str) and syn.strip():
                keys_to_set.append(syn.strip().lower())

        for k in keys_to_set:
            if k not in name_map or (auth_flag and not is_authoritative.get(k, False)):
                name_map[k] = valid_id
                is_authoritative[k] = auth_flag

    resolved = []
    for sk in skills:
        sname = sk.get("skill_name", "") or sk.get("name", "")
        clean_key = sname.strip().lower()
        existing_sid = sk.get("skill_id") or sk.get("id")
        sid = str(existing_sid).strip() if existing_sid and _is_valid_uuid(existing_sid) else name_map.get(clean_key)
        resolved.append({
            **sk,
            "skill_id": str(sid) if sid is not None else None,
        })
    return resolved


@router.get("/student/profile")
async def get_my_student_profile(
    current_user: dict[str, Any] = Depends(get_current_user),
):
    role = (current_user.get("role") or "").upper()
    if role not in ("STUDENT", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Student profile access requires STUDENT or ADMIN role.",
        )
    user_id = current_user["id"]
    try:
        profile = supabase_repository.get_student_profile(user_id)
    except SupabaseRepositoryError as e:
        logger.exception("[Profile] Database failure fetching student profile %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database query failed for student profile.",
        ) from e

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student profile not found for user '{user_id}'.",
        )
    return {
        "status": "success",
        "profile": profile,
    }


def ensure_user_in_supabase(user_id: str, current_user: dict[str, Any], role: str) -> None:
    from app.db import get_supabase_client
    client = get_supabase_client()
    if not client:
        return
    try:
        user_res = client.table("users").select("id").eq("id", user_id).execute()
        if not user_res.data:
            client.table("users").upsert({
                "id": user_id,
                "name": current_user.get("full_name") or current_user.get("name") or "Platform User",
                "email": current_user.get("email") or f"{user_id}@skillsetu.gov.in",
                "role": role,
            }, on_conflict="id").execute()
    except Exception as e:
        logger.warning("[Profile] Failed ensuring user presence in Supabase users table: %s", e)


@router.post("/student/profile", status_code=status.HTTP_201_CREATED)
async def create_student_profile(
    payload: StudentProfilePayload,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    role = (current_user.get("role") or "").upper()
    if role not in ("STUDENT", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Student profile creation requires STUDENT or ADMIN role.",
        )
    user_id = current_user["id"]
    ensure_user_in_supabase(user_id, current_user, role)
    now_iso = datetime.now(timezone.utc).isoformat()
    raw_skills = [s.model_dump() for s in payload.skills]
    deduped_skills = deduplicate_skills(raw_skills)
    target = payload.target_role or payload.desired_role or ""
    desired = payload.desired_role or payload.target_role or ""

    try:
        resolved_skills = resolve_taxonomy_skill_ids(deduped_skills)
        profile_dict = {
            "user_id": user_id,
            "full_name": payload.full_name or current_user.get("full_name") or "",
            "institution": payload.institution,
            "degree": payload.degree,
            "education_level": payload.education_level,
            "academic_year": payload.academic_year,
            "graduation_year": payload.graduation_year,
            "target_role": target,
            "desired_role": desired,
            "preferred_location": payload.preferred_location,
            "career_interests": payload.career_interests,
            "skills": resolved_skills,
            "projects": [p.model_dump() for p in payload.projects],
            "certifications": [c.model_dump() for c in payload.certifications],
            "courses": [co.model_dump() for co in payload.courses],
            "experience": [e.model_dump() for e in payload.experience],
            "skill_match_pct": 0,
            "source": "USER_SUBMITTED",
            "is_demo": False,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        saved = supabase_repository.upsert_student_profile(profile_dict)
    except SupabaseRepositoryError as e:
        logger.exception("[Profile] Database failure creating student profile %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database persistence failed for student profile. Please try again later.",
        ) from e

    return {
        "status": "success",
        "message": "Student profile created successfully",
        "profile": saved,
    }


@router.put("/student/profile")
async def update_student_profile(
    payload: StudentProfilePayload,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    role = (current_user.get("role") or "").upper()
    if role not in ("STUDENT", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Student profile update requires STUDENT or ADMIN role.",
        )
    user_id = current_user["id"]
    ensure_user_in_supabase(user_id, current_user, role)
    now_iso = datetime.now(timezone.utc).isoformat()
    raw_skills = [s.model_dump() for s in payload.skills]
    deduped_skills = deduplicate_skills(raw_skills)
    target = payload.target_role or payload.desired_role or ""
    desired = payload.desired_role or payload.target_role or ""

    try:
        resolved_skills = resolve_taxonomy_skill_ids(deduped_skills)
        profile_dict = {
            "user_id": user_id,
            "full_name": payload.full_name or current_user.get("full_name") or "",
            "institution": payload.institution,
            "degree": payload.degree,
            "education_level": payload.education_level,
            "academic_year": payload.academic_year,
            "graduation_year": payload.graduation_year,
            "target_role": target,
            "desired_role": desired,
            "preferred_location": payload.preferred_location,
            "career_interests": payload.career_interests,
            "skills": resolved_skills,
            "projects": [p.model_dump() for p in payload.projects],
            "certifications": [c.model_dump() for c in payload.certifications],
            "courses": [co.model_dump() for co in payload.courses],
            "experience": [e.model_dump() for e in payload.experience],
            "source": "USER_SUBMITTED",
            "is_demo": False,
            "updated_at": now_iso,
        }
        saved = supabase_repository.upsert_student_profile(profile_dict)
    except SupabaseRepositoryError as e:
        logger.exception("[Profile] Database failure updating student profile %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database persistence failed for student profile. Please try again later.",
        ) from e

    return {
        "status": "success",
        "message": "Student profile updated successfully",
        "profile": saved,
    }


@router.patch("/student/profile")
async def patch_student_profile(
    payload: StudentProfilePatchPayload,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    role = (current_user.get("role") or "").upper()
    if role not in ("STUDENT", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Student profile patch requires STUDENT or ADMIN role.",
        )
    user_id = current_user["id"]
    ensure_user_in_supabase(user_id, current_user, role)
    try:
        existing = supabase_repository.get_student_profile(user_id)
    except SupabaseRepositoryError as e:
        logger.exception("[Profile] Database query failure on patch %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database query failed for student profile.",
        ) from e

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student profile not found for user '{user_id}'.",
        )

    try:
        patch_data = payload.model_dump(exclude_unset=True)
        if "skills" in patch_data and patch_data["skills"] is not None:
            raw_skills = [s.model_dump() if hasattr(s, "model_dump") else s for s in payload.skills or []]
            patch_data["skills"] = resolve_taxonomy_skill_ids(deduplicate_skills(raw_skills))
        if "projects" in patch_data and patch_data["projects"] is not None:
            patch_data["projects"] = [p.model_dump() if hasattr(p, "model_dump") else p for p in payload.projects or []]
        if "certifications" in patch_data and patch_data["certifications"] is not None:
            patch_data["certifications"] = [c.model_dump() if hasattr(c, "model_dump") else c for c in payload.certifications or []]
        if "courses" in patch_data and patch_data["courses"] is not None:
            patch_data["courses"] = [co.model_dump() if hasattr(co, "model_dump") else co for co in payload.courses or []]
        if "experience" in patch_data and patch_data["experience"] is not None:
            patch_data["experience"] = [e.model_dump() if hasattr(e, "model_dump") else e for e in payload.experience or []]

        if "desired_role" in patch_data and "target_role" not in patch_data:
            patch_data["target_role"] = patch_data["desired_role"]
        elif "target_role" in patch_data and "desired_role" not in patch_data:
            patch_data["desired_role"] = patch_data["target_role"]

        merged = {**existing, **patch_data, "updated_at": datetime.now(timezone.utc).isoformat()}
        saved = supabase_repository.upsert_student_profile(merged)
    except SupabaseRepositoryError as e:
        logger.exception("[Profile] Database upsert failure on patch %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database persistence failed for student profile patch. Please try again later.",
        ) from e

    return {
        "status": "success",
        "message": "Student profile patched successfully",
        "profile": saved,
    }


class SkillsUpdatePayload(BaseModel):
    skills: list[SkillItem]


@router.put("/student/profile/skills")
async def update_student_skills(
    payload: SkillsUpdatePayload,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    role = (current_user.get("role") or "").upper()
    if role not in ("STUDENT", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Student skills update requires STUDENT or ADMIN role.",
        )
    user_id = current_user["id"]
    try:
        existing = supabase_repository.get_student_profile(user_id)
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found.")
        raw_skills = [s.model_dump() for s in payload.skills]
        deduped = resolve_taxonomy_skill_ids(deduplicate_skills(raw_skills))
        updated = {**existing, "skills": deduped, "updated_at": datetime.now(timezone.utc).isoformat()}
        saved = supabase_repository.upsert_student_profile(updated)
        return {
            "status": "success",
            "skills": saved.get("skills", []),
        }
    except SupabaseRepositoryError as e:
        logger.exception("[Profile] Database failure updating student skills %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed for student skills.",
        ) from e


@router.post("/student/profile/skills")
async def add_student_skill(
    skill: SkillItem,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    role = (current_user.get("role") or "").upper()
    if role not in ("STUDENT", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Student skill addition requires STUDENT or ADMIN role.",
        )
    user_id = current_user["id"]
    try:
        existing = supabase_repository.get_student_profile(user_id)
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found.")
        curr_skills = list(existing.get("skills") or [])
        curr_skills.append(skill.model_dump())
        deduped = resolve_taxonomy_skill_ids(deduplicate_skills(curr_skills))
        updated = {**existing, "skills": deduped, "updated_at": datetime.now(timezone.utc).isoformat()}
        saved = supabase_repository.upsert_student_profile(updated)
        return {
            "status": "success",
            "skills": saved.get("skills", []),
        }
    except SupabaseRepositoryError as e:
        logger.exception("[Profile] Database failure adding student skill %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed for student skill.",
        ) from e


@router.delete("/student/profile/skills/{skill_name}")
async def delete_student_skill(
    skill_name: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    role = (current_user.get("role") or "").upper()
    if role not in ("STUDENT", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Student skill deletion requires STUDENT or ADMIN role.",
        )
    user_id = current_user["id"]
    clean_target = skill_name.strip().lower()
    try:
        existing = supabase_repository.get_student_profile(user_id)
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found.")
        curr_skills = [
            s for s in (existing.get("skills") or [])
            if (s.get("skill_name") or s.get("name") or "").strip().lower() != clean_target
            and str(s.get("skill_id") or "").strip().lower() != clean_target
        ]
        updated = {**existing, "skills": curr_skills, "updated_at": datetime.now(timezone.utc).isoformat()}
        saved = supabase_repository.upsert_student_profile(updated)
        return {
            "status": "success",
            "skills": saved.get("skills", []),
        }
    except SupabaseRepositoryError as e:
        logger.exception("[Profile] Database failure deleting student skill %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed for student skill deletion.",
        ) from e


class ProjectsUpdatePayload(BaseModel):
    projects: list[ProjectItem]


@router.put("/student/profile/projects")
async def update_student_projects(
    payload: ProjectsUpdatePayload,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    role = (current_user.get("role") or "").upper()
    if role not in ("STUDENT", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Student projects update requires STUDENT or ADMIN role.",
        )
    user_id = current_user["id"]
    try:
        existing = supabase_repository.get_student_profile(user_id)
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found.")
        updated = {
            **existing,
            "projects": [p.model_dump() for p in payload.projects],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        saved = supabase_repository.upsert_student_profile(updated)
        return {
            "status": "success",
            "projects": saved.get("projects", []),
        }
    except SupabaseRepositoryError as e:
        logger.exception("[Profile] Database failure updating student projects %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed for student projects.",
        ) from e


class CertificationsUpdatePayload(BaseModel):
    certifications: list[CertificationItem]


@router.put("/student/profile/certifications")
async def update_student_certifications(
    payload: CertificationsUpdatePayload,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    role = (current_user.get("role") or "").upper()
    if role not in ("STUDENT", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Student certifications update requires STUDENT or ADMIN role.",
        )
    user_id = current_user["id"]
    try:
        existing = supabase_repository.get_student_profile(user_id)
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found.")
        updated = {
            **existing,
            "certifications": [c.model_dump() for c in payload.certifications],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        saved = supabase_repository.upsert_student_profile(updated)
        return {
            "status": "success",
            "certifications": saved.get("certifications", []),
        }
    except SupabaseRepositoryError as e:
        logger.exception("[Profile] Database failure updating student certifications %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed for student certifications.",
        ) from e


class CoursesUpdatePayload(BaseModel):
    courses: list[CourseItem]


@router.put("/student/profile/courses")
async def update_student_courses(
    payload: CoursesUpdatePayload,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    role = (current_user.get("role") or "").upper()
    if role not in ("STUDENT", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Student courses update requires STUDENT or ADMIN role.",
        )
    user_id = current_user["id"]
    try:
        existing = supabase_repository.get_student_profile(user_id)
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found.")
        updated = {
            **existing,
            "courses": [co.model_dump() for co in payload.courses],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        saved = supabase_repository.upsert_student_profile(updated)
        return {
            "status": "success",
            "courses": saved.get("courses", []),
        }
    except SupabaseRepositoryError as e:
        logger.exception("[Profile] Database failure updating student courses %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed for student courses.",
        ) from e


@router.get("/employee/profile")
async def get_my_employee_profile(
    current_user: dict[str, Any] = Depends(get_current_user),
):
    role = (current_user.get("role") or "").upper()
    if role not in ("EMPLOYEE", "EMPLOYER", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Employee profile access requires EMPLOYEE, EMPLOYER, or ADMIN role.",
        )
    user_id = current_user["id"]
    try:
        profile = supabase_repository.get_employee_profile(user_id)
    except SupabaseRepositoryError as e:
        logger.exception("[Profile] Database failure fetching employee profile %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database query failed for employee profile.",
        ) from e

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee profile not found for user '{user_id}'.",
        )
    return {
        "status": "success",
        "profile": profile,
    }


@router.post("/employee/profile", status_code=status.HTTP_201_CREATED)
async def create_employee_profile(
    payload: EmployeeProfilePayload,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    role = (current_user.get("role") or "").upper()
    if role not in ("EMPLOYEE", "EMPLOYER", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Employee profile creation requires EMPLOYEE, EMPLOYER, or ADMIN role.",
        )
    user_id = current_user["id"]
    ensure_user_in_supabase(user_id, current_user, role)
    now_iso = datetime.now(timezone.utc).isoformat()
    raw_skills = [s.model_dump() for s in payload.skills]
    deduped_skills = deduplicate_skills(raw_skills)

    try:
        resolved_skills = resolve_taxonomy_skill_ids(deduped_skills)
        profile_dict = {
            "user_id": user_id,
            "full_name": payload.full_name or current_user.get("full_name") or "",
            "current_role": payload.current_role,
            "years_of_experience": payload.years_of_experience,
            "industry": payload.industry,
            "education": payload.education,
            "target_role": payload.target_role,
            "preferred_location": payload.preferred_location,
            "skills": resolved_skills,
            "certifications": [c.model_dump() for c in payload.certifications],
            "source": "USER_SUBMITTED",
            "is_demo": False,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        saved = supabase_repository.upsert_employee_profile(profile_dict)
    except SupabaseRepositoryError as e:
        logger.exception("[Profile] Database failure creating employee profile %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database persistence failed for employee profile.",
        ) from e

    return {
        "status": "success",
        "message": "Employee profile created successfully",
        "profile": saved,
    }


@router.put("/employee/profile")
async def update_employee_profile(
    payload: EmployeeProfilePayload,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    role = (current_user.get("role") or "").upper()
    if role not in ("EMPLOYEE", "EMPLOYER", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Employee profile update requires EMPLOYEE, EMPLOYER, or ADMIN role.",
        )
    user_id = current_user["id"]
    ensure_user_in_supabase(user_id, current_user, role)
    now_iso = datetime.now(timezone.utc).isoformat()
    raw_skills = [s.model_dump() for s in payload.skills]
    deduped_skills = deduplicate_skills(raw_skills)

    try:
        resolved_skills = resolve_taxonomy_skill_ids(deduped_skills)
        profile_dict = {
            "user_id": user_id,
            "full_name": payload.full_name or current_user.get("full_name") or "",
            "current_role": payload.current_role,
            "years_of_experience": payload.years_of_experience,
            "industry": payload.industry,
            "education": payload.education,
            "target_role": payload.target_role,
            "preferred_location": payload.preferred_location,
            "skills": resolved_skills,
            "certifications": [c.model_dump() for c in payload.certifications],
            "source": "USER_SUBMITTED",
            "is_demo": False,
            "updated_at": now_iso,
        }
        saved = supabase_repository.upsert_employee_profile(profile_dict)
    except SupabaseRepositoryError as e:
        logger.exception("[Profile] Database failure updating employee profile %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database persistence failed for employee profile.",
        ) from e

    return {
        "status": "success",
        "message": "Employee profile updated successfully",
        "profile": saved,
    }


@router.patch("/employee/profile")
async def patch_employee_profile(
    payload: EmployeeProfilePatchPayload,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    role = (current_user.get("role") or "").upper()
    if role not in ("EMPLOYEE", "EMPLOYER", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Employee profile patch requires EMPLOYEE, EMPLOYER, or ADMIN role.",
        )
    user_id = current_user["id"]
    ensure_user_in_supabase(user_id, current_user, role)
    try:
        existing = supabase_repository.get_employee_profile(user_id)
    except SupabaseRepositoryError as e:
        logger.exception("[Profile] Database query failure on employee patch %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database query failed for employee profile.",
        ) from e

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee profile not found for user '{user_id}'.",
        )

    try:
        patch_data = payload.model_dump(exclude_unset=True)
        if "skills" in patch_data and patch_data["skills"] is not None:
            raw_skills = [s.model_dump() if hasattr(s, "model_dump") else s for s in payload.skills or []]
            patch_data["skills"] = resolve_taxonomy_skill_ids(deduplicate_skills(raw_skills))
        if "certifications" in patch_data and patch_data["certifications"] is not None:
            patch_data["certifications"] = [c.model_dump() if hasattr(c, "model_dump") else c for c in payload.certifications or []]

        merged = {**existing, **patch_data, "updated_at": datetime.now(timezone.utc).isoformat()}
        saved = supabase_repository.upsert_employee_profile(merged)
    except SupabaseRepositoryError as e:
        logger.exception("[Profile] Database upsert failure on employee patch %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database persistence failed for employee profile patch.",
        ) from e

    return {
        "status": "success",
        "message": "Employee profile patched successfully",
        "profile": saved,
    }


@router.put("/employee/profile/skills")
async def update_employee_skills(
    payload: SkillsUpdatePayload,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    role = (current_user.get("role") or "").upper()
    if role not in ("EMPLOYEE", "EMPLOYER", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Employee skills update requires EMPLOYEE, EMPLOYER, or ADMIN role.",
        )
    user_id = current_user["id"]
    try:
        existing = supabase_repository.get_employee_profile(user_id)
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee profile not found.")
        raw_skills = [s.model_dump() for s in payload.skills]
        deduped = resolve_taxonomy_skill_ids(deduplicate_skills(raw_skills))
        updated = {**existing, "skills": deduped, "updated_at": datetime.now(timezone.utc).isoformat()}
        saved = supabase_repository.upsert_employee_profile(updated)
        return {
            "status": "success",
            "skills": saved.get("skills", []),
        }
    except SupabaseRepositoryError as e:
        logger.exception("[Profile] Database failure updating employee skills %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed for employee skills.",
        ) from e


@router.post("/employee/profile/skills")
async def add_employee_skill(
    skill: SkillItem,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    role = (current_user.get("role") or "").upper()
    if role not in ("EMPLOYEE", "EMPLOYER", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Employee skill addition requires EMPLOYEE, EMPLOYER, or ADMIN role.",
        )
    user_id = current_user["id"]
    try:
        existing = supabase_repository.get_employee_profile(user_id)
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee profile not found.")
        curr_skills = list(existing.get("skills") or [])
        curr_skills.append(skill.model_dump())
        deduped = resolve_taxonomy_skill_ids(deduplicate_skills(curr_skills))
        updated = {**existing, "skills": deduped, "updated_at": datetime.now(timezone.utc).isoformat()}
        saved = supabase_repository.upsert_employee_profile(updated)
        return {
            "status": "success",
            "skills": saved.get("skills", []),
        }
    except SupabaseRepositoryError as e:
        logger.exception("[Profile] Database failure adding employee skill %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed for employee skill.",
        ) from e


@router.delete("/employee/profile/skills/{skill_name}")
async def delete_employee_skill(
    skill_name: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    role = (current_user.get("role") or "").upper()
    if role not in ("EMPLOYEE", "EMPLOYER", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Employee skill deletion requires EMPLOYEE, EMPLOYER, or ADMIN role.",
        )
    user_id = current_user["id"]
    clean_target = skill_name.strip().lower()
    try:
        existing = supabase_repository.get_employee_profile(user_id)
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee profile not found.")
        curr_skills = [
            s for s in (existing.get("skills") or [])
            if (s.get("skill_name") or s.get("name") or "").strip().lower() != clean_target
            and str(s.get("skill_id") or "").strip().lower() != clean_target
        ]
        updated = {**existing, "skills": curr_skills, "updated_at": datetime.now(timezone.utc).isoformat()}
        saved = supabase_repository.upsert_employee_profile(updated)
        return {
            "status": "success",
            "skills": saved.get("skills", []),
        }
    except SupabaseRepositoryError as e:
        logger.exception("[Profile] Database failure deleting employee skill %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed for employee skill deletion.",
        ) from e


@router.put("/employee/profile/certifications")
async def update_employee_certifications(
    payload: CertificationsUpdatePayload,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    role = (current_user.get("role") or "").upper()
    if role not in ("EMPLOYEE", "EMPLOYER", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Employee certifications update requires EMPLOYEE, EMPLOYER, or ADMIN role.",
        )
    user_id = current_user["id"]
    try:
        existing = supabase_repository.get_employee_profile(user_id)
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee profile not found.")
        updated = {
            **existing,
            "certifications": [c.model_dump() for c in payload.certifications],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        saved = supabase_repository.upsert_employee_profile(updated)
        return {
            "status": "success",
            "certifications": saved.get("certifications", []),
        }
    except SupabaseRepositoryError as e:
        logger.exception("[Profile] Database failure updating employee certifications %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed for employee certifications.",
        ) from e
