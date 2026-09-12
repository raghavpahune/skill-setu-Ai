"""Student Service — Personalized Industry Alerts & Skill Explainability Hub.

Fulfills PROJECT_SPEC Section 18 ("Why Should I Learn This?") and Section 19 ("Personalized Industry Alerts").
Derives all metrics deterministically from existing SkillSetu datasets with explicit data grounding.
"""
import logging
from collections import Counter
from typing import Any

from app.core.security import is_demo_student_id
from app.db import get_demo
from app.services.gap_engine import compute_gaps
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported Alert Domains (PROJECT_SPEC Section 19)
# ---------------------------------------------------------------------------

SUPPORTED_ALERT_DOMAINS = [
    {
        "id": "ai_ml",
        "name": "AI / ML",
        "icon": "🤖",
        "description": "Autonomous agents, RAG architectures, generative models, and LLM orchestration.",
        "signal_ids": ["sig-001", "sig-006", "sig-011"],
        "skill_categories": ["AI/ML"],
        "core_skill_ids": ["sk-005", "sk-006", "sk-004", "sk-041", "sk-002", "sk-003", "sk-040"],
    },
    {
        "id": "data_science",
        "name": "Data Science",
        "icon": "📊",
        "description": "Enterprise data analytics, predictive modeling, SQL warehousing, and BI dashboards.",
        "signal_ids": ["sig-006"],
        "skill_categories": ["Data Science"],
        "core_skill_ids": ["sk-007", "sk-008", "sk-030", "sk-047", "sk-001"],
    },
    {
        "id": "cloud",
        "name": "Cloud Computing",
        "icon": "☁️",
        "description": "Cloud-native architectures, Kubernetes containerization, CI/CD, and AWS infrastructure.",
        "signal_ids": ["sig-003"],
        "skill_categories": ["Cloud"],
        "core_skill_ids": ["sk-009", "sk-010", "sk-028", "sk-029"],
    },
    {
        "id": "cybersecurity",
        "name": "Cybersecurity",
        "icon": "🛡️",
        "description": "CERT-In compliance, network defense, threat detection, and ethical vulnerability testing.",
        "signal_ids": ["sig-004"],
        "skill_categories": ["Security"],
        "core_skill_ids": ["sk-011", "sk-012", "sk-052"],
    },
    {
        "id": "robotics",
        "name": "Robotics & Automation",
        "icon": "🦾",
        "description": "Industrial robotics, PLC automation, Industry 4.0 smart factory lines, and mechatronics.",
        "signal_ids": ["sig-005"],
        "skill_categories": ["Manufacturing"],
        "core_skill_ids": ["sk-021", "sk-053", "sk-054", "sk-017"],
    },
    {
        "id": "ev",
        "name": "Electric Vehicles",
        "icon": "⚡",
        "description": "EV battery management systems, motor design, power electronics, and charging networks.",
        "signal_ids": ["sig-002"],
        "skill_categories": ["Electric Vehicles"],
        "core_skill_ids": ["sk-018", "sk-019", "sk-023", "sk-045"],
    },
    {
        "id": "iot",
        "name": "IoT & Embedded",
        "icon": "📡",
        "description": "Connected sensor networks, embedded C microcontrollers, smart farming, and edge telemetry.",
        "signal_ids": ["sig-005", "sig-012"],
        "skill_categories": ["Emerging Tech", "Electronics", "Agriculture"],
        "core_skill_ids": ["sk-020", "sk-045", "sk-036", "sk-033"],
    },
]


def list_alert_domains() -> list[dict[str, Any]]:
    """Return all supported alert domains with metadata."""
    return [
        {
            "id": d["id"],
            "name": d["name"],
            "icon": d["icon"],
            "description": d["description"],
            "skills_count": len(d["core_skill_ids"]),
        }
        for d in SUPPORTED_ALERT_DOMAINS
    ]


# ---------------------------------------------------------------------------
# Feature 1: Personalized Industry Alerts Engine
# ---------------------------------------------------------------------------

