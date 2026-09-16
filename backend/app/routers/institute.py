"""Institute Data Management API — courses, vocational training programs, capacity reporting, and skill alignment."""
from datetime import datetime, timezone
import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

import logging
from app.db import get_demo, save_course, update_course, delete_course
from app.core.security import get_current_user, get_optional_current_user, require_roles
from app.repositories.supabase_repository import (
    get_course,
    list_courses,
    create_course,
    update_course_repo,
    delete_course_repo,
    SupabaseRepositoryError,
    CourseNotFoundError,
)

logger = logging.getLogger("skillsetu.institute")

router = APIRouter()


class InstituteCourseCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=200, description="Course / Program Name")
    institute_name: str | None = Field(None, description="Institute / College Name")
    district: str = Field(..., min_length=2, max_length=100, description="Maharashtra District")
    category: str = Field(default="Vocational & Emerging Tech", max_length=100)
    description: str = Field(default="", max_length=2000)
    skills: list[str] = Field(..., min_length=1, description="List of skills covered in syllabus")
    nsqf_level: int = Field(default=5, ge=1, le=10)
    enrolment_capacity: int = Field(default=60, ge=1, le=10000)
    placed_count: int = Field(default=0, ge=0)
    duration_weeks: int = Field(default=12, ge=1, le=260)
    certifications: list[str] | str | None = None
    status: str = Field(default="active")


class InstituteCourseUpdate(BaseModel):
    name: str | None = None
    institute_name: str | None = None
    district: str | None = None
    category: str | None = None
    description: str | None = None
    skills: list[str] | None = None
    nsqf_level: int | None = None
    enrolment_capacity: int | None = None
    placed_count: int | None = None
    duration_weeks: int | None = None
    certifications: list[str] | str | None = None
    status: str | None = None


@router.post("/institute/courses")
@router.post("/institute/programs")
async def create_institute_course(
    data: InstituteCourseCreate,
    current_user: dict = Depends(require_roles(["INSTITUTE", "ADMIN"])),
):
    """Submit a first-party vocational / academic course with skills curriculum and capacity."""
    inst_name = (
        data.institute_name
        or current_user.get("organization_id")
        or current_user.get("full_name")
        or "Maharashtra Training Institute"
    ).strip()

    course_id = f"cr-inst-{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    enrolment = max(1, data.enrolment_capacity)
    placed = max(0, data.placed_count)
    placement_rate = round((placed / enrolment) * 100)

    course_record = {
        "id": course_id,
        "course_id": course_id,
        "name": data.name.strip(),
        "course_name": data.name.strip(),
        "description": data.description.strip(),
        "institute": inst_name,
        "institute_name": inst_name,
        "district": data.district.strip(),
        "category": data.category.strip(),
        "skills": data.skills,
        "skills_taught": data.skills,
        "nsqf_level": data.nsqf_level,
        "enrolment_count": enrolment,
        "enrolment_capacity": enrolment,
        "student_count": enrolment,
        "placed_count": placed,
        "placement_rate": placement_rate,
        "duration_weeks": data.duration_weeks,
        "certifications": data.certifications,
        "status": data.status,
        "source": "USER_SUBMITTED",
        "is_demo": False,
        "data_provenance": "INSTITUTE_REPORTED",
        "submitted_at": now_iso,
        "user_id": current_user.get("id"),
        "user_email": current_user.get("email"),
        "institute_id": current_user.get("organization_id") or f"inst-{current_user['id']}",
    }

    try:
        saved = create_course(course_record)
    except SupabaseRepositoryError as e:
        logger.exception("[Institute] Failed creating course in Supabase: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database persistence failed for course.",
        )

    try:
        save_course(course_record, sync_repo=False)
    except Exception:
        pass

    return {
        "status": "created",
        "message": f"Course program '{course_id}' successfully submitted into state registry.",
        "course": saved,
    }


@router.get("/institute/me/courses")
@router.get("/institute/my-courses")
@router.get("/institute/courses/mine")
async def list_my_courses(current_user: dict = Depends(require_roles(["INSTITUTE", "ADMIN"]))):
    """Retrieve courses submitted by the current authenticated training institute account."""
    try:
        all_courses = list_courses()
    except SupabaseRepositoryError as e:
        logger.exception("[Institute] Failed querying courses from Supabase: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database query failed for courses.",
        )

    user_id = current_user.get("id")
    org_id = current_user.get("organization_id")
    email = current_user.get("email")

    if current_user.get("role", "").upper() == "ADMIN":
        my_courses = [c for c in all_courses if c.get("source") in ("USER_SUBMITTED", "INSTITUTE_SUBMITTED") or c.get("is_demo") is False]
    else:
        my_courses = [
            c for c in all_courses
            if c.get("user_id") == user_id or (org_id and c.get("institute_id") == org_id) or (email and c.get("user_email") == email)
        ]

    return {
        "status": "success",
        "total": len(my_courses),
        "courses": my_courses,
    }


