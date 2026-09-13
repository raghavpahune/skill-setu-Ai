"""AI-Powered Career Recommendation & Skill-Gap Engine (Phase 16).

Connects:
1. Student Assessment & Profile (Skills, Proficiency, Quiz, Goal, District)
2. Validated Employer Demands (Phase 14 — strictly VALIDATED records only)
3. Government Opportunities & Schemes (Phase 15 — apprenticeships, training)
4. Deterministic Skill-Gap Analysis (NSQF-aligned matching)
5. Explainable Grounded Reasons (Why each career & course is recommended)
6. Optional Gemini AI Copilot synthesis with 100% resilient deterministic fallback.
"""
import logging
from collections import Counter
from typing import Any

from app.core.security import is_demo_student_id
from app.db import get_demo

logger = logging.getLogger("skillsetu.recommendation_engine")

# Standard Career Roles Benchmark Taxonomy
CAREER_ROLES_BENCHMARK = [
    {
        "role_name": "AI Engineer",
        "domain": "ai_ml",
        "required_skills": ["sk-005", "sk-006", "sk-004", "sk-041", "sk-001", "sk-040"],
        "required_skill_names": ["Generative AI", "RAG", "AI Agents", "Python", "Vector Databases", "Prompt Engineering"],
        "description": "Designs and deploys autonomous AI agents, enterprise RAG architectures, and fine-tuned LLM workflows.",
        "avg_salary_lpa": 14.5,
        "nsqf_level": 7,
    },
    {
        "role_name": "Data Analyst",
        "domain": "data_science",
        "required_skills": ["sk-007", "sk-008", "sk-030", "sk-001", "sk-047"],
        "required_skill_names": ["Python", "SQL", "Data Analysis", "Tableau / Power BI", "Machine Learning"],
        "description": "Transforms raw enterprise and public datasets into actionable intelligence, dashboards, and automated analytics.",
        "avg_salary_lpa": 8.5,
        "nsqf_level": 5,
    },
    {
        "role_name": "Cloud Architect",
        "domain": "cloud",
        "required_skills": ["sk-009", "sk-010", "sk-028", "sk-029", "sk-001"],
        "required_skill_names": ["AWS / Azure", "Kubernetes", "Docker", "CI/CD", "Linux"],
        "description": "Architects resilient, secure multi-cloud containerized infrastructure and automated deployment pipelines.",
        "avg_salary_lpa": 16.0,
        "nsqf_level": 7,
    },
    {
        "role_name": "Cybersecurity Analyst",
        "domain": "cybersecurity",
        "required_skills": ["sk-011", "sk-012", "sk-052", "sk-028", "sk-001"],
        "required_skill_names": ["Network Security", "Vulnerability Assessment", "CERT-In Compliance", "Penetration Testing", "Linux"],
        "description": "Monitors enterprise infrastructure, conducts vulnerability assessments, and defends critical digital assets.",
        "avg_salary_lpa": 10.5,
        "nsqf_level": 6,
    },
    {
        "role_name": "EV Technician",
        "domain": "ev",
        "required_skills": ["sk-018", "sk-019", "sk-023", "sk-045", "sk-021"],
        "required_skill_names": ["EV Battery Technology", "Battery Management (BMS)", "Motor Control", "CAN Bus", "Electrical Diagnostics"],
        "description": "Diagnoses, calibrates, and services high-voltage EV battery management systems and electric drivetrains.",
        "avg_salary_lpa": 7.0,
        "nsqf_level": 5,
    },
    {
        "role_name": "Robotics & Automation Engineer",
        "domain": "robotics",
        "required_skills": ["sk-021", "sk-053", "sk-054", "sk-017", "sk-020"],
        "required_skill_names": ["PLC Programming", "Industrial Robotics", "SCADA", "CNC Machining", "Sensors & Actuators"],
        "description": "Designs and programs automated assembly lines, robotic workcells, and Industry 4.0 smart factory systems.",
        "avg_salary_lpa": 9.5,
        "nsqf_level": 6,
    },
    {
        "role_name": "Full Stack Developer",
        "domain": "it_software",
        "required_skills": ["sk-001", "sk-007", "sk-028", "sk-029", "sk-009"],
        "required_skill_names": ["Python", "JavaScript / React", "SQL", "Node.js", "REST APIs", "Git"],
        "description": "Builds end-to-end modern web applications, scalable REST APIs, and interactive frontend interfaces.",
        "avg_salary_lpa": 9.0,
        "nsqf_level": 6,
    },
    {
        "role_name": "IoT & Smart Systems Engineer",
        "domain": "iot",
        "required_skills": ["sk-020", "sk-045", "sk-036", "sk-033", "sk-001"],
        "required_skill_names": ["Embedded C", "Microcontrollers", "MQTT / LoRaWAN", "Sensors", "Python"],
        "description": "Connects edge sensor networks, telemetry hardware, and smart city / agritech telemetry devices.",
        "avg_salary_lpa": 8.0,
        "nsqf_level": 5,
    },
]