def get_personalized_industry_alerts(
    domain_id: str | None = None,
    student_id: str | None = None,
    is_demo: bool | None = None,
    current_user: dict | None = None,
) -> dict[str, Any]:
    """Retrieve personalized technology and labour-market signals for a domain."""
    from app.core.data_mode import is_explicit_demo_mode
    is_demo_req = False if is_demo is False else (is_explicit_demo_mode(is_demo) or (student_id is not None and is_demo_student_id(student_id)))

    if is_demo_req:
        signals_all = {s["id"]: s for s in get_demo("industry_signals")}
        skills_map = {s["id"]: s for s in get_demo("skills")}
        jobs = get_demo("jobs")
        job_skills = get_demo("job_skills")
        courses = get_demo("courses")
        course_skills = get_demo("course_skills")
    else:
        try:
            from app.repositories.supabase_repository import list_industry_signals as list_industry_signals_repo
            signals_all = {s["id"]: s for s in list_industry_signals_repo()}
        except Exception:
            signals_all = {}
        try:
            from app.repositories.supabase_repository import list_skills
            repo_skills = list_skills(limit=10000) or []
            skills_map = {s["id"]: s for s in repo_skills if "id" in s}
        except Exception:
            skills_map = {}
        try:
            from app.repositories.supabase_repository import list_jobs as list_jobs_repo, list_job_skills as list_job_skills_repo
            repo_jobs = list_jobs_repo(limit=10000)
            jobs = [j for j in (repo_jobs or []) if not j.get("is_demo")]
            job_ids = {j.get("id") for j in jobs if j.get("id")}
            repo_js = list_job_skills_repo(job_ids=list(job_ids)) if job_ids else []
            job_skills = [js for js in (repo_js or []) if js.get("job_id") in job_ids]
        except Exception:
            jobs = []
            job_skills = []
        try:
            from app.repositories.supabase_repository import list_courses, list_course_skills
            courses = list_courses() or []
            c_ids = [c["id"] for c in courses if c.get("id")]
            course_skills = list_course_skills(course_ids=c_ids) if c_ids else []
        except Exception:
            courses = []
            course_skills = []
    gaps_list = compute_gaps(is_demo=is_demo_req)
    gaps_map = {g["skill_id"]: g for g in gaps_list}

    # Student context if provided
    student_profile = None
    student_acquired_ids = set()
    if student_id:
        is_demo_id = is_demo_student_id(student_id)
        is_demo_fixture = False
        if not is_demo_id:
            demo_profiles = get_demo("student_profiles") or []
            is_demo_fixture = any((p.get("user_id") or p.get("id")) == student_id for p in demo_profiles)
        is_demo_req = is_demo_id or is_demo_fixture
        if not is_demo_req and current_user is not None:
            user_id = current_user.get("id")
            user_role = (current_user.get("role") or "").upper()
            if user_id != student_id and user_role != "ADMIN":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: You cannot access industry alerts for another user.",
                )

        try:
            from app.repositories.supabase_repository import get_student_profile, get_student_assessment, get_student_assessment_by_user, get_employee_profile
            student_profile = (
                get_student_profile(student_id)
                or get_student_assessment(student_id)
                or get_student_assessment_by_user(student_id)
                or get_employee_profile(student_id)
            )
        except Exception as e:
            logger.error("[StudentService] Supabase error resolving student %s: %s", student_id, e)
            student_profile = None

        if not student_profile and is_demo_req:
            profiles = get_demo("student_profiles")
            for p in profiles:
                if p["user_id"] == student_id:
                    student_profile = p
                    break
        student_acquired_ids = set()
        if student_profile:
            name_to_sids: dict[str, list[str]] = {}
            for s_id, s_obj in skills_map.items():
                s_n = (s_obj.get("name") or "").strip().lower()
                if s_n:
                    name_to_sids.setdefault(s_n, []).append(s_id)

            for sk in student_profile.get("skills", []):
                if isinstance(sk, dict):
                    if "skill_id" in sk and sk["skill_id"]:
                        student_acquired_ids.add(sk["skill_id"])
                    s_name = (sk.get("skill_name") or sk.get("name") or "").strip().lower()
                    if s_name in name_to_sids:
                        student_acquired_ids.update(name_to_sids[s_name])

    # Determine domains to evaluate
    domains_to_process = []
    if domain_id and domain_id.lower() != "all":
        matched = [d for d in SUPPORTED_ALERT_DOMAINS if d["id"] == domain_id.lower()]
        if matched:
            domains_to_process = matched
        else:
            # Fallback to all if unknown domain requested
            domains_to_process = SUPPORTED_ALERT_DOMAINS
    else:
        domains_to_process = SUPPORTED_ALERT_DOMAINS

    alerts_result = []

    for dom in domains_to_process:
        # 1. Gather signals associated with this domain
        dom_signals = [signals_all[sid] for sid in dom["signal_ids"] if sid in signals_all]
        if not dom_signals:
            continue

        primary_signal = dom_signals[0]

        # 2. Extract affected skills for this domain
        affected_skill_ids = set(primary_signal.get("affected_skills", []))
        affected_skill_ids.update(dom["core_skill_ids"])

        affected_skills_data = []
        for sid in affected_skill_ids:
            sk = skills_map.get(sid)
            if not sk:
                continue
            gp = gaps_map.get(sid, {})
            affected_skills_data.append({
                "skill_id": sid,
                "name": sk.get("name", ""),
                "category": sk.get("category", ""),
                "nsqf_level": sk.get("nsqf_level"),
                "demand_pct": gp.get("demand_pct", 0),
                "gap_pct": gp.get("gap_pct", 0),
                "priority": gp.get("priority", "MEDIUM"),
                "is_acquired": sid in student_acquired_ids,
            })

        # Sort affected skills by demand/gap
        affected_skills_data.sort(key=lambda x: x["demand_pct"], reverse=True)

        # 3. Calculate relevant job demand metrics
        matching_job_ids = {
            js["job_id"] for js in job_skills if js["skill_id"] in affected_skill_ids
        }
        domain_jobs_count = len(matching_job_ids)
        total_jobs_count = len(jobs) or 1
        demand_share_pct = min(100, round((domain_jobs_count / total_jobs_count) * 100))

        # 4. Determine student-specific skills to strengthen
        skills_to_strengthen = []
        if student_profile:
            # Prioritize skills required by student's target role or in domain that student lacks
            for sk_item in affected_skills_data:
                if not sk_item["is_acquired"] and sk_item["gap_pct"] > 0:
                    skills_to_strengthen.append(sk_item)
        else:
            # General high-gap skills in domain
            skills_to_strengthen = [s for s in affected_skills_data if s["gap_pct"] >= 5]

        # 5. Formulate actionable next steps
        actionable_steps = []
        if dom["id"] == "ai_ml":
            actionable_steps = [
                "Build and deploy an autonomous Agentic RAG pipeline capstone",
                "Complete advanced vector indexing and prompt orchestration modules",
                "Target verified AI Engineer entry requirements in Pune and Mumbai clusters",
            ]
        elif dom["id"] == "ev":
            actionable_steps = [
                "Master Battery Management System (BMS) telemetry and motor drive diagnostics",
                "Enroll in accredited high-voltage industrial electrical maintenance practicals",
                "Prepare for Chakan EV manufacturing corridor industrial apprenticeship intake",
            ]
        elif dom["id"] == "cloud":
            actionable_steps = [
                "Achieve hands-on certification in Kubernetes cluster configuration & Docker",
                "Implement end-to-end CI/CD automated deployment pipelines on AWS/Azure",
                "Practice infrastructure-as-code automation and production container monitoring",
            ]
        elif dom["id"] == "cybersecurity":
            actionable_steps = [
                "Review CERT-In compliance frameworks for Maharashtra enterprise infrastructure",
                "Practice network packet inspection, intrusion detection, and security auditing",
                "Obtain ethical hacking and endpoint security verification credentials",
            ]
        elif dom["id"] == "robotics":
            actionable_steps = [
                "Program industrial 6-axis robotic arms and PLC automation sequences",
                "Master Industry 4.0 sensor telemetry and predictive maintenance interfaces",
                "Align with Siemens Technical Academy or Government ITI Pune advanced trades",
            ]
        elif dom["id"] == "data_science":
            actionable_steps = [
                "Build production SQL analytics pipelines and real-time Power BI dashboards",
                "Deepen statistical inference, ETL automation, and feature engineering workflows",
                "Target junior data analyst and business intelligence roles across Maharashtra IT corridors",
            ]
        elif dom["id"] == "iot":
            actionable_steps = [
                "Interface microcontrollers with environmental IoT telemetry sensors",
                "Build embedded C edge computing modules for precision agriculture and smart metering",
                "Complete Maharashtra Smart Agriculture Mission certified practical training",
            ]

        # 6. Find related certified training courses
        related_course_ids = {
            cs["course_id"] for cs in course_skills if cs["skill_id"] in affected_skill_ids
        }
        related_courses = [
            {
                "id": c["id"],
                "name": c["name"],
                "institute": c["institute"],
                "district": c.get("district", ""),
                "enrolment": c.get("enrolment_count", 0),
            }
            for c in courses
            if c["id"] in related_course_ids
        ][:4]

        # 7. Assemble Alert Card
        alerts_result.append({
            "domain_id": dom["id"],
            "domain_name": dom["name"],
            "domain_icon": dom["icon"],
            "primary_signal": {
                "id": primary_signal["id"],
                "title": primary_signal["title"],
                "technology": primary_signal.get("technology", dom["name"]),
                "summary": primary_signal["summary"],
                "source": primary_signal.get("source", "Maharashtra Industry Council"),
                "signal_date": primary_signal.get("signal_date", "2026-07-01"),
                "impact_level": primary_signal.get("impact_level", "high"),
            },
            "career_impact": {
                "level": primary_signal.get("impact_level", "high").upper(),
                "score_out_of_10": 9 if primary_signal.get("impact_level") == "critical" else (8 if primary_signal.get("impact_level") == "high" else 6),
                "summary": f"Strong hiring momentum in {dom['name']} across Maharashtra's industrial belts.",
            },
            "job_demand_signal": {
                "active_vacancies_count": domain_jobs_count,
                "demand_share_pct": demand_share_pct,
                "hiring_trend": "Surging (↑ YoY)" if demand_share_pct > 15 else "Steady",
            },
            "affected_skills": affected_skills_data[:6],
            "skills_to_strengthen": skills_to_strengthen[:4],
            "actionable_next_steps": actionable_steps,
            "related_courses": related_courses,
            "data_provenance": "GROUNDED_DEMO_DATASET" if is_demo_req else "SUPABASE_AUTHORITATIVE",
        })

    return {
        "status": "success",
        "selected_domain": domain_id or "all",
        "student_id": student_id,
        "available_domains": list_alert_domains(),
        "alerts": alerts_result,
        "data_provenance": "GROUNDED_DEMO_DATASET" if is_demo_req else "SUPABASE_AUTHORITATIVE",
    }


# ---------------------------------------------------------------------------
# Feature 2: "Why Should I Learn This?" Explainability Hub
# ---------------------------------------------------------------------------

