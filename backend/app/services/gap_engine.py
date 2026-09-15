"""Skill Gap Engine — computes demand vs. coverage gaps."""
from collections import Counter
from app.db import get_demo
from app.services.career_recommendation_engine import is_live_employer_demand


def compute_gaps(
    district: str | None = None,
    is_demo: bool | None = None,
    jobs: list[dict] | None = None,
    job_skills: list[dict] | None = None,
    courses: list[dict] | None = None,
    course_skills_data: list[dict] | None = None,
    skills_map: dict[str, dict] | None = None,
    employer_demands: list[dict] | None = None,
) -> list[dict]:
    """Compute skill gaps: demand_score - coverage_score per skill.

    Demand score: % of job postings requiring this skill (0-100).
    Coverage score: weighted average of course coverage × training capacity.
    Gap = demand - coverage. Negative gaps are clamped to 0.
    """
    from app.core.data_mode import is_explicit_demo_mode
    is_demo_mode = is_explicit_demo_mode(is_demo)

    if is_demo_mode:
        jobs = jobs if jobs is not None else get_demo("jobs")
        job_skills = job_skills if job_skills is not None else get_demo("job_skills")
        courses = courses if courses is not None else get_demo("courses")
        course_skills_data = course_skills_data if course_skills_data is not None else get_demo("course_skills")
        skills_map = skills_map if skills_map is not None else {s["id"]: s for s in get_demo("skills")}
        employer_demands = employer_demands if employer_demands is not None else get_demo("employer_demands")
    else:
        if jobs is None or job_skills is None:
            try:
                from app.repositories.supabase_repository import list_jobs, list_job_skills
                jobs = list_jobs(limit=None) or []
                job_ids = {j.get("id") for j in jobs if j.get("id")}
                repo_js = list_job_skills(job_ids=list(job_ids)) if job_ids else []
                job_skills = [js for js in (repo_js or []) if js.get("job_id") in job_ids]
            except Exception:
                jobs = []
                job_skills = []

        if courses is None or course_skills_data is None:
            try:
                from app.repositories.supabase_repository import list_courses, list_course_skills
                courses = list_courses() or []
                c_ids = [c["id"] for c in courses if c.get("id")]
                course_skills_data = list_course_skills(course_ids=c_ids) if c_ids else []
            except Exception:
                courses = []
                course_skills_data = []

        if skills_map is None:
            try:
                from app.repositories.supabase_repository import list_skills
                repo_skills = list_skills(limit=None) or []
                skills_map = {s["id"]: s for s in repo_skills if "id" in s}
            except Exception:
                skills_map = {}

        if employer_demands is None:
            try:
                from app.repositories.supabase_repository import list_employer_demands
                employer_demands = list_employer_demands(is_demo=False) or []
            except Exception:
                employer_demands = []

    if not is_demo_mode and (not jobs or not skills_map):
        return []

    # Filter jobs by district if specified
    if district:
        district_job_ids = {j["id"] for j in jobs if j.get("district", "").lower() == district.lower()}
        filtered_js = [js for js in job_skills if js.get("job_id") in district_job_ids]
        total_jobs = len(district_job_ids) or 1
    else:
        filtered_js = job_skills
        total_jobs = len(jobs) or 1

    # Demand: what % of all job postings require this skill
    demand_counts = Counter(js["skill_id"] for js in filtered_js if js.get("skill_id"))

    skills_by_name = {s["name"].lower(): s["id"] for s in skills_map.values()}
    validated_demands = [
        d for d in employer_demands
        if is_live_employer_demand(d) and (d.get("validation_status") or d.get("status") or "").upper() in ("VALIDATED", "APPROVED")
    ]
    if district:
        validated_demands = [d for d in validated_demands if d.get("district", "").lower() == district.lower()]

    for ed in validated_demands:
        weight = max(1, ed.get("openings_count", ed.get("positions_count", 10)) // 10)
        req_skills = ed.get("required_skills") or ed.get("skills") or []
        for sk in req_skills:
            sk_name = sk if isinstance(sk, str) else sk.get("name", "")
            sid = sk if sk in skills_map else skills_by_name.get(str(sk_name).lower())
            if sid:
                demand_counts[sid] += weight
                total_jobs += weight

    # Coverage: weighted by course enrolment
    # A skill taught in a course with 120 students at level 4/5 is better covered
    # than a skill in a course with 30 students at level 2/5
    courses_to_use = [c for c in courses if c.get("district", "").lower() == district.lower()] if district else courses
    course_enrolment = {c["id"]: (c.get("enrolment_count") or c.get("enrolment_capacity", 60)) for c in courses_to_use}
    total_enrolment = sum(course_enrolment.values()) or 1

    # For each skill: sum(coverage_level/5 * course_enrolment) / total_enrolment
    skill_coverage_weighted = {}
    existing_cs_course_ids = set()
    for cs in course_skills_data:
        cid = cs.get("course_id")
        if cid in course_enrolment:
            existing_cs_course_ids.add(cid)
            sid = cs["skill_id"]
            raw_lvl = cs.get("coverage_level") or cs.get("proficiency_level") or 0
            if isinstance(raw_lvl, (int, float)):
                lvl = float(raw_lvl)
            elif isinstance(raw_lvl, str):
                s_lvl = raw_lvl.strip().lower()
                text_map = {"beginner": 2.0, "intermediate": 3.5, "advanced": 5.0, "expert": 5.0}
                if s_lvl in text_map:
                    lvl = text_map[s_lvl]
                else:
                    try:
                        lvl = float(s_lvl)
                    except ValueError:
                        lvl = 0.0
            else:
                lvl = 0.0
            enrol = course_enrolment.get(cid, 0)
            weighted = (lvl / 5) * enrol
            skill_coverage_weighted[sid] = skill_coverage_weighted.get(sid, 0) + weighted

    # Phase 25: Incorporate first-party user-submitted courses not present in static course_skills
    for c in courses_to_use:
        cid = c.get("id")
        c_skills = c.get("skills") or c.get("skills_taught") or []
        if cid not in existing_cs_course_ids and c_skills:
            enrol = c.get("enrolment_count") or c.get("enrolment_capacity", 60)
            lvl = min(5, max(1, c.get("nsqf_level", 5) - 1))
            for sk in c_skills:
                sk_name = sk if isinstance(sk, str) else sk.get("name", "")
                sid = sk if sk in skills_map else skills_by_name.get(str(sk_name).lower())
                if sid:
                    weighted = (lvl / 5) * enrol
                    skill_coverage_weighted[sid] = skill_coverage_weighted.get(sid, 0) + weighted

    gaps = []
    for sid, count in demand_counts.items():
        skill = skills_map.get(sid, {})
        # Demand: % of jobs needing this skill (cap at 100)
        demand_pct = min(100, round(count / total_jobs * 100))
        # Coverage: weighted training capacity as % of total
        coverage_raw = skill_coverage_weighted.get(sid, 0) / total_enrolment * 100
        coverage_pct = min(100, round(coverage_raw))
        gap_pct = max(0, demand_pct - coverage_pct)

        if gap_pct >= 15:
            priority = "CRITICAL"
        elif gap_pct >= 8:
            priority = "HIGH"
        elif gap_pct >= 3:
            priority = "MEDIUM"
        else:
            priority = "LOW"

        gaps.append({
            "skill_id": sid,
            "skill_name": skill.get("name", "Unknown"),
            "category": skill.get("category", ""),
            "demand_pct": demand_pct,
            "coverage_pct": coverage_pct,
            "gap_pct": gap_pct,
            "priority": priority,
            "demand_count": count,
        })

    gaps.sort(key=lambda x: x["gap_pct"], reverse=True)
    return gaps