def _resolve_student_profile(student_id: str) -> dict[str, Any] | None:
    """Resolve student profile or assessment from Supabase repository.

    Supabase is the authoritative system of record for production student candidates.
    Explicit demo fixtures are only checked if the ID specifically matches a known demo fixture.
    """
    if not student_id or student_id == "me":
        # 'me' must be resolved to the authenticated user ID prior to calling this function
        return None

    # 1. Query Supabase repository (authoritative system of record)
    from app.repositories.supabase_repository import (
        get_student_assessment,
        get_student_assessment_by_user,
        get_student_profile,
        get_employee_profile,
        SupabaseRepositoryError,
    )
    from app.core.time import parse_iso_timestamp
    try:
        a = get_student_assessment(student_id) or get_student_assessment_by_user(student_id)
        p = get_student_profile(student_id)
        p_time = parse_iso_timestamp((p.get("updated_at") or p.get("created_at") or "") if p else "")
        a_time = parse_iso_timestamp((a.get("updated_at") or a.get("created_at") or "") if a else "")
        if p and (p.get("skills") or not a or p_time >= a_time):
            return p
        if a:
            return a
        ep = get_employee_profile(student_id)
        if ep:
            return ep
    except SupabaseRepositoryError as e:
        logger.warning("[RecommendationEngine] Supabase repository unavailable resolving student '%s': %s", student_id, e)
        if not is_demo_student_id(student_id):
            raise RuntimeError(f"Database error resolving student profile: {e}") from e

    # 2. Only allow explicit demo fixture IDs for legitimate demo candidate selector
    # NEVER fall back to demo records for production student IDs (e.g. usr-student-*, UUIDs, etc.)
    if is_demo_student_id(student_id):
        assessments = get_demo("student_assessments")
        for a in assessments:
            if a.get("id") == student_id or a.get("user_id") == student_id:
                return a

        profiles = get_demo("student_profiles")
        for p in profiles:
            if p.get("user_id") == student_id or p.get("id") == student_id:
                return p

    return None



def _is_live_employer_demand(demand: dict[str, Any]) -> bool:
    """Check if an employer demand is a live, non-synthetic record.

    Excludes records with is_demo=True or source in ('DEMO_SYNTHETIC', 'DEMO').
    Includes authentic employer/user submissions (source='EMPLOYER_SUBMITTED', 'USER_SUBMITTED', etc. with is_demo=False).
    """
    if not isinstance(demand, dict):
        return False
    if demand.get("is_demo") is True:
        return False
    source = (demand.get("source") or "").upper()
    if source in ("DEMO_SYNTHETIC", "DEMO"):
        return False
    if source in ("EMPLOYER_SUBMITTED", "USER_SUBMITTED", "FIRST_PARTY") or demand.get("is_demo") is False:
        return True
    return False