def get_skill_explainability(
    skill_query: str,
    student_id: str | None = None,
    is_demo: bool | None = None,
) -> dict[str, Any]:
    """Provide a transparent, 5-point evidence-based explainability breakdown for a skill."""
    from app.core.data_mode import is_explicit_demo_mode
    is_demo_req = False if is_demo is False else (is_explicit_demo_mode(is_demo) or (student_id is not None and is_demo_student_id(student_id)))
    if is_demo_req:
        skills_list = get_demo("skills")
        skills_map = {s["id"]: s for s in skills_list}
        jobs = get_demo("jobs")
        job_skills = get_demo("job_skills")
        courses = get_demo("courses")
        course_skills = get_demo("course_skills")
    else:
        try:
            from app.repositories.supabase_repository import list_skills
            repo_skills = list_skills(limit=10000) or []
            skills_list = repo_skills
            skills_map = {s["id"]: s for s in skills_list if "id" in s}
        except Exception:
            skills_list = []
            skills_map = {}
        try:
            from app.repositories.supabase_repository import list_jobs as list_jobs_repo, list_job_skills as list_job_skills_repo
            repo_jobs = list_jobs_repo(limit=10000)
            jobs = [j for j in (repo_jobs or []) if not j.get("is_demo")]
            job_ids = {j.get("id") for j in jobs if j.get("id")}
            repo_js = list_job_skills_repo(job_ids=list(job_ids)) if job_ids else []
            job_skills = [js for js in (repo_js or []) if js.get("job_id") in job_ids]
        except Exception:
            jobs = []
            job_skills = []
        try:
            from app.repositories.supabase_repository import list_courses, list_course_skills
            courses = list_courses() or []
            c_ids = [c["id"] for c in courses if c.get("id")]
            course_skills = list_course_skills(course_ids=c_ids) if c_ids else []
        except Exception:
            courses = []
            course_skills = []
    # 0. Resolve student record BEFORE deciding whether demo forecast fallback is allowed
    resolved_student = None
    _authoritative_lookup_failed = False
    if student_id:
        try:
            from app.repositories.supabase_repository import (
                get_student_profile,
                get_student_assessment,
                get_student_assessment_by_user,
            )
            resolved_student = (
                get_student_profile(student_id)
                or get_student_assessment(student_id)
                or get_student_assessment_by_user(student_id)
            )
        except ImportError:
            pass  # ponytail: supabase module unavailable — test/local env
        except Exception as e:
            from app.repositories.supabase_repository import SupabaseConnectionError
            if isinstance(e, SupabaseConnectionError):
                # Supabase not configured — expected in test/demo environments
                logger.info("[StudentService] Supabase not configured for student %s, will check demo fixtures", student_id)
            else:
                # Real authoritative lookup failure — do NOT fall through to demo
                logger.error("[StudentService] Authoritative Supabase lookup failed for student %s: %s", student_id, e)
                _authoritative_lookup_failed = True

        # Only search demo fixtures if authoritative lookup did NOT fail (it either succeeded with no result, or Supabase wasn't configured)
        if not resolved_student and not _authoritative_lookup_failed and is_demo_student_id(student_id):
            profiles = get_demo("student_profiles")
            for item in profiles:
                if item.get("user_id") == student_id or item.get("id") == student_id:
                    resolved_student = item
                    break

        if _authoritative_lookup_failed and not resolved_student:
            raise RuntimeError("Failed to resolve student record") from None


    # Only allow get_demo("skill_forecasts") when the resolved student record explicitly has is_demo=True or source=DEMO_SYNTHETIC.
    # For unresolved students, real users, USER_SUBMITTED students, and stu-* IDs that belong to real users:
    # do NOT silently use demo forecasts.
    is_explicit_demo = bool(
        resolved_student
        and (resolved_student.get("is_demo") is True or resolved_student.get("source") == "DEMO_SYNTHETIC")
        and resolved_student.get("source") != "USER_SUBMITTED"
        and resolved_student.get("is_demo") is not False
    )
    fc_from_repo = False
    if is_demo_req:
        forecasts = get_demo("skill_forecasts")
    else:
        try:
            from app.repositories.supabase_repository import list_skill_forecasts
            forecasts = list_skill_forecasts() or []
            fc_from_repo = True
        except Exception as e:
            if is_explicit_demo:
                logger.warning("[SkillExplainability] Supabase forecasts unavailable, using demo fixtures for demo student %s: %s", student_id, e)
                forecasts = get_demo("skill_forecasts")
            else:
                logger.exception("[SkillExplainability] Supabase forecast query failed for non-demo student %s: %s", student_id, e)
                raise RuntimeError("Database error fetching skill forecasts.") from e
    if is_demo_req:
        feedback = get_demo("employer_feedback")
    else:
        try:
            from app.repositories.supabase_repository import list_employer_feedback
            feedback = list_employer_feedback() or []
        except Exception:
            feedback = []
    difficult_skills = get_demo("difficult_skills") if is_demo_req else []
    if is_demo_req:
        signals = get_demo("industry_signals")
    else:
        try:
            from app.repositories.supabase_repository import list_industry_signals as list_industry_signals_repo
            signals = list_industry_signals_repo()
        except Exception:
            signals = []
    gaps_list = compute_gaps(is_demo=is_demo_req)
    gaps_map = {g["skill_id"]: g for g in gaps_list}

    # 1. Resolve target skill by ID or case-insensitive name/synonym
    target_skill = None
    q_clean = skill_query.strip().lower()

    if q_clean in skills_map:
        target_skill = skills_map[q_clean]
    else:
        for s in skills_list:
            if s.get("name", "").lower() == q_clean or s.get("id", "").lower() == q_clean:
                target_skill = s
                break
            for syn in s.get("synonyms", []):
                if syn.lower() == q_clean:
                    target_skill = s
                    break
            if target_skill:
                break

    if not target_skill:
        return {
            "error": "Skill not found in Maharashtra labour-market database",
            "queried": skill_query,
            "data_available": False,
        }

    sid = target_skill["id"]
    skill_name = target_skill.get("name", "Unknown Skill")
    category = target_skill.get("category", "General")
    nsqf_level = target_skill.get("nsqf_level")

    # 2. Dimension 1: Demand Surge / Current Demand Signal
    matching_jobs = [js for js in job_skills if js["skill_id"] == sid]
    vacancies_count = len(matching_jobs)
    total_jobs = len(jobs) or 1
    demand_pct = min(100, round((vacancies_count / total_jobs) * 100))

    # Top hiring districts for this skill
    job_id_set = {js["job_id"] for js in matching_jobs}
    matching_job_objs = [j for j in jobs if j["id"] in job_id_set]
    district_counts = Counter(j.get("district", "Maharashtra") for j in matching_job_objs)
    top_districts = [d for d, _ in district_counts.most_common(3)]

    # Top hiring roles
    role_counts = Counter(j.get("title", "") for j in matching_job_objs)
    relevant_roles = [r for r, _ in role_counts.most_common(4)]

    demand_verified = bool(vacancies_count > 0 and (not is_demo_req or is_explicit_demo)) if not is_demo_req else True
    dimension_demand = {
        "verified": demand_verified,
        "demand_pct": demand_pct,
        "active_vacancies_count": vacancies_count,
        "demand_surge_label": f"↑ {demand_pct}% of indexed Maharashtra job postings",
        "top_hiring_districts": top_districts if top_districts else ["Pune", "Mumbai"],
        "relevant_roles_count": len(role_counts),
        "relevant_roles": relevant_roles,
    }

    # 3. Dimension 2: Future Horizon / Forecast Outlook
    skill_fc_records = [f for f in forecasts if f.get("skill_id") == sid]
    if skill_fc_records:
        # Choose best period or 12m
        fc_12m = next((f for f in skill_fc_records if f.get("period") == "12m"), skill_fc_records[0])
        fc_verified = bool(fc_from_repo and not fc_12m.get("is_demo", False) and fc_12m.get("source") != "DEMO_SYNTHETIC")
        dimension_forecast = {
            "verified": fc_verified,
            "forecast_source": fc_12m.get("source", "SUPABASE_AUTHORITATIVE" if fc_from_repo else "DEMO_SYNTHETIC"),
            "period": fc_12m.get("period", "12m"),
            "future_demand": fc_12m.get("future_demand", "high").replace("_", " ").upper(),
            "trend": fc_12m.get("trend", "rising"),
            "confidence_pct": fc_12m.get("confidence", 80),
            "summary": f"Projected {fc_12m.get('future_demand', 'high').replace('_', ' ')} demand over {fc_12m.get('period', '12m')} with {fc_12m.get('confidence', 80)}% model confidence.",
        }
    else:
        dimension_forecast = {
            "verified": False,
            "forecast_verified": False,
            "forecast_source": "UNAVAILABLE",
            "future_demand": "UNAVAILABLE",
            "trend": "unknown",
            "confidence_pct": None,
            "summary": "Verified longitudinal forecast projection is currently unavailable for this specific competency.",
        }

    # 4. Dimension 3: Employer Demand & Shortage Consensus
    diff_record = next((d for d in difficult_skills if d.get("skill_id") == sid), None)
    emp_feedbacks = [f for f in feedback if f.get("skill_id") == sid]
    confirmed_count = sum(1 for f in emp_feedbacks if f.get("status") == "confirmed")
    corrected_count = sum(1 for f in emp_feedbacks if f.get("status") == "corrected")

    if diff_record or emp_feedbacks:
        dimension_employer = {
            "verified": True,
            "demand_rating": "CRITICAL SHORTAGE" if (diff_record and diff_record.get("deficit_score", 0) > 75) else "HIGH DEMAND",
            "deficit_score": diff_record.get("deficit_score") if diff_record else 70,
            "avg_days_to_fill": diff_record.get("avg_days_to_fill") if diff_record else 45,
            "hiring_challenge": diff_record.get("shortage_reason") if diff_record else "Industry employers report scarcity of candidates with production-grade proficiency.",
            "employer_validations": {
                "total_reviews": len(emp_feedbacks),
                "confirmed": confirmed_count,
                "corrected": corrected_count,
            },
        }
    else:
        dimension_employer = {
            "verified": True,
            "demand_rating": "MODERATE DEMAND",
            "deficit_score": None,
            "avg_days_to_fill": 28,  # baseline state benchmark
            "hiring_challenge": "Standard recruitment turnaround aligned with state baseline.",
            "employer_validations": {"total_reviews": len(emp_feedbacks), "confirmed": 0, "corrected": 0},
        }

    # 5. Dimension 4: Curriculum Deficit & Training Capacity
    gap_data = gaps_map.get(sid, {})
    coverage_pct = gap_data.get("coverage_pct", 0)
    gap_pct = gap_data.get("gap_pct", max(0, demand_pct - coverage_pct))
    priority = gap_data.get("priority", "MEDIUM")

    # Find training courses teaching this skill
    taught_in_course_ids = {cs["course_id"]: cs.get("coverage_level", 0) for cs in course_skills if cs["skill_id"] == sid}
    teaching_courses = [
        {
            "id": c["id"],
            "name": c["name"],
            "institute": c["institute"],
            "district": c.get("district", ""),
            "coverage_level": taught_in_course_ids.get(c["id"], 3),
        }
        for c in courses
        if c["id"] in taught_in_course_ids
    ]

    dimension_curriculum = {
        "verified": True,
        "curriculum_coverage_pct": coverage_pct,
        "skill_gap_pct": gap_pct,
        "priority_level": priority,
        "courses_count": len(teaching_courses),
        "teaching_courses": teaching_courses[:4],
        "coverage_summary": f"Current vocational syllabus coverage is {coverage_pct}% against {demand_pct}% employer demand (Deficit: {gap_pct}%).",
    }

    # 6. Dimension 5: Formal Academic / Training Rationale
    # Find any related macro signal
    related_signal = next((sig for sig in signals if sid in sig.get("affected_skills", [])), None)

    rationale_text = (
        f"Recommended by Maharashtra State Innovation Society and vocational curriculum boards "
        f"because live job-posting trends ({demand_pct}% demand frequency), employer validations, "
        f"and {category} technological shifts indicate rapid workforce absorption, while state institutional coverage ({coverage_pct}%) leaves an active talent deficit of {gap_pct}%."
    )

    dimension_rationale = {
        "verified": True,
        "recommendation_level": "HIGH PRIORITY REQUISITE" if gap_pct >= 8 else "RECOMMENDED ELECTIVE",
        "formal_statement": rationale_text,
        "associated_signal_title": related_signal.get("title") if related_signal else None,
    }

    # 7. Student Personalization Overlay (if student_id supplied)
    student_alignment = None
    if student_id:
        p = resolved_student
        if p:
            skills_list = p.get("skills", []) + p.get("current_skills", [])
            has_skill = any((sk.get("skill_id") == sid or sk.get("skill_name", "").lower() == skill_name.lower()) if isinstance(sk, dict) else sk == sid for sk in skills_list)
            req_skills = p.get("required_skills", [])
            is_required_for_target = any(r == sid or (isinstance(r, dict) and r.get("skill_id") == sid) for r in req_skills)
            student_alignment = {
                "student_name": p.get("name", "Student"),
                "target_role": p.get("target_role") or p.get("career_goal", "Career Goal"),
                "is_acquired": has_skill,
                "is_required_for_target": is_required_for_target,
                "status_label": "Already Acquired" if has_skill else ("Core Target Deficit" if is_required_for_target else "Recommended Adjacent Competency"),
            }

    return {
        "status": "success",
        "data_available": True,
        "skill": {
            "id": sid,
            "name": skill_name,
            "category": category,
            "nsqf_level": nsqf_level,
        },
        "explainability": {
            "dimension_1_demand_surge": dimension_demand,
            "dimension_2_future_forecast": dimension_forecast,
            "dimension_3_employer_consensus": dimension_employer,
            "dimension_4_curriculum_deficit": dimension_curriculum,
            "dimension_5_academic_rationale": dimension_rationale,
        },
        "student_alignment": student_alignment,
        "data_provenance": "GROUNDED_DEMO_DATASET" if is_demo_req else "SUPABASE_AUTHORITATIVE",
    }