@router.get("/institute/courses")
async def list_institute_courses(
    district: str | None = Query(None),
    category: str | None = Query(None),
    skill: str | None = Query(None),
    source: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = Query(None),
):
    """Query state curriculum and training offerings with rich filtering and search."""
    try:
        all_courses = list_courses(
            district=district,
            category=category,
            source=source,
            status=status_filter,
        )
    except SupabaseRepositoryError as e:
        logger.exception("[Institute] Failed querying courses from Supabase: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
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

    if status_filter and status_filter.lower() != "all":
        st_clean = status_filter.strip().lower()
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

    return results


@router.get("/institute/courses/{course_id}")
async def get_institute_course(course_id: str):
    """Retrieve detailed individual training course record."""
    try:
        c = get_course(course_id)
    except SupabaseRepositoryError as e:
        logger.exception("[Institute] Failed fetching course '%s' from Supabase: %s", course_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database query failed for course '{course_id}'.",
        )
    if c:
        return {"status": "success", "course": c}

    raise HTTPException(status_code=404, detail=f"Course '{course_id}' not found.")


@router.patch("/institute/courses/{course_id}")
async def update_my_course(
    course_id: str,
    updates: InstituteCourseUpdate,
    current_user: dict = Depends(require_roles(["INSTITUTE", "ADMIN"])),
):
    """Update training course record with ownership authorization."""
    try:
        matched = get_course(course_id)
    except SupabaseRepositoryError as e:
        logger.exception("[Institute] Failed fetching course '%s' for update: %s", course_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database query failed for course '{course_id}'.",
        )
    if not matched:
        raise HTTPException(status_code=404, detail=f"Course '{course_id}' not found.")

    user_role = (current_user.get("role") or "").upper()
    user_id = current_user.get("id")
    org_id = current_user.get("organization_id")
    is_owner = bool(
        (user_id and matched.get("user_id") == user_id)
        or (org_id and matched.get("institute_id") == org_id)
    )

    if user_role != "ADMIN" and not is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to edit another institute's course offering.",
        )

    patch_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    if not patch_data:
        raise HTTPException(status_code=422, detail="No fields provided for update.")

    if "enrolment_capacity" in patch_data:
        patch_data["enrolment_count"] = patch_data["enrolment_capacity"]
        patch_data["student_count"] = patch_data["enrolment_capacity"]

    if "placed_count" in patch_data or "enrolment_capacity" in patch_data:
        placed = patch_data.get("placed_count", matched.get("placed_count", 0))
        enrol = patch_data.get("enrolment_capacity", matched.get("enrolment_count", 50))
        patch_data["placement_rate"] = round((placed / max(1, enrol)) * 100)

    patch_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    try:
        updated = update_course_repo(course_id, patch_data)
    except CourseNotFoundError:
        raise HTTPException(status_code=404, detail=f"Course '{course_id}' not found.")
    except SupabaseRepositoryError as e:
        logger.exception("[Institute] Failed updating course '%s' in Supabase: %s", course_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database update failed for course.",
        )

    try:
        update_course(course_id, patch_data, sync_repo=False)
    except Exception:
        pass

    return {"status": "success", "message": "Course program updated.", "course": updated}


@router.delete("/institute/courses/{course_id}")
async def delete_my_course(
    course_id: str,
    current_user: dict = Depends(require_roles(["INSTITUTE", "ADMIN"])),
):
    """Delete training course offering with ownership authorization."""
    try:
        matched = get_course(course_id)
    except SupabaseRepositoryError as e:
        logger.exception("[Institute] Failed fetching course '%s' for deletion: %s", course_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database query failed for course '{course_id}'.",
        )
    if not matched:
        raise HTTPException(status_code=404, detail=f"Course '{course_id}' not found.")

    user_role = (current_user.get("role") or "").upper()
    user_id = current_user.get("id")
    org_id = current_user.get("organization_id")
    is_owner = bool(
        (user_id and matched.get("user_id") == user_id)
        or (org_id and matched.get("institute_id") == org_id)
    )

    if user_role != "ADMIN" and not is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to delete another institute's course offering.",
        )

    try:
        deleted = delete_course_repo(course_id)
    except SupabaseRepositoryError as e:
        logger.exception("[Institute] Failed deleting course '%s' from Supabase: %s", course_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database deletion failed for course.",
        )

    if not deleted:
        raise HTTPException(status_code=404, detail=f"Course '{course_id}' not found.")

    try:
        delete_course(course_id, sync_repo=False)
    except Exception:
        pass

    return {"status": "success", "message": f"Course program '{course_id}' removed.", "deleted_id": course_id}


# Phase 34: Institute Syllabus Ingestion & Skill Extraction
from app.services.syllabus_extractor import extract_skills_from_syllabus


@router.post("/institute/syllabus/extract")
async def extract_institute_syllabus(
    request: Request,
    current_user: dict | None = Depends(get_optional_current_user),
):
    """Ingest syllabus text or document file and extract aligned skills, NSQF level, and domain category."""
    content_type = request.headers.get("content-type", "")
    content: str | bytes = ""
    course_name_hint: str | None = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        file = form.get("file")
        if file and hasattr(file, "read"):
            content = await file.read()
            filename = getattr(file, "filename", "")
            if filename:
                course_name_hint = filename.rsplit(".", 1)[0].replace("-", " ").replace("_", " ").title()
        text_field = form.get("syllabus_text")
        if not content and text_field:
            content = str(text_field)
        if form.get("course_name"):
            course_name_hint = str(form.get("course_name"))
    else:
        try:
            body = await request.json()
        except Exception:
            body = {}
        content = body.get("syllabus_text", "")
        course_name_hint = body.get("course_name")

    if not content or (isinstance(content, str) and not content.strip()):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Syllabus content is empty. Please provide syllabus_text or upload a syllabus document.",
        )

    try:
        return extract_skills_from_syllabus(content, course_name_hint=course_name_hint)
    except Exception as e:
        logger.exception("[Institute] Error extracting syllabus skills: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Syllabus analysis failed.",
        ) from e