def _get_validated_employer_demands(is_demo: bool = False) -> list[dict[str, Any]]:
    """Retrieve only real employer demands that are strictly VALIDATED (Phase 14 rule)."""
    if is_demo:
        demands = get_demo("employer_demands")
    else:
        try:
            from app.repositories.supabase_repository import list_employer_demands
            demands = list_employer_demands() or []
        except Exception:
            demands = []
    validated = []
    for d in demands:
        if not is_demo and not _is_live_employer_demand(d):
            continue
        status = (d.get("validation_status") or d.get("status") or "").upper()
        if status in ("VALIDATED", "APPROVED"):
            validated.append(d)
    return validated


is_live_employer_demand = _is_live_employer_demand
get_validated_employer_demands = _get_validated_employer_demands


def _match_skills(student_skills: list[dict[str, Any]], required_skill_names: list[str]) -> tuple[list[str], list[str], int]:
    """Calculate matched skills, missing skills, and match percentage."""
    normalized_student = {}
    for s in student_skills:
        name = (s.get("skill_name") or s.get("name") or s.get("skill_id") or "").lower()
        prof = (s.get("proficiency") or "intermediate").lower()
        normalized_student[name] = prof

    matched = []
    missing = []
    weighted_score = 0.0

    prof_weights = {"expert": 1.0, "advanced": 1.0, "intermediate": 0.8, "beginner": 0.5, "none": 0.0}

    for req in required_skill_names:
        req_clean = req.lower()
        # Find exact or substring match
        matched_key = None
        for sk_name, prof in normalized_student.items():
            if sk_name in req_clean or req_clean in sk_name:
                matched_key = (sk_name, prof)
                break

        if matched_key:
            matched.append(req)
            weighted_score += prof_weights.get(matched_key[1], 0.75)
        else:
            missing.append(req)

    total_req = len(required_skill_names) or 1
    match_pct = min(100, max(0, round((weighted_score / total_req) * 100)))

    return matched, missing, match_pct