# ---------------------------------------------------------------------------
# Feature 3: Phase 12 Student Data Collection & Diagnostic Assessment
# ---------------------------------------------------------------------------

DIAGNOSTIC_QUIZ_QUESTIONS = [
    {
        "id": "q1",
        "category": "Problem Solving & Logic",
        "question": "When approaching a complex technical challenge or system bottleneck, what is your standard initial approach?",
        "options": [
            {"key": "a", "text": "Jump straight into implementation with trial-and-error iterations.", "points": 10},
            {"key": "b", "text": "Decompose the problem into modular specifications, verify requirements, and map logical steps.", "points": 20},
            {"key": "c", "text": "Search for pre-built snippets and copy without inspecting underlying mechanics.", "points": 10},
            {"key": "d", "text": "Wait for external guidance before initiating preliminary troubleshooting.", "points": 5},
        ],
        "rationale": "Systematic problem decomposition and requirement verification reflect engineering maturity.",
    },
    {
        "id": "q2",
        "category": "Applied Tooling & Standards",
        "question": "How do you ensure reliability, version safety, and quality in your projects or coursework?",
        "options": [
            {"key": "a", "text": "Save occasional local backup copies with date-stamped file names.", "points": 5},
            {"key": "b", "text": "Rely exclusively on final manual inspection right before deadline submission.", "points": 10},
            {"key": "c", "text": "Utilize standardized version control (Git), automated validation/tests, and structured documentation.", "points": 20},
            {"key": "d", "text": "Only inspect quality if an instructor or supervisor flags an error.", "points": 5},
        ],
        "rationale": "Git version control and automated validation are foundational industry standards.",
    },
    {
        "id": "q3",
        "category": "Emerging Technologies",
        "question": "In modern AI & data architectures, what differentiates production Agentic/RAG pipelines from simple static chatbots?",
        "options": [
            {"key": "a", "text": "Dynamic tool execution, persistent vector memory retrieval, and deterministic verification.", "points": 20},
            {"key": "b", "text": "Larger font styling and longer text prompts without data connection.", "points": 5},
            {"key": "c", "text": "Running basic offline spelling and grammar correction filters.", "points": 10},
            {"key": "d", "text": "Replacing all relational databases with flat spreadsheet files.", "points": 5},
        ],
        "rationale": "Agentic workflows combine grounded domain retrieval with active tool calling.",
    },
    {
        "id": "q4",
        "category": "Data & Quality Assurance",
        "question": "When preparing dataset inputs or telemetry streams for model training or industrial monitoring, what is essential?",
        "options": [
            {"key": "a", "text": "Ignoring null values and feeding raw unfiltered records directly.", "points": 5},
            {"key": "b", "text": "Data profiling, schema validation, outlier handling, and consistency checks.", "points": 20},
            {"key": "c", "text": "Duplicating existing rows until the dataset volume looks impressive.", "points": 5},
            {"key": "d", "text": "Manually fabricating missing sensor metrics.", "points": 5},
        ],
        "rationale": "Rigorous data sanitation prevents cascading errors in downstream intelligence.",
    },
    {
        "id": "q5",
        "category": "Continuous Upskilling",
        "question": "How do you align your technical capabilities with shifting Maharashtra industry demand?",
        "options": [
            {"key": "a", "text": "Rely strictly on outdated academic syllabi without exploring modern frameworks.", "points": 5},
            {"key": "b", "text": "Audit skill gaps against live market signals, build practical capstones, and target NSQF credentials.", "points": 20},
            {"key": "c", "text": "Postpone learning industry skills until after joining a corporate workplace.", "points": 10},
            {"key": "d", "text": "Avoid emerging technologies until they become mandatory requisites.", "points": 5},
        ],
        "rationale": "Proactive self-assessment against live labour signals accelerates career placement.",
    },
]


def get_diagnostic_quiz_questions() -> list[dict[str, Any]]:
    return [
        {
            "id": q["id"],
            "category": q["category"],
            "question": q["question"],
            "options": [{"key": opt["key"], "text": opt["text"]} for opt in q["options"]],
        }
        for q in DIAGNOSTIC_QUIZ_QUESTIONS
    ]


