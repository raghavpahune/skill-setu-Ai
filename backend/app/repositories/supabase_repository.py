"""Supabase Data-Access Repository for SkillSetu.

Phase 32A: Established as the authoritative persistence layer for employer_feedback.
Eliminates reliance on in-memory _cache and JSON writes for migrated domains.
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("skillsetu.repository.supabase")

_client_override: Any | None = None


def _is_valid_uuid(val: Any) -> bool:
    try:
        uuid.UUID(str(val))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


class SupabaseRepositoryError(Exception):
    """Base exception for Supabase repository data-access failures."""
    pass


class FeedbackNotFoundError(SupabaseRepositoryError):
    """Raised when an employer feedback record does not exist in Supabase."""
    pass


class DemandNotFoundError(SupabaseRepositoryError):
    """Raised when an employer demand record does not exist in Supabase."""
    pass


class AssessmentNotFoundError(SupabaseRepositoryError):
    """Raised when a student assessment record cannot be located in Supabase."""
    pass


class ProfileNotFoundError(SupabaseRepositoryError):
    """Raised when a student profile record cannot be located in Supabase."""
    pass


class EmployeeProfileNotFoundError(SupabaseRepositoryError):
    pass



class CourseNotFoundError(SupabaseRepositoryError):
    """Raised when a course record cannot be located in Supabase."""
    pass


class IndustrySignalNotFoundError(SupabaseRepositoryError):
    """Raised when an industry signal record cannot be located in Supabase."""
    pass


class SkillForecastNotFoundError(SupabaseRepositoryError):
    """Raised when a skill forecast record cannot be located in Supabase."""
    pass


class JobNotFoundError(SupabaseRepositoryError):
    """Raised when a job/opportunity record cannot be located in Supabase."""
    pass


class SchemeNotFoundError(SupabaseRepositoryError):
    """Raised when a scheme record cannot be located in Supabase."""
    pass


class SupabaseConnectionError(SupabaseRepositoryError):
    """Raised when Supabase client is not configured or fails to connect."""
    pass


def set_supabase_client(client: Any | None) -> None:
    """Set a client override (useful for testing and dependency injection)."""
    global _client_override
    _client_override = client


def reset_supabase_client() -> None:
    """Reset the client override to default behavior."""
    global _client_override
    _client_override = None


def get_client() -> Any:
    """Retrieve active Supabase client or raise SupabaseConnectionError."""
    global _client_override
    if _client_override is not None:
        return _client_override

    from app.db import get_supabase_client
    client = get_supabase_client()
    if client is None:
        raise SupabaseConnectionError(
            "Supabase client is not configured or unavailable. Check SUPABASE_URL and credentials."
        )
    return client


# ============================================================================
# EMPLOYER FEEDBACK REPOSITORY DOMAIN (Phase 32A)
# ============================================================================

def get_employer_feedback(feedback_id: str) -> dict[str, Any] | None:
    """Query single employer feedback record by ID directly from Supabase."""
    try:
        client = get_client()
        res = client.table("employer_feedback").select("*").eq("id", feedback_id).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]
        return None
    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed querying employer_feedback id='%s': %s", feedback_id, e)
        raise SupabaseRepositoryError(f"Database query failed for employer_feedback '{feedback_id}': {e}") from e


def list_employer_feedback(
    status: str | None = None,
    demand_level: str | None = None,
) -> list[dict[str, Any]]:
    """Query employer feedback records directly from Supabase with optional filtering."""
    try:
        client = get_client()
        query = client.table("employer_feedback").select("*")

        if status and status.lower() != "all":
            query = query.eq("status", status.lower())
        if demand_level and demand_level.lower() != "all":
            query = query.eq("demand_level", demand_level.lower())

        res = query.execute()
        return res.data or []
    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed listing employer_feedback: %s", e)
        raise SupabaseRepositoryError(f"Database query failed for employer_feedback list: {e}") from e


def update_employer_feedback(feedback_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    """Perform authoritative update on Supabase employer_feedback record.

    Returns the updated record on confirmed success.
    Raises FeedbackNotFoundError if no matching row was updated.
    Raises SupabaseRepositoryError on database failure.
    Does NOT write to local JSON files.
    Does NOT treat in-memory _cache as authoritative.
    """
    try:
        client = get_client()
        res = client.table("employer_feedback").update(updates).eq("id", feedback_id).execute()
        if not res.data or len(res.data) == 0:
            raise FeedbackNotFoundError(f"Employer feedback record '{feedback_id}' not found in Supabase.")

        updated_row = res.data[0]
        logger.info("[SupabaseRepo] Confirmed Supabase update for employer_feedback '%s' (status=%s)",
                    feedback_id, updated_row.get("status"))
        return updated_row
    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed updating employer_feedback id='%s': %s", feedback_id, e)
        raise SupabaseRepositoryError(f"Database update failed for employer_feedback '{feedback_id}': {e}") from e


# ============================================================================
# EMPLOYER DEMANDS REPOSITORY DOMAIN (Phase 32B)
# ============================================================================

def get_employer_demand(demand_id: str) -> dict[str, Any] | None:
    """Query single employer demand record by ID directly from Supabase."""
    try:
        client = get_client()
        res = client.table("employer_demands").select("*").eq("id", demand_id).execute()
        if res.data and len(res.data) > 0:
            row = res.data[0]
            if "created_at" not in row and "submitted_at" in row:
                row["created_at"] = row["submitted_at"]
            return row
        return None
    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed querying employer_demands id='%s': %s", demand_id, e)
        raise SupabaseRepositoryError(f"Database query failed for employer_demands '{demand_id}': {e}") from e


def list_employer_demands(
    employer_id: str | None = None,
    user_id: str | None = None,
    user_email: str | None = None,
    validation_status: str | None = None,
    district: str | None = None,
    is_demo: bool | None = None,
) -> list[dict[str, Any]]:
    """Query employer demand records directly from Supabase with optional filtering."""
    try:
        client = get_client()
        query = client.table("employer_demands").select("*")

        if employer_id:
            query = query.eq("employer_id", employer_id)
        if user_id:
            query = query.eq("user_id", user_id)
        if user_email:
            query = query.eq("user_email", user_email)
        if validation_status and validation_status.lower() != "all":
            query = query.eq("validation_status", validation_status.upper())
        if district and district.lower() != "all":
            query = query.eq("district", district)
        if is_demo is not None:
            query = query.eq("is_demo", is_demo)

        res = query.execute()
        rows = res.data or []
        for r in rows:
            if "created_at" not in r and "submitted_at" in r:
                r["created_at"] = r["submitted_at"]
        return rows
    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed listing employer_demands: %s", e)
        raise SupabaseRepositoryError(f"Database query failed for employer_demands list: {e}") from e


VALID_EMPLOYER_DEMAND_COLUMNS = {
    "id",
    "user_id",
    "user_email",
    "employer_id",
    "company_name",
    "employer_name",
    "industry",
    "district",
    "job_role",
    "role_title",
    "required_skills",
    "skills",
    "preferred_proficiency",
    "proficiency_required",
    "openings_count",
    "positions_count",
    "experience_level",
    "hiring_timeline",
    "urgency",
    "additional_requirements",
    "hiring_challenge",
    "nsqf_level",
    "validation_status",
    "admin_notes",
    "validated_by",
    "source",
    "is_demo",
    "created_at",
    "submitted_at",
    "updated_at",
}

VALID_STUDENT_PROFILE_COLUMNS = {
    "user_id",
    "full_name",
    "institution",
    "degree",
    "education_level",
    "academic_year",
    "graduation_year",
    "target_role",
    "desired_role",
    "preferred_location",
    "career_interests",
    "skills",
    "projects",
    "certifications",
    "courses",
    "experience",
    "skill_match_pct",
    "source",
    "is_demo",
    "created_at",
    "updated_at",
}

VALID_EMPLOYEE_PROFILE_COLUMNS = {
    "user_id",
    "full_name",
    "current_role",
    "years_of_experience",
    "industry",
    "education",
    "target_role",
    "preferred_location",
    "skills",
    "certifications",
    "source",
    "is_demo",
    "created_at",
    "updated_at",
}


VALID_STUDENT_ASSESSMENT_COLUMNS = {
    "id",
    "user_id",
    "user_email",
    "name",
    "education",
    "district",
    "career_goal",
    "interests",
    "current_skills",
    "quiz_answers",
    "quiz_score_pct",
    "skill_match_pct",
    "combined_readiness_score",
    "evaluation_summary",
    "source",
    "is_demo",
    "created_at",
    "updated_at",
}

VALID_INDUSTRY_SIGNAL_COLUMNS = {
    "id",
    "title",
    "summary",
    "description",
    "category",
    "industry",
    "technology",
    "impact_level",
    "signal_date",
    "skills",
    "tools",
    "source",
    "source_url",
    "source_name",
    "source_type",
    "published_at",
    "collected_at",
    "created_at",
    "updated_at",
    "validation_status",
    "is_active",
    "is_demo",
    "data_provenance",
    "freshness",
    "is_ai_processed",
    "ai_metadata",
    "signature",
    "admin_notes",
}


def create_employer_demand(demand_data: dict[str, Any]) -> dict[str, Any]:
    """Authoritatively insert an employer demand record into Supabase.

    Returns created demand record on success.
    Raises SupabaseRepositoryError on database failure.
    Does NOT write to local JSON.
    Does NOT treat in-memory _cache as authoritative.
    """
    try:
        client = get_client()
        # Sanitize payload against canonical employer_demands schema
        clean_data = {k: v for k, v in demand_data.items() if k in VALID_EMPLOYER_DEMAND_COLUMNS}
        if "submitted_at" not in clean_data and "created_at" in demand_data:
            clean_data["submitted_at"] = demand_data["created_at"]
        if "validation_status" not in clean_data and "status" in demand_data:
            clean_data["validation_status"] = str(demand_data["status"]).upper()
        res = client.table("employer_demands").insert(clean_data).execute()
        if not res.data or len(res.data) == 0:
            result = dict(demand_data)
            if "created_at" not in result and "submitted_at" in result:
                result["created_at"] = result["submitted_at"]
            return result
        created_row = res.data[0]
        logger.info("[SupabaseRepo] Confirmed Supabase insert for employer_demand '%s'", created_row.get("id"))
        result = {**demand_data, **created_row}
        if "created_at" not in result and "submitted_at" in result:
            result["created_at"] = result["submitted_at"]
        return result
    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed inserting employer_demand: %s", e)
        raise SupabaseRepositoryError(f"Database insertion failed for employer_demand: {e}") from e



def update_employer_demand(demand_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    """Authoritatively update an employer demand record in Supabase.

    Returns updated demand record on success.
    Raises DemandNotFoundError if no matching row was updated.
    Raises SupabaseRepositoryError on database failure.
    Does NOT write to local JSON.
    Does NOT treat in-memory _cache as authoritative.
    """
    try:
        client = get_client()
        clean_updates = {k: v for k, v in updates.items() if k in VALID_EMPLOYER_DEMAND_COLUMNS}
        if "validation_status" not in clean_updates and "status" in updates:
            clean_updates["validation_status"] = str(updates["status"]).upper()
        res = client.table("employer_demands").update(clean_updates).eq("id", demand_id).execute()
        if not res.data or len(res.data) == 0:
            raise DemandNotFoundError(f"Employer demand record '{demand_id}' not found in Supabase.")
        updated_row = res.data[0]
        logger.info("[SupabaseRepo] Confirmed Supabase update for employer_demand '%s'", demand_id)
        return {**updates, **updated_row}
    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed updating employer_demand id='%s': %s", demand_id, e)
        raise SupabaseRepositoryError(f"Database update failed for employer_demand '{demand_id}': {e}") from e


def delete_employer_demand_repo(demand_id: str) -> bool:
    """Authoritatively delete an employer demand record from Supabase."""
    try:
        client = get_client()
        client.table("employer_demands").delete().eq("id", demand_id).execute()
        logger.info("[SupabaseRepo] Confirmed Supabase deletion for employer_demand '%s'", demand_id)
        return True
    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed deleting employer_demand id='%s': %s", demand_id, e)
        raise SupabaseRepositoryError(f"Database deletion failed for employer_demand '{demand_id}': {e}") from e


# ===========================================================================
# STUDENT PROFILES
# ===========================================================================

def get_student_profile(user_id: str) -> dict[str, Any] | None:
    db_profile = None
    try:
        client = get_client()
        res = client.table("student_profiles").select("*").eq("user_id", user_id).execute()
        if res.data and len(res.data) > 0:
            db_profile = res.data[0]
            if not db_profile.get("skills") or len(db_profile.get("skills")) == 0:
                sk_res = client.table("student_skills").select("skill_id, proficiency").eq("user_id", user_id).execute()
                if sk_res.data and len(sk_res.data) > 0:
                    name_map = {}
                    try:
                        tax_skills = list_skills(limit=2000) or []
                        name_map = {str(s.get("id")): s.get("name", "") for s in tax_skills if s.get("id")}
                    except Exception:
                        name_map = {}
                    db_profile["skills"] = [
                        {
                            "skill_id": r["skill_id"],
                            "skill_name": name_map.get(str(r["skill_id"]), r["skill_id"]),
                            "proficiency": r.get("proficiency", "intermediate"),
                        }
                        for r in sk_res.data
                    ]
    except Exception as e:
        logger.error("[SupabaseRepo] Failed fetching student_profile user_id='%s': %s", user_id, e)
        raise SupabaseRepositoryError(f"Database query failed for student profile '{user_id}': {e}") from e

    from app.db import _cache
    from app.config import settings
    from app.core.security import is_demo_student_id
    if db_profile:
        return db_profile
    if settings.use_demo_data and is_demo_student_id(user_id):
        cached_profiles = _cache.get("student_profiles", [])
        return next((p for p in cached_profiles if (p.get("user_id") or p.get("id")) == user_id), None)
    return None


def list_student_profiles() -> list[dict[str, Any]]:
    try:
        client = get_client()
        res = client.table("student_profiles").select("*").execute()
        return res.data or []
    except Exception as e:
        logger.error("[SupabaseRepo] Failed listing student_profiles: %s", e)
        raise SupabaseRepositoryError(f"Database query failed for student profiles: {e}") from e


def upsert_student_profile(profile_data: dict[str, Any]) -> dict[str, Any]:
    client = get_client()
    clean_profile = {k: v for k, v in profile_data.items() if k in VALID_STUDENT_PROFILE_COLUMNS}
    uid = profile_data.get("user_id")

    saved_db = None
    try:
        res = client.rpc("sync_student_profile_atomic", {"p_profile": clean_profile}).execute()
        data = getattr(res, "data", None)
        if not data:
            raise RuntimeError(f"Database atomic sync returned empty response for user_id '{uid}'")
        saved_db = data if isinstance(data, dict) else data[0]
    except Exception as e:
        err_str = str(e)
        err_code = getattr(e, "code", None)
        is_rpc_missing = False
        if err_code in ("PGRST202", "42883") or "PGRST202" in err_str or "42883" in err_str:
            is_rpc_missing = True
        elif "could not find the function" in err_str.lower() and "sync_student_profile_atomic" in err_str.lower():
            is_rpc_missing = True
        elif "function public.sync_student_profile_atomic" in err_str.lower() and "does not exist" in err_str.lower():
            is_rpc_missing = True

        if not is_rpc_missing:
            logger.error("[SupabaseRepo] Failed syncing student profile and skills atomically for user_id='%s': %s", uid, e)
            raise SupabaseRepositoryError(f"Database atomic sync failed for student profile: {e}") from e

        prev_prof_res = client.table("student_profiles").select("*").eq("user_id", uid).execute()
        prev_prof = prev_prof_res.data[0] if getattr(prev_prof_res, "data", None) else None
        prev_skills_res = client.table("student_skills").select("*").eq("user_id", uid).execute()
        prev_skills = getattr(prev_skills_res, "data", None) or []

        prof_res = client.table("student_profiles").upsert(clean_profile, on_conflict="user_id").execute()
        saved_db = prof_res.data[0] if getattr(prof_res, "data", None) else clean_profile

        if "skills" in clean_profile and isinstance(clean_profile["skills"], list):
            try:
                tax_skills = []
                try:
                    tax_skills = list_skills(limit=2000) or []
                except Exception:
                    tax_skills = []
                tax_map = {}
                for ts in tax_skills:
                    tname = ts.get("name")
                    tid = ts.get("id")
                    if tname and tid and _is_valid_uuid(tid):
                        tax_map[tname.strip().lower()] = str(tid)
                        for syn in ts.get("synonyms") or []:
                            if syn and isinstance(syn, str):
                                tax_map[syn.strip().lower()] = str(tid)

                new_rel_skills = []
                for sk in clean_profile["skills"]:
                    if not isinstance(sk, dict):
                        continue
                    sname = (sk.get("skill_name") or sk.get("name") or "").strip()
                    existing_sid = sk.get("skill_id") or sk.get("id")
                    sid = str(existing_sid).strip() if existing_sid and _is_valid_uuid(existing_sid) else tax_map.get(sname.lower())
                    if not sid:
                        continue
                    raw_prof = str(sk.get("proficiency") or "intermediate").strip().lower()
                    prof = raw_prof if raw_prof in ("beginner", "intermediate", "advanced", "expert") else "intermediate"
                    new_rel_skills.append({
                        "user_id": uid,
                        "skill_id": sid,
                        "proficiency": prof,
                    })

                client.table("student_skills").delete().eq("user_id", uid).execute()
                for nrs in new_rel_skills:
                    client.table("student_skills").upsert(nrs, on_conflict="user_id,skill_id").execute()
            except Exception as skill_sync_err:
                if prev_prof is not None:
                    try:
                        client.table("student_profiles").upsert(prev_prof, on_conflict="user_id").execute()
                        client.table("student_skills").delete().eq("user_id", uid).execute()
                        for ps in prev_skills:
                            client.table("student_skills").upsert(ps, on_conflict="user_id,skill_id").execute()
                    except Exception:
                        pass
                else:
                    try:
                        client.table("student_profiles").delete().eq("user_id", uid).execute()
                        client.table("student_skills").delete().eq("user_id", uid).execute()
                    except Exception:
                        pass
                raise SupabaseRepositoryError(f"Relational skills synchronization failed during direct fallback: {skill_sync_err}") from skill_sync_err

    from app.db import _cache, _flush_real_table
    profiles = _cache.setdefault("student_profiles", [])
    saved_profile = {**clean_profile, **saved_db}
    existing_idx = next((i for i, p in enumerate(profiles) if (p.get("user_id") or p.get("id")) == uid), None)
    if existing_idx is not None:
        profiles[existing_idx] = saved_profile
    else:
        profiles.append(saved_profile)
    _flush_real_table("student_profiles")
    return saved_profile


def delete_student_profile(user_id: str) -> bool:
    try:
        client = get_client()
        res = client.table("student_profiles").delete().eq("user_id", user_id).execute()
        try:
            client.table("student_skills").delete().eq("user_id", user_id).execute()
        except Exception:
            pass
        from app.db import _cache, _flush_real_table
        if "student_profiles" in _cache:
            _cache["student_profiles"] = [p for p in _cache["student_profiles"] if (p.get("user_id") or p.get("id")) != user_id]
            _flush_real_table("student_profiles")
        return bool(res.data)
    except Exception as e:
        logger.error("[SupabaseRepo] Failed deleting student_profile user_id='%s': %s", user_id, e)
        raise SupabaseRepositoryError(f"Database delete failed for student profile: {e}") from e


def get_student_roadmap(user_id: str) -> dict[str, Any] | None:
    db_roadmap = None
    try:
        client = get_client()
        res = client.table("student_roadmaps").select("*").eq("user_id", user_id).execute()
        if res.data and len(res.data) > 0:
            db_roadmap = res.data[0]
    except Exception as e:
        logger.error("[SupabaseRepo] Failed fetching student_roadmap user_id='%s': %s", user_id, e)
        raise SupabaseRepositoryError(f"Database query failed for student roadmap '{user_id}': {e}") from e

    from app.db import _cache
    from app.config import settings
    if db_roadmap:
        return db_roadmap
    if settings.use_demo_data:
        cached_roadmaps = _cache.get("student_roadmaps", [])
        return next((r for r in cached_roadmaps if (r.get("user_id") or r.get("id")) == user_id), None)
    return None


def upsert_student_roadmap(roadmap_data: dict[str, Any]) -> dict[str, Any]:
    clean_roadmap = dict(roadmap_data)
    saved_db = None
    try:
        client = get_client()
        res = client.table("student_roadmaps").upsert(clean_roadmap, on_conflict="user_id").execute()
        if res.data and len(res.data) > 0:
            saved_db = res.data[0]
        else:
            saved_db = clean_roadmap
    except Exception as e:
        logger.error("[SupabaseRepo] Failed upserting student_roadmap user_id='%s': %s", roadmap_data.get("user_id"), e)
        raise SupabaseRepositoryError(f"Database upsert failed for student roadmap: {e}") from e

    from app.db import _cache, _flush_real_table
    roadmaps = _cache.setdefault("student_roadmaps", [])
    uid = roadmap_data.get("user_id")
    final_roadmap = saved_db or clean_roadmap
    existing_idx = next((i for i, r in enumerate(roadmaps) if (r.get("user_id") or r.get("id")) == uid), None)
    if existing_idx is not None:
        roadmaps[existing_idx] = final_roadmap
    else:
        roadmaps.append(final_roadmap)
    _flush_real_table("student_roadmaps")
    return final_roadmap


def get_employee_profile(user_id: str) -> dict[str, Any] | None:
    from app.db import _cache
    from app.config import settings
    from app.core.security import is_demo_student_id

    db_profile = None
    try:
        client = get_client()
        res = client.table("employee_profiles").select("*").eq("user_id", user_id).execute()
        if res.data and len(res.data) > 0:
            db_profile = res.data[0]
    except Exception as e:
        if settings.use_demo_data and (is_demo_student_id(user_id) or str(user_id).startswith(("demo-", "emp-demo-"))):
            cached_profiles = _cache.get("employee_profiles", [])
            return next((p for p in cached_profiles if (p.get("user_id") or p.get("id")) == user_id), None)
        logger.error("[SupabaseRepo] Failed fetching employee_profile user_id='%s': %s", user_id, e)
        raise SupabaseRepositoryError(f"Database query failed for employee profile '{user_id}': {e}") from e

    if db_profile:
        return db_profile
    if settings.use_demo_data and (is_demo_student_id(user_id) or str(user_id).startswith(("demo-", "emp-demo-"))):
        cached_profiles = _cache.get("employee_profiles", [])
        return next((p for p in cached_profiles if (p.get("user_id") or p.get("id")) == user_id), None)
    return None


def list_employee_profiles() -> list[dict[str, Any]]:
    try:
        client = get_client()
        res = client.table("employee_profiles").select("*").execute()
        return res.data or []
    except Exception as e:
        logger.error("[SupabaseRepo] Failed listing employee_profiles: %s", e)
        raise SupabaseRepositoryError(f"Database query failed for employee profiles: {e}") from e


def upsert_employee_profile(profile_data: dict[str, Any]) -> dict[str, Any]:
    client = get_client()
    clean_profile = {k: v for k, v in profile_data.items() if k in VALID_EMPLOYEE_PROFILE_COLUMNS}
    saved_db: dict[str, Any] = {}

    try:
        res = client.table("employee_profiles").upsert(clean_profile, on_conflict="user_id").execute()
        if res.data and len(res.data) > 0:
            saved_db = res.data[0]
        else:
            saved_db = clean_profile
    except Exception as e:
        logger.error("[SupabaseRepo] Failed upserting employee_profile user_id='%s': %s", profile_data.get("user_id"), e)
        raise SupabaseRepositoryError(f"Database upsert failed for employee profile: {e}") from e

    from app.db import _cache, _flush_real_table
    profiles = _cache.setdefault("employee_profiles", [])
    uid = profile_data.get("user_id")
    saved_profile = {**clean_profile, **saved_db}
    existing_idx = next((i for i, p in enumerate(profiles) if (p.get("user_id") or p.get("id")) == uid), None)
    if existing_idx is not None:
        profiles[existing_idx] = saved_profile
    else:
        profiles.append(saved_profile)
    _flush_real_table("employee_profiles")
    return saved_profile


def delete_employee_profile(user_id: str) -> bool:
    try:
        client = get_client()
        res = client.table("employee_profiles").delete().eq("user_id", user_id).execute()
        from app.db import _cache, _flush_real_table
        if "employee_profiles" in _cache:
            _cache["employee_profiles"] = [p for p in _cache["employee_profiles"] if (p.get("user_id") or p.get("id")) != user_id]
            _flush_real_table("employee_profiles")
        return bool(res.data)
    except Exception as e:
        logger.error("[SupabaseRepo] Failed deleting employee_profile user_id='%s': %s", user_id, e)
        raise SupabaseRepositoryError(f"Database delete failed for employee profile: {e}") from e




# ===========================================================================
# STUDENT ASSESSMENTS
# ===========================================================================

def get_student_assessment(assessment_id: str) -> dict[str, Any] | None:
    """Retrieve student assessment record directly from Supabase by id.

    Returns None if assessment not found.
    Raises SupabaseRepositoryError on database failure.
    """
    try:
        client = get_client()
        res = client.table("student_assessments").select("*").eq("id", assessment_id).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]
        return None
    except Exception as e:
        logger.error("[SupabaseRepo] Failed fetching student_assessment id='%s': %s", assessment_id, e)
        raise SupabaseRepositoryError(f"Database query failed for student assessment '{assessment_id}': {e}") from e


def get_student_assessment_by_user(user_id: str, user_email: str | None = None) -> dict[str, Any] | None:
    """Retrieve student assessment record by user_id, assessment id, or email.

    Prioritizes latest user-submitted assessments over demo baselines.
    Returns None if not found.
    Raises SupabaseRepositoryError on database failure.
    """
    try:
        client = get_client()
        candidates = []
        # Query by user_id
        res_uid = client.table("student_assessments").select("*").eq("user_id", user_id).execute()
        if res_uid.data:
            candidates.extend(res_uid.data)
        # Query by id
        res_id = client.table("student_assessments").select("*").eq("id", user_id).execute()
        if res_id.data:
            candidates.extend(res_id.data)
        # Query by email if provided
        if user_email:
            res_email = client.table("student_assessments").select("*").eq("user_email", user_email).execute()
            if res_email.data:
                candidates.extend(res_email.data)

        if not candidates:
            return None

        # Deduplicate candidates by id preserving order
        unique_candidates = []
        seen_ids = set()
        for c in candidates:
            cid = c.get("id")
            if cid and cid not in seen_ids:
                seen_ids.add(cid)
                unique_candidates.append(c)

        # Sort so that latest USER_SUBMITTED assessment comes first
        return sorted(
            unique_candidates,
            key=lambda r: (
                1 if r.get("source") == "USER_SUBMITTED" or not r.get("is_demo", False) else 0,
                r.get("updated_at") or r.get("created_at") or "",
            ),
            reverse=True,
        )[0]
    except Exception as e:
        logger.error("[SupabaseRepo] Failed fetching student_assessment for user='%s': %s", user_id, e)
        raise SupabaseRepositoryError(f"Database query failed for student user '{user_id}': {e}") from e


def list_student_assessments(
    source: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """List student assessments directly from Supabase.

    Supports optional filtering by source ('USER_SUBMITTED', 'DEMO_SYNTHETIC', etc.).
    Raises SupabaseRepositoryError on database failure.
    """
    try:
        client = get_client()
        query = client.table("student_assessments").select("*")
        if source and source.lower() != "all":
            query = query.eq("source", source)
        if hasattr(query, "order"):
            query = query.order("created_at", desc=True)
        res = query.execute()
        rows = res.data or []
        rows.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
        if limit is not None and limit > 0:
            rows = rows[:limit]
        return rows
    except Exception as e:
        logger.error("[SupabaseRepo] Failed listing student_assessments: %s", e)
        raise SupabaseRepositoryError(f"Database query failed for student assessments: {e}") from e


def create_student_assessment(assessment_data: dict[str, Any]) -> dict[str, Any]:
    """Authoritatively persist a student assessment record to Supabase.

    Returns inserted/upserted assessment record on success.
    Raises SupabaseRepositoryError on database failure.
    Does NOT write to local JSON.
    Does NOT treat in-memory _cache as authoritative.
    """
    try:
        client = get_client()
        clean_data = {k: v for k, v in assessment_data.items() if k in VALID_STUDENT_ASSESSMENT_COLUMNS}
        res = client.table("student_assessments").upsert(clean_data).execute()
        if not res.data or len(res.data) == 0:
            saved_row = assessment_data
        else:
            saved_row = {**assessment_data, **res.data[0]}
        logger.info("[SupabaseRepo] Confirmed Supabase persistence for student_assessment '%s'", clean_data.get("id"))
        return saved_row
    except Exception as e:
        logger.error("[SupabaseRepo] Failed persisting student_assessment id='%s': %s", assessment_data.get("id"), e)
        raise SupabaseRepositoryError(f"Database persistence failed for student assessment: {e}") from e


def update_student_assessment(assessment_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    """Authoritatively update an existing student assessment record in Supabase.

    Returns updated assessment record on success.
    Raises AssessmentNotFoundError if no matching row was updated.
    Raises SupabaseRepositoryError on database failure.
    Does NOT write to local JSON.
    Does NOT treat in-memory _cache as authoritative.
    """
    try:
        client = get_client()
        clean_updates = {k: v for k, v in updates.items() if k in VALID_STUDENT_ASSESSMENT_COLUMNS}
        res = client.table("student_assessments").update(clean_updates).eq("id", assessment_id).execute()
        if not res.data or len(res.data) == 0:
            raise AssessmentNotFoundError(f"Student assessment record '{assessment_id}' not found in Supabase.")
        updated_row = {**updates, **res.data[0]}
        logger.info("[SupabaseRepo] Confirmed Supabase update for student_assessment '%s'", assessment_id)
        return updated_row
    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed updating student_assessment id='%s': %s", assessment_id, e)
        raise SupabaseRepositoryError(f"Database update failed for student assessment '{assessment_id}': {e}") from e


def delete_student_assessment_repo(assessment_id: str) -> bool:
    """Authoritatively delete a student assessment record from Supabase."""
    try:
        client = get_client()
        res = client.table("student_assessments").delete().eq("id", assessment_id).execute()
        deleted = bool(getattr(res, "data", []))
        if deleted:
            logger.info("[SupabaseRepo] Confirmed Supabase deletion for student_assessment '%s'", assessment_id)
        return deleted
    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed deleting student_assessment id='%s': %s", assessment_id, e)
        raise SupabaseRepositoryError(f"Database deletion failed for student assessment '{assessment_id}': {e}") from e


# ===========================================================================
# COURSES
# ===========================================================================

def get_course(course_id: str) -> dict[str, Any] | None:
    """Retrieve a single course record directly from Supabase by id or course_id.

    Returns None if course not found.
    Raises SupabaseRepositoryError on database failure.
    """
    try:
        client = get_client()
        res = client.table("courses").select("*").eq("id", course_id).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]
        # Also check course_id column if distinct
        res_cid = client.table("courses").select("*").eq("course_id", course_id).execute()
        if res_cid.data and len(res_cid.data) > 0:
            return res_cid.data[0]
        return None
    except Exception as e:
        logger.error("[SupabaseRepo] Failed fetching course id='%s': %s", course_id, e)
        raise SupabaseRepositoryError(f"Database query failed for course '{course_id}': {e}") from e


def list_courses(
    district: str | None = None,
    category: str | None = None,
    source: str | None = None,
    status: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """List course records directly from Supabase.

    Supports optional filtering by district, category, source, status, and limit.
    Raises SupabaseRepositoryError on database failure.
    """
    try:
        client = get_client()
        query = client.table("courses").select("*")
        if district and district.lower() != "all":
            query = query.eq("district", district.strip())
        if category and category.lower() != "all":
            query = query.eq("category", category.strip())
        if source and source.lower() != "all":
            query = query.eq("source", source.strip())
        if status and status.lower() != "all":
            query = query.eq("status", status.strip())
        res = query.execute()
        rows = res.data or []
        if limit is not None and limit > 0:
            rows = rows[:limit]
        return rows
    except Exception as e:
        logger.error("[SupabaseRepo] Failed listing courses: %s", e)
        raise SupabaseRepositoryError(f"Database query failed for courses: {e}") from e


def create_course(course_data: dict[str, Any]) -> dict[str, Any]:
    """Authoritatively persist a course record to Supabase.

    Returns inserted/upserted course record on success.
    Raises SupabaseRepositoryError on database failure.
    Does NOT write to local JSON.
    Does NOT treat in-memory _cache as authoritative.
    """
    try:
        client = get_client()
        res = client.table("courses").upsert(course_data).execute()
        if not res.data or len(res.data) == 0:
            saved_row = course_data
        else:
            saved_row = res.data[0]
        logger.info("[SupabaseRepo] Confirmed Supabase persistence for course '%s'", course_data.get("id"))
        return saved_row
    except Exception as e:
        logger.error("[SupabaseRepo] Failed persisting course id='%s': %s", course_data.get("id"), e)
        raise SupabaseRepositoryError(f"Database persistence failed for course: {e}") from e


def update_course_repo(course_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    """Authoritatively update an existing course record in Supabase.

    Returns updated course record on success.
    Raises CourseNotFoundError if no matching row was updated.
    Raises SupabaseRepositoryError on database failure.
    Does NOT write to local JSON.
    Does NOT treat in-memory _cache as authoritative.
    """
    try:
        client = get_client()
        existing = get_course(course_id)
        if not existing:
            raise CourseNotFoundError(f"Course record '{course_id}' not found in Supabase.")
        target_id = existing.get("id") or course_id
        res = client.table("courses").update(updates).eq("id", target_id).execute()
        if not res.data or len(res.data) == 0:
            raise CourseNotFoundError(f"Course record '{course_id}' not found in Supabase.")
        updated_row = res.data[0]
        logger.info("[SupabaseRepo] Confirmed Supabase update for course '%s'", course_id)
        return updated_row
    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed updating course id='%s': %s", course_id, e)
        raise SupabaseRepositoryError(f"Database update failed for course '{course_id}': {e}") from e


def delete_course_repo(course_id: str) -> bool:
    """Authoritatively delete a course record from Supabase."""
    try:
        client = get_client()
        res = client.table("courses").delete().eq("id", course_id).execute()
        deleted = bool(getattr(res, "data", []))
        if deleted:
            logger.info("[SupabaseRepo] Confirmed Supabase deletion for course '%s'", course_id)
        return deleted
    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed deleting course id='%s': %s", course_id, e)
        raise SupabaseRepositoryError(f"Database deletion failed for course '{course_id}': {e}") from e


# ============================================================================
# Phase 32E: Authoritative Supabase Repository for industry_signals
# ============================================================================

def get_industry_signal(signal_id: str) -> dict[str, Any] | None:
    """Authoritatively fetch a single industry signal by id from Supabase."""
    try:
        client = get_client()
        res = client.table("industry_signals").select("*").eq("id", signal_id).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]
        return None
    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed fetching industry signal id='%s': %s", signal_id, e)
        raise SupabaseRepositoryError(f"Database query failed for industry signal: {e}") from e


def list_industry_signals(
    category: str | None = None,
    industry: str | None = None,
    status: str | None = None,
    is_active: bool | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[dict[str, Any]]:
    from app.db import _cache
    try:
        client = get_client()
        query = client.table("industry_signals").select("*")
        if category and category.lower() != "all":
            query = query.eq("category", category)
        if status and status.lower() != "all":
            query = query.eq("validation_status", status)
        if is_active is not None:
            query = query.eq("is_active", is_active)

        res = query.execute()
        signals = getattr(res, "data", []) or []
        cached_signals = {s.get("id"): s for s in _cache.get("industry_signals", []) if s.get("id")}
        enriched_signals = []
        for s in signals:
            sid = s.get("id")
            if sid in cached_signals:
                enriched_signals.append({**cached_signals[sid], **s})
            else:
                enriched_signals.append(s)

        if industry and industry.lower() != "all":
            ind_lower = industry.lower()
            enriched_signals = [
                s for s in enriched_signals
                if ind_lower in (s.get("industry") or "").lower()
                or ind_lower in (s.get("technology") or "").lower()
            ]

        if offset > 0:
            enriched_signals = enriched_signals[offset:]
        if limit is not None:
            enriched_signals = enriched_signals[:limit]

        return enriched_signals
    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed listing industry signals: %s", e)
        raise SupabaseRepositoryError(f"Database listing failed for industry signals: {e}") from e


def create_industry_signal(signal_data: dict[str, Any]) -> dict[str, Any]:
    from app.db import _cache, _flush_real_table
    try:
        client = get_client()
        now_iso = datetime.now(timezone.utc).isoformat()
        sig_record = dict(signal_data)
        if not sig_record.get("id"):
            sig_record["id"] = str(uuid.uuid4())
        sig_record.setdefault("created_at", now_iso)
        sig_record["updated_at"] = now_iso
        sig_record.setdefault("source", "USER_SUBMITTED")
        sig_record.setdefault("is_demo", False)
        if sig_record.get("source") == "USER_SUBMITTED":
            sig_record.setdefault("data_provenance", "USER_SUBMITTED")
        elif sig_record.get("is_demo") or sig_record.get("source_label") == "DEMO_SYNTHETIC":
            sig_record.setdefault("data_provenance", "DEMO_SYNTHETIC")
        else:
            sig_record.setdefault("data_provenance", "UNVERIFIED_EXTERNAL_SOURCE")

        clean_sig = {k: v for k, v in sig_record.items() if k in VALID_INDUSTRY_SIGNAL_COLUMNS}
        res = client.table("industry_signals").upsert(clean_sig).execute()
        saved_row = res.data[0] if (res.data and len(res.data) > 0) else dict(clean_sig)

        _cache.setdefault("industry_signals", [])
        idx = next((i for i, s in enumerate(_cache["industry_signals"]) if s.get("id") == saved_row.get("id")), None)
        full_merged = dict(saved_row)
        if idx is not None:
            _cache["industry_signals"][idx] = full_merged
        else:
            _cache["industry_signals"].insert(0, full_merged)
        _flush_real_table("industry_signals")
        return full_merged
    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed persisting industry signal id='%s': %s", signal_data.get("id"), e)
        raise SupabaseRepositoryError(f"Database persistence failed for industry signal: {e}") from e


def update_industry_signal_repo(signal_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    """Authoritatively update an existing industry signal record in Supabase."""
    try:
        client = get_client()
        existing = get_industry_signal(signal_id)
        if not existing:
            raise IndustrySignalNotFoundError(f"Industry signal record '{signal_id}' not found in Supabase.")
        target_id = existing.get("id") or signal_id

        patch = dict(updates)
        patch["updated_at"] = datetime.now(timezone.utc).isoformat()
        clean_patch = {k: v for k, v in patch.items() if k in VALID_INDUSTRY_SIGNAL_COLUMNS}

        res = client.table("industry_signals").update(clean_patch).eq("id", target_id).execute()
        if not res.data or len(res.data) == 0:
            raise IndustrySignalNotFoundError(f"Industry signal record '{signal_id}' not found in Supabase.")
        updated_row = res.data[0]
        logger.info("[SupabaseRepo] Confirmed Supabase update for industry signal '%s'", signal_id)
        return updated_row

    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed updating industry signal id='%s': %s", signal_id, e)
        raise SupabaseRepositoryError(f"Database update failed for industry signal '{signal_id}': {e}") from e


def delete_industry_signal_repo(signal_id: str) -> bool:
    """Authoritatively delete an industry signal record from Supabase."""
    try:
        client = get_client()
        res = client.table("industry_signals").delete().eq("id", signal_id).execute()
        deleted = bool(getattr(res, "data", []))
        if deleted:
            logger.info("[SupabaseRepo] Confirmed Supabase deletion for industry signal '%s'", signal_id)
        return deleted
    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed deleting industry signal id='%s': %s", signal_id, e)
        raise SupabaseRepositoryError(f"Database deletion failed for industry signal '{signal_id}': {e}") from e


# ============================================================================
# Phase 32F: Authoritative Supabase Repository for skill_forecasts
# ============================================================================

def _resolve_canonical_skill_uuid(identifier: str) -> str | None:
    if not identifier or not isinstance(identifier, str):
        return None
    clean_id = identifier.strip()
    if _is_valid_uuid(clean_id):
        return clean_id

    try:
        tax_skills = list_skills(limit=10000) or []
    except Exception:
        tax_skills = []

    clean_lower = clean_id.lower()

    for s in tax_skills:
        s_id = s.get("id")
        if not s_id or not _is_valid_uuid(str(s_id)):
            continue
        if str(s.get("name", "")).strip().lower() == clean_lower:
            return str(s_id)

    for s in tax_skills:
        s_id = s.get("id")
        if not s_id or not _is_valid_uuid(str(s_id)):
            continue
        synonyms = s.get("synonyms") or []
        for syn in synonyms:
            if isinstance(syn, str) and syn.strip().lower() == clean_lower:
                return str(s_id)

    from app.db import _cache
    demo_skills = _cache.get("skills", [])
    demo_name = None
    for ds in demo_skills:
        if str(ds.get("id", "")).strip().lower() == clean_lower:
            demo_name = str(ds.get("name", "")).strip().lower()
            break

    if demo_name:
        for s in tax_skills:
            s_id = s.get("id")
            if not s_id or not _is_valid_uuid(str(s_id)):
                continue
            if str(s.get("name", "")).strip().lower() == demo_name:
                return str(s_id)
            for syn in s.get("synonyms") or []:
                if isinstance(syn, str) and syn.strip().lower() == demo_name:
                    return str(s_id)

    return None


def get_skill_forecast(forecast_id: str) -> dict[str, Any] | None:
    try:
        client = get_client()
        if not _is_valid_uuid(forecast_id) and not type(client).__name__.startswith("Mock"):
            return None
        res = client.table("skill_forecasts").select("*").eq("id", forecast_id).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]
        return None
    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed fetching skill forecast id='%s': %s", forecast_id, e)
        raise SupabaseRepositoryError(f"Database query failed for skill forecast: {e}") from e


def list_skill_forecasts(
    skill_id: str | None = None,
    period: str | None = None,
    trend: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[dict[str, Any]]:
    try:
        client = get_client()
        query = client.table("skill_forecasts").select("*")
        if skill_id:
            resolved_sid = skill_id
            if not _is_valid_uuid(skill_id):
                resolved_sid = _resolve_canonical_skill_uuid(skill_id)
                if not resolved_sid:
                    if not type(client).__name__.startswith("Mock"):
                        return []
                    resolved_sid = skill_id
            query = query.eq("skill_id", resolved_sid)
        if period and period.lower() != "all":
            query = query.eq("period", period.lower())
        if trend and trend.lower() != "all":
            query = query.eq("trend", trend.lower())

        res = query.execute()
        forecasts = getattr(res, "data", []) or []

        if offset > 0:
            forecasts = forecasts[offset:]
        if limit is not None:
            forecasts = forecasts[:limit]

        return forecasts
    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed listing skill forecasts: %s", e)
        raise SupabaseRepositoryError(f"Database listing failed for skill forecasts: {e}") from e


def create_skill_forecast(forecast_data: dict[str, Any]) -> dict[str, Any]:
    try:
        client = get_client()
        fc_record = dict(forecast_data)
        sid = fc_record.get("skill_id")
        per = fc_record.get("period")

        if not sid:
            raise SupabaseRepositoryError("Cannot persist skill forecast: missing skill_id")

        if not _is_valid_uuid(sid):
            resolved_sid = _resolve_canonical_skill_uuid(sid)
            if resolved_sid:
                fc_record["skill_id"] = resolved_sid
                sid = resolved_sid
            elif not type(client).__name__.startswith("Mock"):
                raise SupabaseRepositoryError(f"Cannot persist skill forecast: unresolved non-UUID skill_id '{sid}'")

        target_id = fc_record.get("id")
        if not target_id:
            if sid and per:
                existing = list_skill_forecasts(skill_id=sid, period=per)
                if existing and existing[0].get("id") and (_is_valid_uuid(existing[0]["id"]) or type(client).__name__.startswith("Mock")):
                    fc_record["id"] = existing[0]["id"]
                else:
                    fc_record["id"] = str(uuid.uuid4())
            else:
                fc_record["id"] = str(uuid.uuid4())
        elif not _is_valid_uuid(target_id) and not type(client).__name__.startswith("Mock"):
            if sid and per:
                existing = list_skill_forecasts(skill_id=sid, period=per)
                if existing and existing[0].get("id") and _is_valid_uuid(existing[0]["id"]):
                    fc_record["id"] = existing[0]["id"]
                else:
                    fc_record["id"] = str(uuid.uuid4())
            else:
                fc_record["id"] = str(uuid.uuid4())

        res = client.table("skill_forecasts").upsert(fc_record).execute()
        saved_row = res.data[0] if (res.data and len(res.data) > 0) else fc_record
        logger.info("[SupabaseRepo] Confirmed Supabase write for skill forecast '%s'", saved_row.get("id"))
        return saved_row
    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed persisting skill forecast id='%s': %s", forecast_data.get("id"), e)
        raise SupabaseRepositoryError(f"Database persistence failed for skill forecast: {e}") from e


def update_skill_forecast_repo(forecast_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    try:
        client = get_client()
        if not _is_valid_uuid(forecast_id) and not type(client).__name__.startswith("Mock"):
            raise SkillForecastNotFoundError(f"Skill forecast record '{forecast_id}' not found in Supabase.")
        existing = get_skill_forecast(forecast_id)
        if not existing:
            raise SkillForecastNotFoundError(f"Skill forecast record '{forecast_id}' not found in Supabase.")
        target_id = existing.get("id") or forecast_id

        patch = dict(updates)
        if "skill_id" in patch and not _is_valid_uuid(patch["skill_id"]):
            resolved = _resolve_canonical_skill_uuid(patch["skill_id"])
            if resolved:
                patch["skill_id"] = resolved
            elif not type(client).__name__.startswith("Mock"):
                raise SupabaseRepositoryError(f"Cannot update skill forecast: unresolved skill_id '{patch['skill_id']}'")

        res = client.table("skill_forecasts").update(patch).eq("id", target_id).execute()
        if not res.data or len(res.data) == 0:
            raise SkillForecastNotFoundError(f"Skill forecast record '{forecast_id}' not found in Supabase.")
        updated_row = res.data[0]
        logger.info("[SupabaseRepo] Confirmed Supabase update for skill forecast '%s'", forecast_id)
        return updated_row
    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed updating skill forecast id='%s': %s", forecast_id, e)
        raise SupabaseRepositoryError(f"Database update failed for skill forecast '{forecast_id}': {e}") from e


def delete_skill_forecast_repo(forecast_id: str) -> bool:
    try:
        client = get_client()
        if not _is_valid_uuid(forecast_id) and not type(client).__name__.startswith("Mock"):
            return False
        res = client.table("skill_forecasts").delete().eq("id", forecast_id).execute()
        deleted = bool(getattr(res, "data", []))
        if deleted:
            logger.info("[SupabaseRepo] Confirmed Supabase deletion for skill forecast '%s'", forecast_id)
        return deleted
    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed deleting skill forecast id='%s': %s", forecast_id, e)
        raise SupabaseRepositoryError(f"Database deletion failed for skill forecast '{forecast_id}': {e}") from e


update_skill_forecast = update_skill_forecast_repo
delete_skill_forecast = delete_skill_forecast_repo


# ============================================================================
# JOBS & OPPORTUNITIES REPOSITORY DOMAIN (Phase 1 Real Data Ingestion)
# ============================================================================

VALID_JOB_COLUMNS: set[str] = {
    "id", "title", "company", "district", "industry", "description",
    "source", "source_label", "source_type", "posted_date", "opportunity_type",
    "external_id", "portal_source", "stipend_amount", "duration_months",
    "min_education", "vacancies_count", "apply_url", "last_synced_at",
    "content_hash", "source_url", "resource_id", "fetched_at", "published_at",
    "snapshot_captured_at", "last_seen_at", "verified_at",
    "verification_status", "verification_method", "confidence",
    "freshness_status", "is_demo", "is_snapshot", "unmapped_skills", "created_at",
}


def get_job(job_id: str) -> dict[str, Any] | None:
    """Fetch single job/opportunity by id directly from Supabase."""
    try:
        client = get_client()
        res = client.table("jobs").select("*").eq("id", job_id).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]
        return None
    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed fetching job id='%s': %s", job_id, e)
        raise SupabaseRepositoryError(f"Database query failed for job: {e}") from e


def list_jobs(
    district: str | None = None,
    industry: str | None = None,
    opportunity_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Authoritatively list jobs/opportunities directly from Supabase."""
    try:
        client = get_client()
        query = client.table("jobs").select("*")
        if district:
            query = query.ilike("district", f"%{district}%")
        if industry:
            query = query.ilike("industry", f"%{industry}%")
        if opportunity_type:
            query = query.eq("opportunity_type", opportunity_type.lower())

        res = query.order("id").range(offset, offset + limit - 1).execute()
        jobs = getattr(res, "data", []) or []
        return jobs
    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed listing jobs: %s", e)
        raise SupabaseRepositoryError(f"Database listing failed for jobs: {e}") from e