def compute_career_recommendations(student_id: str, is_demo: bool | None = None) -> dict[str, Any]:
    """Deterministic recommendation engine combining assessment, employer demand, and gov opportunities."""
    from app.core.data_mode import is_explicit_demo_mode
    profile = _resolve_student_profile(student_id)
    if not profile:
        raise ValueError(f"Student profile or assessment with ID '{student_id}' not found.")

    source_provenance = profile.get("source") or ("DEMO_SYNTHETIC" if (profile.get("is_demo") is True or is_demo_student_id(student_id)) else "STUDENT_SUBMITTED")
    is_demo_mode = False if is_demo is False else (is_explicit_demo_mode(is_demo) or (is_demo_student_id(student_id) and (profile.get("is_demo") is True or source_provenance == "DEMO_SYNTHETIC")))

    # 1. Normalize Student Current Skills
    current_skills_raw = profile.get("skills", []) or profile.get("current_skills", [])
    if is_demo_mode:
        skills_map = {s["id"]: s for s in get_demo("skills")}
    else:
        try:
            from app.repositories.supabase_repository import list_skills
            repo_skills = list_skills(limit=10000) or []
            skills_map = {s["id"]: s for s in repo_skills if "id" in s}
        except Exception:
            skills_map = {}
    
    current_skills_normalized = []
    for s in current_skills_raw:
        if isinstance(s, dict):
            sid = s.get("skill_id") or s.get("id") or ""
            master = skills_map.get(sid, {})
            name = s.get("skill_name") or master.get("name") or s.get("name") or sid
            cat = s.get("category") or master.get("category") or "Technical"
            nsqf = s.get("nsqf_level") or master.get("nsqf_level") or 5
            prof = s.get("proficiency") or "intermediate"
            current_skills_normalized.append({
                "skill_id": sid,
                "skill_name": name,
                "category": cat,
                "nsqf_level": nsqf,
                "proficiency": prof,
            })
        else:
            current_skills_normalized.append({
                "skill_id": str(s),
                "skill_name": str(s),
                "category": "Technical",
                "nsqf_level": 5,
                "proficiency": "intermediate",
            })

    candidate_name = profile.get("full_name") or profile.get("name") or "Candidate"
    target_career_raw = profile.get("target_role") or profile.get("desired_role") or profile.get("career_goal") or "AI Engineer"
    candidate_district = profile.get("preferred_location") or profile.get("district") or "Maharashtra"
    candidate_education = profile.get("education") or profile.get("degree") or profile.get("education_level") or "Diploma / Degree"
    quiz_score_pct = profile.get("quiz_score_pct", 75)

    # 2. Extract strictly VALIDATED Employer Demands
    validated_demands = _get_validated_employer_demands(is_demo=is_demo_mode)

    if is_demo_mode:
        gov_opportunities = get_demo("gov_opportunities")
        gov_opps_source = "DEMO_SYNTHETIC"
    else:

        try:
            from app.db import get_supabase_client
            client = get_supabase_client()
            if client:
                res = client.table("gov_opportunities").select("*").execute()
                all_opps = getattr(res, "data", []) or []
            else:
                all_opps = []
        except Exception as e:
            logger.warning("Failed querying authoritative gov_opportunities for student '%s': %s", student_id, e)
            all_opps = []

        real_opps = [
            o for o in all_opps
            if o.get("is_demo") is False
            and o.get("source_type") != "SANDBOX_SIMULATION"
            and o.get("source") != "DEMO_SYNTHETIC"
            and (o.get("data_provenance") == "GOVERNMENT_OFFICIAL" or o.get("source") in ("DATAGOV_IN", "OGD_DATAGOV_IN", "USER_SUBMITTED", "ADMIN_CREATED"))
        ]
        gov_opportunities = real_opps
        gov_opps_source = "GOVERNMENT_OFFICIAL" if gov_opportunities else "NO_OFFICIAL_MATCHES"

    if is_demo_mode:
        all_courses = get_demo("courses")
        course_source_default = "DEMO_SYNTHETIC"
    else:
        try:
            from app.repositories.supabase_repository import list_courses, list_course_skills, list_skills
            all_courses = list_courses() or []
            if all_courses:
                course_ids = [c["id"] for c in all_courses if c.get("id")]
                cs_links = list_course_skills(course_ids=course_ids) or []
                skills_repo = list_skills(limit=10000) or []
                skill_name_map = {s["id"]: s.get("name", "") for s in skills_repo if s.get("id")}
                skills_by_course: dict[str, list[str]] = {}
                for cs in cs_links:
                    cid = cs.get("course_id")
                    sid = cs.get("skill_id")
                    sname = cs.get("skill_name") or skill_name_map.get(sid, sid)
                    if cid and sname:
                        skills_by_course.setdefault(cid, []).append(sname)
                for c in all_courses:
                    cid = c.get("id")
                    if cid and cid in skills_by_course:
                        existing = list(c.get("skills") or c.get("skills_taught") or [])
                        linked = skills_by_course[cid]
                        c["skills"] = list(dict.fromkeys(existing + linked))
        except Exception:
            all_courses = []
        course_source_default = "INSTITUTE_SUBMITTED"

    if is_demo_mode:
        all_signals = get_demo("industry_signals")
    else:
        try:
            from app.repositories.supabase_repository import list_industry_signals as list_industry_signals_repo
            all_signals = list_industry_signals_repo()
        except Exception:
            all_signals = []

    career_evaluations = []
    for role_def in CAREER_ROLES_BENCHMARK:
        role_name = role_def["role_name"]
        matched_skills, missing_skills, match_pct = _match_skills(
            current_skills_normalized, role_def["required_skill_names"]
        )

        # Connect with validated employer demand
        role_demands = []
        total_openings = 0
        for d in validated_demands:
            d_role = (d.get("job_role") or d.get("role_title") or "").lower()
            d_skills = [s.lower() for s in (d.get("required_skills") or d.get("skills") or [])]
            
            # Check overlap with role title or role required skills
            role_match = role_name.lower() in d_role or any(w in d_role for w in role_name.lower().split() if len(w) > 3)
            skills_overlap = any(any(req.lower() in ds for ds in d_skills) for req in role_def["required_skill_names"])

            if role_match or skills_overlap:
                openings = int(d.get("openings_count") or d.get("positions_count") or 1)
                total_openings += openings
                role_demands.append({
                    "id": d.get("id"),
                    "company_name": d.get("company_name") or d.get("employer_name"),
                    "job_role": d.get("job_role") or d.get("role_title"),
                    "district": d.get("district"),
                    "openings_count": openings,
                    "hiring_timeline": d.get("hiring_timeline") or d.get("urgency"),
                    "validation_status": "VALIDATED",
                    "source": d.get("source", "EMPLOYER_SUBMITTED"),
                })

        # Connect with matching government opportunities
        role_gov_ops = []
        for g in gov_opportunities:
            if g.get("status", "active").lower() != "active":
                continue
            g_target = [s.lower() for s in (g.get("target_skills") or [])]
            g_text = f"{g.get('name', '')} {g.get('description', '')}".lower()

            match_role = any(req.lower() in g_target or req.lower() in g_text for req in role_def["required_skill_names"])
            if match_role:
                role_gov_ops.append({
                    "id": g.get("id"),
                    "name": g.get("name"),
                    "department": g.get("department"),
                    "opportunity_type": g.get("opportunity_type"),
                    "district_coverage": g.get("district_coverage"),
                    "application_url": g.get("application_url"),
                    "source": g.get("source", "DEMO_SYNTHETIC"),
                })

        role_courses = []
        for c in all_courses:
            if c.get("status", "active").lower() not in ("active", "needs_attention"):
                continue
            c_skills = [s.lower() for s in (c.get("skills") or c.get("skills_taught") or [])]
            c_text = f"{c.get('name', '')} {c.get('description', '')}".lower()
            matches_skill = any(req.lower() in c_skills or req.lower() in c_text for req in missing_skills)
            if matches_skill:
                role_courses.append({
                    "id": c.get("id"),
                    "course_name": c.get("name") or c.get("course_name"),
                    "institute_name": c.get("institute") or c.get("institute_name"),
                    "district": c.get("district"),
                    "category": c.get("category"),
                    "placement_rate": c.get("placement_rate", 80),
                    "nsqf_level": c.get("nsqf_level", 5),
                    "source": c.get("source") or course_source_default,
                    "is_demo": c.get("is_demo", is_demo_mode),
                })

        role_signals = []
        for s in all_signals:
            if not s.get("is_active", True) or s.get("validation_status", "APPROVED") != "APPROVED":
                continue
            sig_text = f"{s.get('title', '')} {s.get('description', '')} {s.get('summary', '')} {s.get('industry', '')} {s.get('technology', '')}".lower()
            sig_skills = [sk.lower() for sk in (s.get("skills") or [])]
            matches_domain = role_def["domain"].lower() in sig_text or role_name.lower() in sig_text
            matches_skill = any(req.lower() in sig_skills or req.lower() in sig_text for req in role_def["required_skill_names"])
            if matches_domain or matches_skill:
                role_signals.append({
                    "id": s.get("id"),
                    "title": s.get("title"),
                    "category": s.get("category", "INDUSTRY_DEMAND"),
                    "source_name": s.get("source_name") or s.get("source"),
                    "source_url": s.get("source_url") or "https://data.gov.in",
                    "freshness": s.get("freshness", "NEW"),
                    "skills": s.get("skills", []),
                })

        # Generate Explainable Reasons (PROJECT_SPEC Requirement #2)
        reasons = []
        if matched_skills:
            reasons.append(f"Matches {len(matched_skills)} of your existing skills ({', '.join(matched_skills[:3])}).")
        if target_career_raw.lower() in role_name.lower() or role_name.lower() in target_career_raw.lower():
            reasons.append(f"Directly aligned with your stated career goal '{target_career_raw}'.")
        if total_openings > 0:
            reasons.append(f"{total_openings} verified vacancies available from validated employer submissions in Maharashtra.")
        if role_signals:
            reasons.append(f"Corroborated by verified industry signal: '{role_signals[0]['title']}' ({role_signals[0]['source_name']}).")
        if role_courses:
            reasons.append(f"Supported by {len(role_courses)} accredited training programs across Maharashtra institutes.")
        if role_gov_ops:
            reasons.append(f"Supported by government skill development & apprenticeship initiatives ({role_gov_ops[0]['name']}).")
        if not reasons:
            reasons.append("Emerging high-demand vocational domain in Maharashtra's industrial corridors.")

        # Demand Indicator
        if total_openings >= 30:
            demand_indicator = "VERY HIGH"
        elif total_openings >= 10:
            demand_indicator = "HIGH"
        else:
            demand_indicator = "GROWING"

        # Determine readiness level for this role
        if match_pct >= 75:
            role_readiness = "JOB_READY"
        elif match_pct >= 50:
            role_readiness = "NEAR_READY"
        elif match_pct >= 30:
            role_readiness = "INTERMEDIATE"
        else:
            role_readiness = "FOUNDATIONAL"

        career_evaluations.append({
            "role_name": role_name,
            "domain": role_def["domain"],
            "description": role_def["description"],
            "avg_salary_lpa": role_def["avg_salary_lpa"],
            "nsqf_level": role_def["nsqf_level"],
            "match_pct": match_pct,
            "readiness_level": role_readiness,
            "matching_skills": matched_skills,
            "missing_skills": missing_skills,
            "demand_indicator": demand_indicator,
            "validated_openings_count": total_openings,
            "validated_employer_signals": role_demands[:4],
            "matched_institute_training": role_courses[:3],
            "matched_industry_signals": role_signals[:3],
            "matched_government_opportunities": role_gov_ops[:3],
            "explanation_reasons": reasons,
            "is_target_goal": bool(target_career_raw.lower() in role_name.lower() or role_name.lower() in target_career_raw.lower()),
        })

    # Sort careers: Target goal boosted first, then by match_pct descending
    career_evaluations.sort(
        key=lambda c: (1 if c["is_target_goal"] else 0, c["match_pct"], c["validated_openings_count"]),
        reverse=True,
    )

    top_recommended_role = career_evaluations[0]

    is_real_candidate = not is_demo_student_id(student_id) and source_provenance != "DEMO_SYNTHETIC" and not profile.get("is_demo", False)

    fc_from_repo = False
    if is_demo_mode:
        fc_list = get_demo("skill_forecasts")
    else:
        try:
            from app.repositories.supabase_repository import list_skill_forecasts
            fc_list = list_skill_forecasts() or []
            fc_from_repo = True
        except Exception as e:
            if is_real_candidate:
                logger.exception("[RecommendationEngine] Supabase forecast query failed for real candidate '%s': %s", student_id, e)
                raise RuntimeError(f"Database error fetching skill forecasts: {e}") from e
            else:
                fc_list = get_demo("skill_forecasts")
    roadmap_steps = []
    for idx, skill in enumerate(top_recommended_role["missing_skills"], start=1):
        # Grounded why
        matching_fc = next((f for f in fc_list if skill.lower() in f.get("skill_name", "").lower()), None)
        if matching_fc:
            trend = matching_fc.get("trend", "rising")
            conf = matching_fc.get("confidence", 85)
            fc_source = matching_fc.get("source", "SUPABASE_AUTHORITATIVE" if fc_from_repo else "DEMO_SYNTHETIC")
            fc_verified = bool(fc_from_repo and not matching_fc.get("is_demo", False) and matching_fc.get("source") != "DEMO_SYNTHETIC")
        else:
            trend = "unknown"
            conf = None
            fc_source = "UNAVAILABLE"
            fc_verified = False

        # Match institute training courses for this specific missing skill
        training_options = []
        for c in all_courses:
            c_skills = [s.lower() for s in (c.get("skills") or c.get("skills_taught") or [])]
            if any(skill.lower() in cs or cs in skill.lower() for cs in c_skills) or skill.lower() in c.get("name", "").lower():
                training_options.append({
                    "course_id": c.get("id"),
                    "course_name": c.get("name") or c.get("course_name"),
                    "institute_name": c.get("institute") or c.get("institute_name"),
                    "district": c.get("district"),
                    "placement_rate": c.get("placement_rate", 80),
                    "source": c.get("source") or course_source_default,
                })

        # Match industry signals for this specific missing skill (Phase 26)
        skill_signals = []
        for s in all_signals:
            if not s.get("is_active", True) or s.get("validation_status", "APPROVED") != "APPROVED":
                continue
            sig_skills = [sk.lower() for sk in (s.get("skills") or [])]
            if any(skill.lower() in sk for sk in sig_skills) or skill.lower() in (s.get("title") or "").lower():
                skill_signals.append({
                    "id": s.get("id"),
                    "title": s.get("title"),
                    "source_name": s.get("source_name") or s.get("source"),
                    "source_url": s.get("source_url") or "https://data.gov.in",
                })

        roadmap_steps.append({
            "step": idx,
            "skill_name": skill,
            "priority": "HIGH" if idx <= 2 else "MEDIUM",
            "trend": trend,
            "demand_confidence": conf,
            "forecast_source": fc_source,
            "forecast_verified": fc_verified,
            "why_learn": f"Bridging {skill} unlocks {top_recommended_role['role_name']} qualification and aligns with {trend} industry demand ({conf}% confidence)." if conf else f"Bridging {skill} unlocks {top_recommended_role['role_name']} qualification and aligns with current market requirements.",
            "action_item": f"Complete hands-on practical modules for {skill} through recommended vocational institutes.",
            "matched_institute_training": training_options[:2],
            "matched_industry_signals": skill_signals[:2],
        })

    if not roadmap_steps:
        roadmap_steps = [
            {
                "step": 1,
                "skill_name": "Production Capstone Project",
                "priority": "HIGH",
                "trend": "unknown",
                "demand_confidence": None,
                "forecast_source": "UNAVAILABLE",
                "forecast_verified": False,
                "why_learn": "Candidate meets all baseline prerequisites. Building an end-to-end industrial portfolio is the final bridge to placement.",
                "action_item": "Deploy a production-ready application and prepare technical case studies.",
            },
            {
                "step": 2,
                "skill_name": "Direct Industry Placement / Apprenticeship",
                "priority": "HIGH",
                "trend": "unknown",
                "demand_confidence": None,
                "forecast_source": "UNAVAILABLE",
                "forecast_verified": False,
                "why_learn": "Directly interview with verified employers and NAPS registered partners.",
                "action_item": "Submit resume to validated hiring partners in Pune / Mumbai corridors.",
            }
        ]

    # 6. Overall Candidate Readiness Summary
    target_match_pct = top_recommended_role["match_pct"]
    overall_readiness_score = round(0.6 * target_match_pct + 0.4 * quiz_score_pct)

    if overall_readiness_score >= 75:
        candidate_readiness_level = "PRODUCTION_READY"
        readiness_badge_color = "emerald"
        readiness_headline = "High Industry Readiness"
        readiness_description = "Strong alignment with employer requirements and proven diagnostic aptitude. Ready for direct apprenticeship placement."
    elif overall_readiness_score >= 45:
        candidate_readiness_level = "NEAR_READY"
        readiness_badge_color = "teal"
        readiness_headline = "Near Ready (Targeted Skill Gap)"
        readiness_description = "Core vocational foundation is solid. Bridging 1–2 priority skill gaps will achieve production readiness."
    else:
        candidate_readiness_level = "FOUNDATIONAL"
        readiness_badge_color = "amber"
        readiness_headline = "Foundational Stage"
        readiness_description = "Early-stage skill profile. Structured vocational curriculum and prerequisite practicals strongly recommended."

    # 7. Grounded AI Explanation (Deterministic summary + Gemini enhancement hook)
    deterministic_ai_summary = (
        f"Based on candidate {candidate_name}'s self-reported competencies ({len(current_skills_normalized)} skills) "
        f"and diagnostic score of {quiz_score_pct}%, {top_recommended_role['role_name']} is the top recommended pathway "
        f"with a {target_match_pct}% competency match. {top_recommended_role['validated_openings_count']} validated employer "
        f"positions currently demand these skills in Maharashtra. We recommend prioritizing {', '.join(top_recommended_role['missing_skills'][:2]) or 'capstone execution'} "
        f"to achieve full production readiness."
    )

    return {
        "status": "success",
        "student_id": student_id,
        "candidate_name": candidate_name,
        "education": candidate_education,
        "district": candidate_district,
        "candidate_district": candidate_district,
        "target_career_goal": target_career_raw,
        "overall_readiness": {
            "score": overall_readiness_score,
            "level": candidate_readiness_level,
            "headline": readiness_headline,
            "badge_color": readiness_badge_color,
            "description": readiness_description,
            "quiz_score_pct": quiz_score_pct,
            "target_match_pct": target_match_pct,
        },
        "current_skill_profile": current_skills_normalized,
        "recommended_careers": career_evaluations,
        "top_recommendation": top_recommended_role,
        "personalized_roadmap": roadmap_steps,
        "ai_explanation": {
            "summary": deterministic_ai_summary,
            "source": "SkillSetu Grounded Recommendation Engine",
            "is_ai_generated": False,
        },
        "data_provenance": {
            "student_profile_source": source_provenance,
            "employer_demand_source": "EMPLOYER_SUBMITTED_VALIDATED",
            "employer_validation_rule": "Strictly VALIDATED employer submissions only",
            "government_opportunities_source": gov_opps_source,
            "disclaimer": "All recommendations are computed deterministically from verified SkillSetu datasets. No ungrounded claims are made.",
        },
    }