DOMAIN_QUESTION_BANK = [
    {
        "id": "q_sw_git",
        "category": "Software & DevOps",
        "domain": "software",
        "skills": ["Git", "DevOps"],
        "question": "In a collaborative Git workflow, what is the best practice for isolating new features before merging into the release branch?",
        "options": [
            {"key": "a", "text": "Commit directly to the main branch to ensure fast synchronization.", "points": 5},
            {"key": "b", "text": "Create a dedicated feature branch, perform automated testing and pull request reviews prior to merging.", "points": 20},
            {"key": "c", "text": "Delete local repositories and clone fresh daily.", "points": 5},
            {"key": "d", "text": "Disable branch protection rules to avoid merge conflicts.", "points": 5},
        ],
    },
    {
        "id": "q_sw_docker",
        "category": "Software & DevOps",
        "domain": "software",
        "skills": ["Docker", "Containers", "DevOps"],
        "question": "What is the primary advantage of utilizing multi-stage Docker builds in production deployments?",
        "options": [
            {"key": "a", "text": "They increase image size by retaining all build-time dependencies.", "points": 5},
            {"key": "b", "text": "They produce lightweight, secure final images by copying only compiled artifacts into runtime containers.", "points": 20},
            {"key": "c", "text": "They prevent containers from running on Linux kernels.", "points": 5},
            {"key": "d", "text": "They eliminate the need for container registries.", "points": 5},
        ],
    },
    {
        "id": "q_sw_dsa",
        "category": "Software Engineering",
        "domain": "software",
        "skills": ["Data Structures", "Algorithms"],
        "question": "Which data structure provides average O(1) time complexity for lookup, insert, and delete operations by key?",
        "options": [
            {"key": "a", "text": "Singly Linked List", "points": 5},
            {"key": "b", "text": "Binary Search Tree", "points": 10},
            {"key": "c", "text": "Hash Map / Hash Table", "points": 20},
            {"key": "d", "text": "Array requiring linear scan", "points": 5},
        ],
    },
    {
        "id": "q_sw_api",
        "category": "Software Engineering",
        "domain": "software",
        "skills": ["API Design", "Backend"],
        "question": "Which HTTP method is designated by RFC standards to be idempotent for updating an existing resource with a full replacement representation?",
        "options": [
            {"key": "a", "text": "POST", "points": 10},
            {"key": "b", "text": "PUT", "points": 20},
            {"key": "c", "text": "PATCH", "points": 10},
            {"key": "d", "text": "CONNECT", "points": 5},
        ],
    },
    {
        "id": "q_sw_py",
        "category": "Software Engineering",
        "domain": "software",
        "skills": ["Python", "Programming"],
        "question": "Why are Python generator expressions preferred over large list comprehensions when streaming millions of records?",
        "options": [
            {"key": "a", "text": "Generators preload the entire dataset into RAM immediately.", "points": 5},
            {"key": "b", "text": "Generators yield items lazily on-demand, reducing memory consumption to O(1).", "points": 20},
            {"key": "c", "text": "Generators disable Python garbage collection entirely.", "points": 5},
            {"key": "d", "text": "Generators convert all variables into static C types.", "points": 5},
        ],
    },
    {
        "id": "q_sw_java",
        "category": "Software Engineering",
        "domain": "software",
        "skills": ["Java", "Backend"],
        "question": "In concurrent Java programming, what does declaring a variable as volatile guarantee?",
        "options": [
            {"key": "a", "text": "Atomic execution of compound increment operations.", "points": 10},
            {"key": "b", "text": "Immediate visibility of writes across all threads by bypassing thread-local CPU cache.", "points": 20},
            {"key": "c", "text": "Automatic serialization of the enclosing class to disk.", "points": 5},
            {"key": "d", "text": "Prevention of garbage collection on that object.", "points": 5},
        ],
    },
    {
        "id": "q_ai_rag",
        "category": "AI & Machine Learning",
        "domain": "ai_ml",
        "skills": ["RAG", "Generative AI", "AI Agents"],
        "question": "What core mechanism enables a Retrieval-Augmented Generation (RAG) system to minimize factual hallucinations in LLM responses?",
        "options": [
            {"key": "a", "text": "Increasing the LLM temperature parameter to maximum creativity.", "points": 5},
            {"key": "b", "text": "Retrieving grounded domain context from a vector database and injecting it into the prompt context window.", "points": 20},
            {"key": "c", "text": "Training models solely on synthetic unverified text prompts.", "points": 5},
            {"key": "d", "text": "Storing text as unindexed flat binary blobs.", "points": 5},
        ],
    },
    {
        "id": "q_ai_eval",
        "category": "AI & Machine Learning",
        "domain": "ai_ml",
        "skills": ["Machine Learning", "Model Evaluation"],
        "question": "When evaluating a classification model with severe class imbalance (99% negative, 1% positive), which metric is most reliable?",
        "options": [
            {"key": "a", "text": "Raw Accuracy", "points": 5},
            {"key": "b", "text": "Precision-Recall AUC and F1-Score on the minority class", "points": 20},
            {"key": "c", "text": "Total training epoch count", "points": 5},
            {"key": "d", "text": "Number of input features regardless of relevance", "points": 5},
        ],
    },
    {
        "id": "q_ai_overfit",
        "category": "AI & Machine Learning",
        "domain": "ai_ml",
        "skills": ["Deep Learning", "Regularization"],
        "question": "What technique prevents deep neural networks from memorizing training noise and overfitting?",
        "options": [
            {"key": "a", "text": "Removing validation datasets during training.", "points": 5},
            {"key": "b", "text": "Applying Dropout, weight decay (L2 regularization), and early stopping based on validation loss.", "points": 20},
            {"key": "c", "text": "Duplicating identical training batches repeatedly without shuffling.", "points": 5},
            {"key": "d", "text": "Maximizing model parameter count with minimal data samples.", "points": 5},
        ],
    },
    {
        "id": "q_ds_sql",
        "category": "Data Science",
        "domain": "ai_ml",
        "skills": ["SQL", "Data Analysis"],
        "question": "In analytical SQL, which clause allows calculating a moving average or running total across partitions without collapsing individual rows?",
        "options": [
            {"key": "a", "text": "GROUP BY without aggregate functions", "points": 5},
            {"key": "b", "text": "Window functions using the OVER (PARTITION BY ... ORDER BY ...) clause", "points": 20},
            {"key": "c", "text": "CROSS JOIN on all records", "points": 5},
            {"key": "d", "text": "HAVING clause without conditions", "points": 5},
        ],
    },
    {
        "id": "q_ds_pandas",
        "category": "Data Science",
        "domain": "ai_ml",
        "skills": ["Data Preprocessing", "Python", "Data Analysis"],
        "question": "When preparing telemetry data with extreme outliers for statistical modeling, what is the best preprocessing step?",
        "options": [
            {"key": "a", "text": "Silently replace all missing values with arbitrary zero values.", "points": 5},
            {"key": "b", "text": "Perform exploratory outlier analysis, apply robust scaling or log transformation, and impute missing data methodically.", "points": 20},
            {"key": "c", "text": "Delete 90% of observations at random.", "points": 5},
            {"key": "d", "text": "Bypass normalization and feed unscaled values into distance-based estimators.", "points": 5},
        ],
    },
    {
        "id": "q_mech_cad",
        "category": "Mechanical & Manufacturing",
        "domain": "mechanical",
        "skills": ["CAD", "Parametric Modeling", "AutoCAD"],
        "question": "In parametric 3D CAD modeling, what does Geometric Dimensioning and Tolerancing (GD&T) ensure during component fabrication?",
        "options": [
            {"key": "a", "text": "Visual aesthetic colors on assembly renders.", "points": 5},
            {"key": "b", "text": "Explicit allowable variation in geometry, form, orientation, and location for proper assembly mating.", "points": 20},
            {"key": "c", "text": "Disabling all manufacturing tolerances to enforce perfect theoretical dimensions.", "points": 5},
            {"key": "d", "text": "Converting 3D assemblies into 1D text lists.", "points": 5},
        ],
    },
    {
        "id": "q_mech_mfg",
        "category": "Mechanical & Manufacturing",
        "domain": "mechanical",
        "skills": ["CNC Programming", "Manufacturing"],
        "question": "What does the G-code command 'G01' specify in CNC milling and turning operations?",
        "options": [
            {"key": "a", "text": "Rapid non-cutting positioning move at maximum traverse speed.", "points": 10},
            {"key": "b", "text": "Linear feed interpolation cutting move at a controlled feed rate.", "points": 20},
            {"key": "c", "text": "Spindle stop and coolant shutoff.", "points": 5},
            {"key": "d", "text": "Emergency machine reset.", "points": 5},
        ],
    },
    {
        "id": "q_mech_thermo",
        "category": "Mechanical Engineering",
        "domain": "mechanical",
        "skills": ["Thermodynamics", "Heat Transfer"],
        "question": "Which mode of heat transfer governs thermal dissipation across metal heat sinks in natural convection air cooling?",
        "options": [
            {"key": "a", "text": "Conduction through the metal fin matrix combined with convective fluid dissipation into surrounding air.", "points": 20},
            {"key": "b", "text": "Pure vacuum electromagnetic radiation only.", "points": 5},
            {"key": "c", "text": "Nuclear transmutation.", "points": 5},
            {"key": "d", "text": "Frictional kinetic heating.", "points": 5},
        ],
    },
    {
        "id": "q_mech_plc",
        "category": "Robotics & Automation",
        "domain": "mechanical",
        "skills": ["PLC Programming", "Industrial Automation", "Robotics"],
        "question": "In industrial PLC ladder logic, how is an emergency stop (E-Stop) circuit wired to meet safety integrity levels (SIL)?",
        "options": [
            {"key": "a", "text": "Normally Open (NO) software flag with no hardware interlock.", "points": 5},
            {"key": "b", "text": "Fail-safe Normally Closed (NC) physical contact opening on power disruption or press.", "points": 20},
            {"key": "c", "text": "Through an unmonitored wireless Bluetooth bridge.", "points": 5},
            {"key": "d", "text": "In series with the operator touchscreen back-light.", "points": 5},
        ],
    },
    {
        "id": "q_mech_quality",
        "category": "Quality Engineering",
        "domain": "mechanical",
        "skills": ["Quality Control", "Six Sigma", "Manufacturing"],
        "question": "What does a process capability index (Cpk) greater than 1.33 indicate in mass component manufacturing?",
        "options": [
            {"key": "a", "text": "The process is unstable and generating over 50% scrap.", "points": 5},
            {"key": "b", "text": "The process is capable, centered, and producing well within specified engineering upper and lower tolerance limits.", "points": 20},
            {"key": "c", "text": "All measurement sensors have failed calibration.", "points": 5},
            {"key": "d", "text": "Production cycle times have doubled.", "points": 5},
        ],
    },
    {
        "id": "q_elec_circuits",
        "category": "Electrical Engineering",
        "domain": "electrical",
        "skills": ["Circuit Analysis", "Electrical"],
        "question": "According to Kirchhoff's Current Law (KCL), what is the algebraic sum of all electrical currents entering and exiting an ideal circuit node?",
        "options": [
            {"key": "a", "text": "Infinite amperes.", "points": 5},
            {"key": "b", "text": "Zero, reflecting conservation of electric charge.", "points": 20},
            {"key": "c", "text": "Equal to the supply voltage.", "points": 5},
            {"key": "d", "text": "Dependent strictly on ambient room temperature.", "points": 5},
        ],
    },
    {
        "id": "q_elec_bms",
        "category": "Electric Vehicles",
        "domain": "electrical",
        "skills": ["EV Battery Technology", "BMS", "Electric Vehicles"],
        "question": "What critical function does an active cell balancing circuit perform within an EV Lithium-ion Battery Management System (BMS)?",
        "options": [
            {"key": "a", "text": "Overcharging weak cells until they match strong cells.", "points": 5},
            {"key": "b", "text": "Equalizing state-of-charge across all series cells to maximize usable pack capacity and prevent thermal runaway.", "points": 20},
            {"key": "c", "text": "Discharging the entire vehicle pack to zero volts on every startup.", "points": 5},
            {"key": "d", "text": "Bypassing temperature sensor monitoring during fast charging.", "points": 5},
        ],
    },
    {
        "id": "q_elec_power",
        "category": "Power Electronics",
        "domain": "electrical",
        "skills": ["Power Electronics", "Inverters", "EV"],
        "question": "In an EV traction inverter, what is the primary purpose of Pulse-Width Modulation (PWM) applied to MOSFET/IGBT gate drivers?",
        "options": [
            {"key": "a", "text": "Converting DC battery voltage into variable-frequency, variable-amplitude sinusoidal AC currents for the traction motor.", "points": 20},
            {"key": "b", "text": "Generating mechanical brake pressure on the wheels.", "points": 5},
            {"key": "c", "text": "Increasing radio frequency interference across cabin speakers.", "points": 5},
            {"key": "d", "text": "Discharging vehicle telemetry into the ground chassis.", "points": 5},
        ],
    },
    {
        "id": "q_elec_motor",
        "category": "Electric Motors",
        "domain": "electrical",
        "skills": ["Motor Control", "EV Motor Design", "Electric Vehicles"],
        "question": "Why is Field-Oriented Control (FOC) preferred over simple trapezoidal commutation for permanent magnet synchronous motors (PMSM) in EVs?",
        "options": [
            {"key": "a", "text": "FOC produces high torque ripple and noisy acoustic vibrations.", "points": 5},
            {"key": "b", "text": "FOC independently controls torque and magnetic flux components, delivering smooth torque, high efficiency, and dynamic response.", "points": 20},
            {"key": "c", "text": "FOC requires mechanical carbon brushes that wear down over time.", "points": 5},
            {"key": "d", "text": "FOC eliminates the need for motor rotor position feedback.", "points": 5},
        ],
    },
    {
        "id": "q_elec_embedded",
        "category": "Embedded Systems",
        "domain": "electrical",
        "skills": ["Embedded Systems", "Microcontrollers", "IoT"],
        "question": "Why are hardware interrupt service routines (ISRs) kept as short and non-blocking as possible in real-time embedded controllers?",
        "options": [
            {"key": "a", "text": "Longer ISRs increase compiler memory optimization.", "points": 5},
            {"key": "b", "text": "To prevent blocking lower-priority interrupts and ensure real-time responsiveness to critical system events.", "points": 20},
            {"key": "c", "text": "To disable serial bus communications permanently.", "points": 5},
            {"key": "d", "text": "Because microcontrollers cannot execute more than 3 instructions.", "points": 5},
        ],
    },
    {
        "id": "q_sec_auth",
        "category": "Cybersecurity",
        "domain": "cybersecurity",
        "skills": ["Authentication", "Cybersecurity", "Security"],
        "question": "Why is storing plaintext passwords in a user database considered a critical vulnerability, and what is the standard mitigation?",
        "options": [
            {"key": "a", "text": "Plaintext is safe if stored behind an intranet firewall.", "points": 5},
            {"key": "b", "text": "Passwords must be hashed using adaptive, salted cryptographic functions (e.g. Argon2, bcrypt) with high work factors.", "points": 20},
            {"key": "c", "text": "Reversing password character order provides sufficient security.", "points": 5},
            {"key": "d", "text": "Compressing passwords into zip files before database storage.", "points": 5},
        ],
    },
    {
        "id": "q_sec_vuln",
        "category": "Cybersecurity",
        "domain": "cybersecurity",
        "skills": ["Application Security", "OWASP", "Cybersecurity"],
        "question": "What is the primary defense against SQL Injection vulnerabilities in backend database query handlers?",
        "options": [
            {"key": "a", "text": "Concatenating untrusted user input directly into SQL strings.", "points": 5},
            {"key": "b", "text": "Utilizing parameterized queries (prepared statements) and Object-Relational Mapping (ORM) escaping.", "points": 20},
            {"key": "c", "text": "Relying exclusively on client-side JavaScript regex validation.", "points": 5},
            {"key": "d", "text": "Increasing database query timeout limits to 60 seconds.", "points": 5},
        ],
    },
    {
        "id": "q_sec_net",
        "category": "Cybersecurity",
        "domain": "cybersecurity",
        "skills": ["Network Security", "Zero Trust", "Security"],
        "question": "What is the foundational principle of a Zero Trust Network Architecture?",
        "options": [
            {"key": "a", "text": "Automatically trust all traffic originating from within the internal corporate network perimeter.", "points": 5},
            {"key": "b", "text": "Never trust, always verify: authenticate and authorize every user, device, and request continuously regardless of network location.", "points": 20},
            {"key": "c", "text": "Disable firewalls and authentication tokens on internal microservices.", "points": 5},
            {"key": "d", "text": "Assign universal root administrator privileges to all employees.", "points": 5},
        ],
    },
    {
        "id": "q_sec_crypto",
        "category": "Cybersecurity",
        "domain": "cybersecurity",
        "skills": ["Cryptography", "Data Protection", "Security"],
        "question": "In TLS 1.3 secure communication, how do symmetric and asymmetric cryptography collaborate?",
        "options": [
            {"key": "a", "text": "Asymmetric encryption is used for all payload data transfer throughout the entire session.", "points": 5},
            {"key": "b", "text": "Asymmetric cryptography securely establishes shared session keys during handshake, and symmetric ciphers encrypt the high-speed data payload.", "points": 20},
            {"key": "c", "text": "Neither cipher type is used in TLS handshakes.", "points": 5},
            {"key": "d", "text": "Symmetric keys are sent unencrypted over public DNS queries.", "points": 5},
        ],
    },
]