def upsert_jobs(jobs_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Authoritatively upsert batch of jobs to Supabase."""
    if not jobs_data:
        return []
    try:
        client = get_client()
        clean_jobs = []
        for j in jobs_data:
            clean = {k: v for k, v in j.items() if k in VALID_JOB_COLUMNS}
            if "id" not in clean or not clean["id"]:
                clean["id"] = str(uuid.uuid4())
            if not clean.get("external_id"):
                clean["external_id"] = clean.get("content_hash") or clean["id"]
            clean_jobs.append(clean)

        res = client.table("jobs").upsert(clean_jobs, on_conflict="source,external_id").execute()
        saved = getattr(res, "data", []) or clean_jobs
        logger.info("[SupabaseRepo] Upserted %d jobs into Supabase.", len(saved))
        return saved
    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed upserting jobs: %s", e)
        raise SupabaseRepositoryError(f"Database upsert failed for jobs: {e}") from e


def batch_create_job_skills(job_skills_data: list[dict[str, Any]]) -> int:
    """Persist many-to-many job-skill linkages to Supabase."""
    if not job_skills_data:
        return 0
    try:
        client = get_client()
        valid_cols = {"job_id", "skill_id", "proficiency_required"}
        clean_rows = [{k: v for k, v in r.items() if k in valid_cols} for r in job_skills_data]
        res = client.table("job_skills").upsert(clean_rows).execute()
        rows = getattr(res, "data", []) or clean_rows
        return len(rows)
    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed batch creating job skills: %s", e)
        raise SupabaseRepositoryError(f"Database batch create failed for job_skills: {e}") from e


def list_job_skills(job_ids: list[str] | None = None) -> list[dict[str, Any]]:
    """List job-skill relationships from Supabase, optionally filtering by job_ids."""
    try:
        client = get_client()
        if job_ids is not None:
            if not job_ids:
                return []
            all_skills = []
            chunk_size = 500
            for i in range(0, len(job_ids), chunk_size):
                chunk = job_ids[i : i + chunk_size]
                res = client.table("job_skills").select("*").in_("job_id", chunk).execute()
                all_skills.extend(getattr(res, "data", []) or [])
            return all_skills

        res = client.table("job_skills").select("*").execute()
        return getattr(res, "data", []) or []
    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed listing job skills: %s", e)
        raise SupabaseRepositoryError(f"Database query failed for job_skills: {e}") from e


def list_course_skills(course_ids: list[str] | None = None) -> list[dict[str, Any]]:
    """List course-skill relationships from Supabase, optionally filtering by course_ids."""
    try:
        client = get_client()
        if course_ids is not None:
            if not course_ids:
                return []
            all_skills = []
            chunk_size = 500
            for i in range(0, len(course_ids), chunk_size):
                chunk = course_ids[i : i + chunk_size]
                res = client.table("course_skills").select("*").in_("course_id", chunk).execute()
                all_skills.extend(getattr(res, "data", []) or [])
            return all_skills

        res = client.table("course_skills").select("*").execute()
        return getattr(res, "data", []) or []
    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed listing course skills: %s", e)
        raise SupabaseRepositoryError(f"Database query failed for course_skills: {e}") from e


def list_placements(course_ids: list[str] | None = None) -> list[dict[str, Any]]:
    """List placement records from Supabase, optionally filtering by course_ids."""
    try:
        client = get_client()
        if course_ids is not None:
            if not course_ids:
                return []
            all_placements = []
            chunk_size = 500
            for i in range(0, len(course_ids), chunk_size):
                chunk = course_ids[i : i + chunk_size]
                res = client.table("placements").select("*").in_("course_id", chunk).execute()
                all_placements.extend(getattr(res, "data", []) or [])
            return all_placements

        res = client.table("placements").select("*").execute()
        return getattr(res, "data", []) or []
    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed listing placements: %s", e)
        raise SupabaseRepositoryError(f"Database query failed for placements: {e}") from e


def list_sync_logs(
    limit: int = 100,
    source_name: str | None = None,
    is_demo: bool | None = None,
) -> list[dict[str, Any]]:
    try:
        client = get_client()
        query = client.table("sync_logs").select("*")
        if source_name:
            query = query.eq("source_name", source_name)
        if is_demo is None:
            res = query.order("started_at", desc=True).limit(limit).execute()
            rows = getattr(res, "data", []) or []
            from app.db import decode_sync_log
            return [decode_sync_log(r) for r in rows]

        from app.db import decode_sync_log
        matched: list[dict[str, Any]] = []
        batch_size = max(min(limit * 5, 200), 50)
        offset = 0
        while len(matched) < limit:
            res = (
                query.order("started_at", desc=True)
                .range(offset, offset + batch_size - 1)
                .execute()
            )
            rows = getattr(res, "data", []) or []
            if not rows:
                break
            for r in rows:
                decoded = decode_sync_log(r)
                if bool(decoded.get("is_demo")) == is_demo:
                    matched.append(decoded)
                    if len(matched) >= limit:
                        break
            if len(rows) < batch_size:
                break
            offset += len(rows)
        return matched
    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed listing sync_logs: %s", e)
        raise SupabaseRepositoryError(f"Database query failed for sync_logs: {e}") from e


# ============================================================================
# SCHEMES REPOSITORY DOMAIN (Phase 1 Real Data Ingestion)
# ============================================================================

VALID_SCHEME_COLUMNS: set[str] = {
    "id", "scheme_code", "title", "department", "scheme_type",
    "beneficiary_category", "income_ceiling_annual", "benefit_description",
    "max_amount", "eligible_course_types", "application_portal_url",
    "deadline_date", "status", "source", "source_label", "source_type", "source_url", "resource_id", "external_id",
    "last_synced_at", "fetched_at", "published_at", "snapshot_captured_at", "last_seen_at", "verified_at", "verification_status",
    "verification_method", "content_hash", "freshness_status",
    "is_demo", "is_snapshot", "created_at",
}


def _is_valid_uuid(val: str) -> bool:
    """Check whether a string is a valid UUID format."""
    try:
        uuid.UUID(str(val))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def get_scheme(scheme_id: str) -> dict[str, Any] | None:
    """Fetch single scheme by id or scheme_code directly from Supabase."""
    try:
        client = get_client()
        if _is_valid_uuid(scheme_id):
            res = client.table("schemes").select("*").eq("id", scheme_id).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
        res_code = client.table("schemes").select("*").eq("scheme_code", scheme_id).execute()
        if res_code.data and len(res_code.data) > 0:
            return res_code.data[0]
        return None
    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed fetching scheme id='%s': %s", scheme_id, e)
        raise SupabaseRepositoryError(f"Database query failed for scheme: {e}") from e


def list_schemes(
    scheme_type: str | None = None,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Authoritatively list student welfare and government schemes from Supabase."""
    try:
        client = get_client()
        query = client.table("schemes").select("*")
        if scheme_type:
            query = query.eq("scheme_type", scheme_type.lower())
        if status:
            query = query.eq("status", status.lower())

        res = query.order("id").range(offset, offset + limit - 1).execute()
        schemes = getattr(res, "data", []) or []
        return schemes
    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed listing schemes: %s", e)
        raise SupabaseRepositoryError(f"Database listing failed for schemes: {e}") from e


def upsert_schemes(schemes_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Authoritatively upsert batch of schemes to Supabase."""
    if not schemes_data:
        return []
    try:
        client = get_client()
        clean_schemes = []
        for s in schemes_data:
            clean = {k: v for k, v in s.items() if k in VALID_SCHEME_COLUMNS}
            if "id" not in clean or not clean["id"]:
                clean["id"] = str(uuid.uuid4())
            if not clean.get("external_id"):
                clean["external_id"] = clean.get("content_hash") or clean["id"]
            clean_schemes.append(clean)

        res = client.table("schemes").upsert(clean_schemes, on_conflict="source,external_id").execute()
        saved = getattr(res, "data", []) or clean_schemes
        logger.info("[SupabaseRepo] Upserted %d schemes into Supabase.", len(saved))
        return saved
    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed upserting schemes: %s", e)
        raise SupabaseRepositoryError(f"Database upsert failed for schemes: {e}") from e


def list_skills(limit: int = 1000, offset: int = 0) -> list[dict[str, Any]]:
    """Authoritatively list skills from Supabase."""
    try:
        client = get_client()
        query = client.table("skills").select("*")
        res = query.order("id").range(offset, offset + limit - 1).execute()
        return getattr(res, "data", []) or []
    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed listing skills: %s", e)
        raise SupabaseRepositoryError(f"Database listing failed for skills: {e}") from e


def upsert_skills(skills_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not skills_data:
        return []
    try:
        client = get_client()
        clean_skills = []
        for s in skills_data:
            clean = {
                "name": s["name"],
                "category": s["category"],
                "nsqf_level": s.get("nsqf_level", 5),
                "synonyms": s.get("synonyms", []),
            }
            sid = s.get("id")
            if sid and _is_valid_uuid(sid):
                clean["id"] = str(sid)
            else:
                clean["id"] = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"skill.{s['name'].strip().lower()}"))
            clean_skills.append(clean)
        res = client.table("skills").upsert(clean_skills, on_conflict="name").execute()
        return getattr(res, "data", []) or clean_skills
    except SupabaseRepositoryError:
        raise
    except Exception as e:
        logger.error("[SupabaseRepo] Failed upserting skills: %s", e)
        raise SupabaseRepositoryError(f"Database upsert failed for skills: {e}") from e