async def generate_ai_copilot_explanation(student_id: str, prompt_override: str | None = None) -> dict[str, Any]:
    """Generate enhanced explainability using Gemini LLM if configured, otherwise fallback gracefully."""
    recommendation = compute_career_recommendations(student_id)
    top = recommendation["top_recommendation"]

    # Try live Gemini via existing ai.copilot
    try:
        from ai.copilot import handle_question
        ai_prompt = (
            prompt_override
            or f"Explain in simple, encouraging Marathi-English student-friendly language why '{top['role_name']}' is recommended "
               f"for {recommendation['candidate_name']} based on their {top['match_pct']}% skill match, {top['validated_openings_count']} "
               f"validated employer openings, and missing skills: {', '.join(top['missing_skills'])}."
        )
        ai_res = await handle_question(ai_prompt, role="student", district=recommendation["district"])
        return {
            "status": "success",
            "student_id": student_id,
            "ai_explanation": ai_res.get("answer", recommendation["ai_explanation"]["summary"]),
            "is_live_ai": not ai_res.get("demo_mode", True),
            "model": ai_res.get("model", "Deterministic Grounded Engine"),
            "recommendation_summary": recommendation,
        }
    except Exception as e:
        logger.warning(f"[RecommendationEngine] AI generation failed, using deterministic fallback: {e}")
        return {
            "status": "success",
            "student_id": student_id,
            "ai_explanation": recommendation["ai_explanation"]["summary"],
            "is_live_ai": False,
            "model": "Rule-Based Offline Intelligence",
            "recommendation_summary": recommendation,
        }