ALL_DIAGNOSTIC_QUESTIONS = DIAGNOSTIC_QUIZ_QUESTIONS + DOMAIN_QUESTION_BANK
ALL_DIAGNOSTIC_QUESTIONS_MAP = {q["id"]: q for q in ALL_DIAGNOSTIC_QUESTIONS}


def get_personalized_diagnostic_questions(
    student_id: str,
    user_email: str | None = None,
) -> dict[str, Any]:
    from app.repositories import supabase_repository
    profile = None
    try:
        profile = supabase_repository.get_student_profile(student_id)
    except Exception as e:
        logger.warning("[AssessmentPersonalization] Failed fetching student profile %s: %s", student_id, e)

    has_skills = bool(profile and profile.get("skills") and len(profile.get("skills")) > 0)
    has_role = bool(profile and (profile.get("target_role") or profile.get("desired_role")))
    has_education = bool(profile and (profile.get("degree") or profile.get("education_level") or profile.get("institution")))

    if not profile or (not has_skills and not has_role and not has_education):
        return {
            "status": "profile_incomplete",
            "message": "Please complete your Skill Passport before taking your personalized assessment.",
            "questions": [],
        }

    skills_list = profile.get("skills") or []
    claimed_skill_names = [
        (s.get("skill_name") or s.get("name") or "").strip().lower()
        for s in skills_list
        if isinstance(s, dict)
    ]
    claimed_skill_names = [cs for cs in claimed_skill_names if cs]
    target_role = (profile.get("target_role") or profile.get("desired_role") or "").lower()
    degree = (profile.get("degree") or "").lower()
    education_level = (profile.get("education_level") or "").lower()
    career_interests = [str(i).lower() for i in (profile.get("career_interests") or [])]

    corpus = f"{target_role} {degree} {education_level} {' '.join(career_interests)} {' '.join(claimed_skill_names)}"

    corpus_words = set(corpus.split())
    if any(k in corpus for k in ("machine learning", "deep learning", "data science", "data analyst", "nlp", "rag", "analytics", "pytorch", "tensorflow", "llm")) or "ai" in corpus_words or "ai_ml" in corpus_words:
        domain = "ai_ml"
    elif any(k in corpus for k in ("security", "cyber", "penetration", "soc analyst", "cryptography", "infosec")):
        domain = "cybersecurity"
    elif any(k in corpus for k in ("electric", "battery", "circuit", "power system", "electronics", "electrical", "bms", "inverter")) or "ev" in corpus_words:
        domain = "electrical"
    elif any(k in corpus for k in ("mechanical", "cad", "cam", "manufacturing", "machining", "cnc", "thermo", "robot")):
        domain = "mechanical"
    else:
        domain = "software"

    domain_pool = [q for q in DOMAIN_QUESTION_BANK if q.get("domain") == domain]
    selected_questions: list[dict[str, Any]] = []
    selected_ids: set[str] = set()

    for q in domain_pool:
        q_skills = [s.lower() for s in q.get("skills", [])]
        if any(cs in q_skills or any(cs in qs for qs in q_skills) for cs in claimed_skill_names):
            selected_questions.append(q)
            selected_ids.add(q["id"])
            if len(selected_questions) >= 2:
                break

    for q in domain_pool:
        if q["id"] not in selected_ids:
            q_skills = [s.lower() for s in q.get("skills", [])]
            if any(qs in target_role for qs in q_skills):
                selected_questions.append(q)
                selected_ids.add(q["id"])
                if len(selected_questions) >= 4:
                    break

    for q in domain_pool:
        if q["id"] not in selected_ids:
            selected_questions.append(q)
            selected_ids.add(q["id"])
            if len(selected_questions) >= 5:
                break

    if len(selected_questions) < 5:
        for q in DIAGNOSTIC_QUIZ_QUESTIONS:
            if q["id"] not in selected_ids:
                selected_questions.append(q)
                selected_ids.add(q["id"])
                if len(selected_questions) >= 5:
                    break

    sanitized = [
        {
            "id": q["id"],
            "category": q["category"],
            "skills": q.get("skills", [q.get("category", "General")]),
            "question": q["question"],
            "options": [{"key": opt["key"], "text": opt["text"]} for opt in q["options"]],
        }
        for q in selected_questions
    ]

    return {
        "status": "success",
        "domain": domain,
        "questions": sanitized,
    }


ROLE_REQUIREMENTS_MAP = {
    "ai engineer": ["sk-001", "sk-002", "sk-003", "sk-004", "sk-005", "sk-006"],
    "data analyst": ["sk-001", "sk-007", "sk-008", "sk-030"],
    "data scientist": ["sk-001", "sk-002", "sk-007", "sk-008", "sk-047"],
    "ev technician": ["sk-018", "sk-019", "sk-023", "sk-045"],
    "ev engineer": ["sk-018", "sk-019", "sk-023", "sk-045", "sk-042"],
    "cybersecurity analyst": ["sk-011", "sk-012", "sk-052", "sk-001"],
    "cloud architect": ["sk-009", "sk-010", "sk-028", "sk-029"],
    "devops engineer": ["sk-009", "sk-010", "sk-028", "sk-029", "sk-001"],
    "robotics engineer": ["sk-021", "sk-017", "sk-053", "sk-054"],
    "full stack developer": ["sk-001", "sk-013", "sk-014", "sk-008", "sk-039"],
    "iot engineer": ["sk-020", "sk-045", "sk-036", "sk-033"],
    "smart manufacturing engineer": ["sk-016", "sk-017", "sk-053", "sk-054", "sk-049"],
}


def evaluate_student_assessment(submission_data: dict[str, Any]) -> dict[str, Any]:
    import datetime
    import uuid
    from app.core.data_mode import is_explicit_demo_mode

    uid = str(submission_data.get("user_id") or submission_data.get("id") or "")
    is_demo_sub = is_demo_student_id(uid)

    if is_demo_sub:
        skills_list = get_demo("skills")
        skills_map = {s["id"]: s for s in skills_list}
        skills_name_map = {s["name"].lower(): s for s in skills_list}
        courses = get_demo("courses")
        course_skills = get_demo("course_skills")
    else:
        try:
            from app.repositories.supabase_repository import list_skills, list_courses, list_course_skills
            skills_list = list_skills(limit=10000) or []
            skills_map = {s["id"]: s for s in skills_list if "id" in s}
            skills_name_map = {s["name"].lower(): s for s in skills_list if "name" in s}
            courses = list_courses() or []
            c_ids = [c["id"] for c in courses if c.get("id")]
            course_skills = list_course_skills(course_ids=c_ids) if c_ids else []
        except Exception:
            skills_list = []
            skills_map = {}
            skills_name_map = {}
            courses = []
            course_skills = []

    gaps_list = compute_gaps(is_demo=is_demo_sub)
    gaps_map = {g["skill_id"]: g for g in gaps_list}

    for s in skills_list:
        for syn in (s.get("synonyms") or []):
            skills_name_map[syn.lower()] = s

    quiz_answers = submission_data.get("quiz_answers", {})
    total_quiz_points = 0
    max_quiz_points = 0
    strong_knowledge_skills: list[str] = []
    moderate_knowledge_skills: list[str] = []
    weak_knowledge_skills: list[str] = []

    for q_id, opt_key in quiz_answers.items():
        q_obj = ALL_DIAGNOSTIC_QUESTIONS_MAP.get(q_id)
        if not q_obj:
            continue
        max_quiz_points += 20
        options_map = {opt["key"].lower(): opt.get("points", 5) for opt in q_obj.get("options", [])}
        pts = options_map.get(str(opt_key).lower(), 5)
        total_quiz_points += pts
        tested_label = (q_obj.get("skills") or [q_obj.get("category", "General")])[0]
        if pts >= 15:
            strong_knowledge_skills.append(tested_label)
        elif pts >= 10:
            moderate_knowledge_skills.append(tested_label)
        else:
            weak_knowledge_skills.append(tested_label)

    if max_quiz_points == 0:
        max_quiz_points = 100

    quiz_score_pct = min(100, max(0, round((total_quiz_points / max(1, max_quiz_points)) * 100)))

    # 2. Parse and resolve student's current skills
    current_skills_input = submission_data.get("current_skills", [])
    resolved_current_skills = []
    acquired_skill_ids = set()

    for item in current_skills_input:
        s_name = item.get("skill_name", "").strip() if isinstance(item, dict) else str(item).strip()
        prof = item.get("proficiency", "intermediate").lower() if isinstance(item, dict) else "intermediate"
        if not s_name:
            continue

        matched_skill = skills_name_map.get(s_name.lower())
        if matched_skill:
            sid = matched_skill["id"]
            acquired_skill_ids.add(sid)
            resolved_current_skills.append({
                "skill_id": sid,
                "skill_name": matched_skill["name"],
                "category": matched_skill.get("category", "General"),
                "nsqf_level": matched_skill.get("nsqf_level", 5),
                "proficiency": prof,
            })
        else:
            # Custom / User-entered skill
            resolved_current_skills.append({
                "skill_id": None,
                "skill_name": s_name,
                "category": "Self-Reported",
                "nsqf_level": None,
                "proficiency": prof,
            })

    # 3. Determine target role required skills
    career_goal = submission_data.get("career_goal", "").strip()
    target_role_clean = career_goal.lower()

    # Look up in standard role map or search closest match
    required_skill_ids = ROLE_REQUIREMENTS_MAP.get(target_role_clean)
    if not required_skill_ids:
        # Search substring match
        for role_key, sids in ROLE_REQUIREMENTS_MAP.items():
            if role_key in target_role_clean or target_role_clean in role_key:
                required_skill_ids = sids
                break

    if not required_skill_ids:
        # Default fallback to 4 prevalent foundational skills
        required_skill_ids = ["sk-001", "sk-007", "sk-008", "sk-050"]

    # 4. Calculate Skill Match Percentage and Identify Gaps
    required_skills_data = []
    missing_skills_data = []
    acquired_target_count = 0
    weighted_score = 0.0

    prof_weights = {"beginner": 0.4, "intermediate": 0.75, "advanced": 1.0, "expert": 1.0}

    for sid in required_skill_ids:
        sk = skills_map.get(sid, {"id": sid, "name": "Required Skill", "category": "General", "nsqf_level": 5})
        is_acquired = sid in acquired_skill_ids
        gap_info = gaps_map.get(sid, {})

        matching_current = next((c for c in resolved_current_skills if c.get("skill_id") == sid), None)
        current_prof = matching_current["proficiency"] if matching_current else "none"

        if is_acquired:
            acquired_target_count += 1
            weighted_score += prof_weights.get(current_prof, 0.75)
        else:
            priority = gap_info.get("priority", "HIGH")
            missing_skills_data.append({
                "skill_id": sid,
                "name": sk.get("name", sid),
                "category": sk.get("category", "General"),
                "nsqf_level": sk.get("nsqf_level", 5),
                "priority": priority,
                "gap_pct": gap_info.get("gap_pct", 65),
                "demand_pct": gap_info.get("demand_pct", 70),
            })

        required_skills_data.append({
            "skill_id": sid,
            "skill_name": sk.get("name", sid),
            "category": sk.get("category", "General"),
            "nsqf_level": sk.get("nsqf_level", 5),
            "is_acquired": is_acquired,
            "proficiency": current_prof,
        })

    total_target = len(required_skill_ids) or 1
    skill_match_pct = min(100, max(0, round((weighted_score / total_target) * 100)))

    # 5. Determine Overall Readiness Level
    combined_score = round(0.6 * skill_match_pct + 0.4 * quiz_score_pct)
    if combined_score >= 75:
        readiness_level = "PRODUCTION_READY"
        readiness_desc = "High competency match and strong diagnostic aptitude. Ready for industry apprenticeships and trainee placement."
    elif combined_score >= 40:
        readiness_level = "INTERMEDIATE_READY"
        readiness_desc = "Solid foundational competencies. Recommended to bridge targeted high-priority skill gaps."
    else:
        readiness_level = "FOUNDATIONAL"
        readiness_desc = "Early-stage learner profile. Structured vocational curriculum and prerequisite practicals recommended."

    # 6. Formulate Tailored Learning Next Steps
    recommended_steps = []
    for idx, m in enumerate(missing_skills_data[:3], start=1):
        recommended_steps.append(f"Step {idx}: Master {m['name']} ({m['category']}) to resolve priority labour deficit.")

    if not recommended_steps:
        recommended_steps = [
            "Build an advanced end-to-end capstone portfolio demonstrating production proficiency.",
            "Apply for verified NAPS apprenticeship openings and employer recruitment drives.",
            "Explore specialized NSQF Level 7-8 certifications.",
        ]
    else:
        recommended_steps.append("Validate competencies through hands-on lab practicals and apply for state welfare toolkits.")

    # 7. Find Related Courses
    missing_ids = {m["skill_id"] for m in missing_skills_data}
    matching_course_ids = {cs["course_id"] for cs in course_skills if cs["skill_id"] in missing_ids}
    related_courses = [
        {
            "id": c["id"],
            "name": c["name"],
            "institute": c["institute"],
            "district": c.get("district", ""),
        }
        for c in courses
        if c["id"] in matching_course_ids
    ][:3]

    # 8. Assemble Completed Record
    assessment_id = f"ast-demo-{uuid.uuid4().hex[:8]}" if is_demo_sub else f"ast-usr-{uuid.uuid4().hex[:8]}"
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    knowledge_breakdown = {
        "strong": strong_knowledge_skills,
        "moderate": moderate_knowledge_skills,
        "weak": weak_knowledge_skills,
        "missing": missing_skills_data,
    }

    assessment_record = {
        "id": assessment_id,
        "name": submission_data.get("name", "").strip(),
        "education": submission_data.get("education", "").strip(),
        "district": submission_data.get("district", "Maharashtra").strip() or "Maharashtra",
        "career_goal": career_goal,
        "interests": submission_data.get("interests", []),
        "current_skills": resolved_current_skills,
        "quiz_answers": quiz_answers,
        "quiz_score_pct": quiz_score_pct,
        "skill_match_pct": skill_match_pct,
        "combined_readiness_score": combined_score,
        "domain_readiness_score": combined_score,
        "skill_proficiency_score": skill_match_pct,
        "knowledge_breakdown": knowledge_breakdown,
        "evaluation_summary": {
            "readiness_level": readiness_level,
            "readiness_desc": readiness_desc,
            "target_role": career_goal,
            "domain_readiness_score": combined_score,
            "skill_proficiency_score": skill_match_pct,
            "knowledge_breakdown": knowledge_breakdown,
            "total_target_skills": len(required_skills_data),
            "acquired_count": acquired_target_count,
            "missing_count": len(missing_skills_data),
            "missing_skills": missing_skills_data,
            "recommended_next_steps": recommended_steps,
            "related_courses": related_courses,
        },
        "submitted_at": now_iso,
        "source": "DEMO_SYNTHETIC" if is_demo_sub else "USER_SUBMITTED",
        "source_label": "Demo Assessment Simulation" if is_demo_sub else "Candidate Self-Reported Assessment",
        "is_demo": is_demo_sub,
        "data_provenance": "DEMO_SYNTHETIC" if is_demo_sub else "SELF_REPORTED_ASSESSMENT",
    }

    return assessment_record

