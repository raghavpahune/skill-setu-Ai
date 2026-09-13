import logging
import re
from datetime import datetime, timezone
from typing import Any
from app.core.security import is_demo_student_id
from app.core.time import parse_iso_timestamp
from app.db import get_demo
from app.repositories import supabase_repository

logger = logging.getLogger("skillsetu.roadmap")

PREREQUISITES_MAP: dict[str, list[str]] = {
    "sk-002": ["sk-001"],
    "sk-003": ["sk-002"],
    "sk-004": ["sk-003"],
    "sk-005": ["sk-004"],
    "sk-006": ["sk-004"],
    "sk-007": ["sk-001", "sk-008"],
    "sk-009": ["sk-001"],
    "sk-010": ["sk-009"],
    "sk-028": ["sk-009", "sk-001"],
    "sk-029": ["sk-028"],
    "sk-012": ["sk-011"],
    "sk-052": ["sk-011", "sk-012"],
    "sk-018": ["sk-023"],
    "sk-019": ["sk-023", "sk-018"],
    "sk-017": ["sk-016"],
    "sk-021": ["sk-017"],
    "sk-053": ["sk-021"],
    "sk-054": ["sk-017"],
    "sk-039": ["sk-013", "sk-014", "sk-008"],
    "sk-045": ["sk-020"],
    "sk-047": ["sk-008", "sk-001"],
}

NSQF_HOURS_MAP: dict[int, int] = {
    3: 20,
    4: 30,
    5: 40,
    6: 50,
    7: 65,
    8: 80,
}

ROLE_CAPSTONES: dict[str, dict[str, Any]] = {
    "ai engineer": {
        "title": "Autonomous RAG & Agentic Workflow Platform",
        "description": "Architect and deploy an enterprise-grade multimodal Retrieval-Augmented Generation agent with vector search and verifiable citations.",
        "deliverables": [
            "Vector pipeline with hybrid search",
            "Autonomous evaluation harness",
            "Production API with rate-limiting and telemetry",
        ],
        "estimated_hours": 40,
        "nsqf_level": 7,
    },
    "data analyst": {
        "title": "Statewide Labour Market Intelligence Dashboard",
        "description": "Build an automated end-to-end analytics pipeline extracting real-time industrial signals and visualizing district employment trends.",
        "deliverables": [
            "ETL pipeline for public labour records",
            "Interactive Power BI / Tableau dashboard",
            "Automated anomaly alert system",
        ],
        "estimated_hours": 35,
        "nsqf_level": 5,
    },
    "data scientist": {
        "title": "Industrial Defect Detection & Predictive Maintenance System",
        "description": "Train and validate machine learning models on telemetry datasets to forecast component failure in manufacturing assembly lines.",
        "deliverables": [
            "Feature engineering pipeline",
            "Model training and cross-validation suite",
            "Real-time inference microservice",
        ],
        "estimated_hours": 45,
        "nsqf_level": 7,
    },
    "cloud architect": {
        "title": "Multi-Region Resilient Kubernetes Infrastructure",
        "description": "Design an automated Terraform and Kubernetes cloud blueprint with zero-downtime rolling deploys, GitOps, and observability.",
        "deliverables": [
            "Infrastructure as Code definitions",
            "Helm charts for microservices",
            "Prometheus and Grafana alerting stack",
        ],
        "estimated_hours": 45,
        "nsqf_level": 7,
    },
    "devops engineer": {
        "title": "Enterprise GitOps CI/CD Automation Pipeline",
        "description": "Construct a fully automated delivery pipeline with container security scanning, automated regression testing, and canary rollouts.",
        "deliverables": [
            "GitHub Actions / GitLab CI pipeline",
            "Trivy container vulnerability scanner",
            "Canary deployment controller",
        ],
        "estimated_hours": 40,
        "nsqf_level": 6,
    },
    "cybersecurity analyst": {
        "title": "Zero-Trust Threat Defense & Incident Response Audit",
        "description": "Conduct a vulnerability assessment and penetration test across a simulated corporate intranet, implementing CERT-In compliance.",
        "deliverables": [
            "Threat vector map and attack surface report",
            "Hardened firewall and IAM policies",
            "Incident response playbook",
        ],
        "estimated_hours": 40,
        "nsqf_level": 6,
    },
    "ev technician": {
        "title": "High-Voltage Battery Pack Diagnostic & BMS Calibration",
        "description": "Diagnose cell balancing issues, calibrate state-of-charge algorithms, and simulate high-temperature thermal runaway containment.",
        "deliverables": [
            "CAN-bus diagnostic logs",
            "BMS firmware parameter calibration",
            "Safety isolation protocol compliance",
        ],
        "estimated_hours": 35,
        "nsqf_level": 5,
    },
    "ev engineer": {
        "title": "Dual-Inverter Powertrain & Regenerative Braking Simulator",
        "description": "Model electric powertrain dynamics and tune motor control algorithms for maximum energy recovery during deceleration cycles.",
        "deliverables": [
            "MATLAB / Simulink motor model",
            "Regenerative braking efficiency curves",
            "Thermal management architecture",
        ],
        "estimated_hours": 50,
        "nsqf_level": 6,
    },
    "robotics engineer": {
        "title": "Industrial Robotic Pick-and-Place Workcell Automation",
        "description": "Program an articulated robot arm integrated with machine vision inspection and PLC conveyor interlocking.",
        "deliverables": [
            "Robot motion trajectory routines",
            "PLC ladder logic interlocks",
            "Safety light curtain integration",
        ],
        "estimated_hours": 45,
        "nsqf_level": 6,
    },
    "full stack developer": {
        "title": "Production Microservices Portal with Real-Time WebSockets",
        "description": "Develop and deploy a full-stack platform featuring responsive UI, JWT auth, database persistence, and event-driven updates.",
        "deliverables": [
            "React and Tailwind frontend",
            "FastAPI / Node backend with async endpoints",
            "Dockerized deployment with CI/CD",
        ],
        "estimated_hours": 40,
        "nsqf_level": 6,
    },
}

DEFAULT_CAPSTONE: dict[str, Any] = {
    "title": "Industry Capstone Project",
    "description": "Deploy an end-to-end practical solution demonstrating verified competency in core target domain requirements.",
    "deliverables": [
        "Comprehensive system design documentation",
        "Working prototype repository with tests",
        "Performance and deployment validation metrics",
    ],
    "estimated_hours": 40,
    "nsqf_level": 6,
}


def _load_skills_map(is_demo: bool) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    if is_demo:
        skills_list = get_demo("skills") or []
    else:
        try:
            skills_list = supabase_repository.list_skills(limit=10000) or []
            if not skills_list:
                skills_list = get_demo("skills") or []
        except Exception:
            skills_list = get_demo("skills") or []

    by_id: dict[str, dict[str, Any]] = {}
    by_name: dict[str, dict[str, Any]] = {}
    for s in skills_list:
        sid = s.get("id")
        if sid:
            by_id[sid] = s
        name = s.get("name")
        if name:
            by_name[name.strip().lower()] = s
        for syn in s.get("synonyms") or []:
            if isinstance(syn, str) and syn.strip():
                by_name[syn.strip().lower()] = s
    return by_id, by_name


def _normalize_skill_token(token: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", token.lower())


def _extract_student_skills(profile: dict[str, Any] | None, assessment: dict[str, Any] | None, skills_by_id: dict[str, dict[str, Any]], skills_by_name: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    claimed: dict[str, dict[str, Any]] = {}

    def record_skill(sid: str | None, name: str | None, prof: str | None):
        target_sid = None
        matched_meta = None
        if sid and sid in skills_by_id:
            target_sid = sid
            matched_meta = skills_by_id[sid]
        elif name:
            clean_name = name.strip().lower()
            if clean_name in skills_by_name:
                matched_meta = skills_by_name[clean_name]
                target_sid = matched_meta.get("id")
            else:
                norm = _normalize_skill_token(name)
                for s_name, s_obj in skills_by_name.items():
                    if _normalize_skill_token(s_name) == norm:
                        matched_meta = s_obj
                        target_sid = s_obj.get("id")
                        break

        resolved_id = target_sid or sid or name
        if not resolved_id:
            return

        clean_prof = (prof or "intermediate").lower().strip()
        if resolved_id not in claimed:
            claimed[resolved_id] = {
                "skill_id": resolved_id,
                "skill_name": (matched_meta.get("name") if matched_meta else name) or resolved_id,
                "proficiency": clean_prof,
                "category": matched_meta.get("category", "General") if matched_meta else "General",
                "nsqf_level": matched_meta.get("nsqf_level", 5) if matched_meta else 5,
            }

    prof_time = parse_iso_timestamp((profile.get("updated_at") or profile.get("created_at") or "") if profile else "")
    asst_time = parse_iso_timestamp((assessment.get("updated_at") or assessment.get("created_at") or "") if assessment else "")
    prof_skills = (profile.get("skills") or []) if profile else []
    asst_skills = (assessment.get("current_skills") or []) if assessment else []
    sources = [(profile, prof_skills), (assessment, asst_skills)] if prof_time >= asst_time else [(assessment, asst_skills), (profile, prof_skills)]
    for src_obj, raw_skills in sources:
        if not src_obj:
            continue
        for sk in raw_skills:
            if isinstance(sk, dict):
                sid = sk.get("skill_id") or sk.get("id")
                name = sk.get("skill_name") or sk.get("name")
                prof = sk.get("proficiency") or sk.get("level")
                record_skill(sid, name, prof)
            elif isinstance(sk, str):
                record_skill(None, sk, "intermediate")

    return claimed


def _get_target_role(student_id: str, requested_role: str | None, profile: dict[str, Any] | None, assessment: dict[str, Any] | None) -> str:
    if requested_role and requested_role.strip():
        return requested_role.strip()
    prof_time = parse_iso_timestamp((profile.get("updated_at") or profile.get("created_at") or "") if profile else "")
    asst_time = parse_iso_timestamp((assessment.get("updated_at") or assessment.get("created_at") or "") if assessment else "")
    if prof_time >= asst_time:
        if profile and (profile.get("target_role") or profile.get("desired_role")):
            return str(profile.get("target_role") or profile.get("desired_role")).strip()
        if assessment and assessment.get("career_goal"):
            return str(assessment["career_goal"]).strip()
    else:
        if assessment and assessment.get("career_goal"):
            return str(assessment["career_goal"]).strip()
        if profile and (profile.get("target_role") or profile.get("desired_role")):
            return str(profile.get("target_role") or profile.get("desired_role")).strip()
    return "AI Engineer"


def _expand_and_topological_sort(core_skill_ids: list[str], skills_by_id: dict[str, dict[str, Any]]) -> list[str]:
    all_needed: set[str] = set(core_skill_ids)
    changed = True
    while changed:
        changed = False
        for sid in list(all_needed):
            for prereq in PREREQUISITES_MAP.get(sid, []):
                if prereq in skills_by_id and prereq not in all_needed:
                    all_needed.add(prereq)
                    changed = True

    in_degree: dict[str, int] = {sid: 0 for sid in all_needed}
    graph: dict[str, list[str]] = {sid: [] for sid in all_needed}

    for sid in all_needed:
        for prereq in PREREQUISITES_MAP.get(sid, []):
            if prereq in all_needed:
                graph[prereq].append(sid)
                in_degree[sid] += 1

    zero_in_degree = [sid for sid in all_needed if in_degree[sid] == 0]
    zero_in_degree.sort(key=lambda s: (skills_by_id.get(s, {}).get("nsqf_level", 5), skills_by_id.get(s, {}).get("name", s)))

    sorted_list: list[str] = []
    while zero_in_degree:
        curr = zero_in_degree.pop(0)
        sorted_list.append(curr)
        for neighbor in graph.get(curr, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                zero_in_degree.append(neighbor)
                zero_in_degree.sort(key=lambda s: (skills_by_id.get(s, {}).get("nsqf_level", 5), skills_by_id.get(s, {}).get("name", s)))

    for sid in all_needed:
        if sid not in sorted_list:
            sorted_list.append(sid)

    return sorted_list


def compute_adaptive_roadmap(
    student_id: str,
    target_role: str | None = None,
    is_demo: bool | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    from app.services.student_service import ROLE_REQUIREMENTS_MAP

    if is_demo is not None:
        is_demo_req = is_demo
    else:
        is_demo_req = is_demo_student_id(student_id) or any(
            (p.get("user_id") or p.get("id")) == student_id for p in (get_demo("student_profiles") or [])
        )

    profile = None
    profile_failed = False
    try:
        profile = supabase_repository.get_student_profile(student_id)
    except Exception as e:
        logger.warning("Failed fetching profile for roadmap '%s': %s", student_id, e)
        profile_failed = True
        profile = None

    if not profile and is_demo_req:
        for p in get_demo("student_profiles") or []:
            if (p.get("user_id") or p.get("id")) == student_id:
                profile = p
                break

    assessment = None
    assessment_failed = False
    try:
        assessment = supabase_repository.get_student_assessment_by_user(student_id) or supabase_repository.get_student_assessment(student_id)
    except Exception as e:
        logger.warning("Failed fetching assessment for roadmap '%s': %s", student_id, e)
        assessment_failed = True
    if not assessment and is_demo_req:
        for a in get_demo("student_assessments") or []:
            if a.get("id") == student_id or a.get("user_id") == student_id:
                assessment = a
                break

    if not is_demo_req and (profile_failed or assessment_failed):
        raise RuntimeError(f"Roadmap source data unavailable due to repository failure for student '{student_id}'")

    if not profile and not assessment and not is_demo_req:
        return {
            "user_id": student_id,
            "target_role": None,
            "has_roadmap": False,
            "roadmap": [],
            "message": "No personal assessment completed yet. Complete your diagnostic to view your learning roadmap.",
            "readiness_score": 0,
            "total_estimated_hours": 0,
            "summary": {
                "total_modules": 0,
                "to_learn": 0,
                "to_review": 0,
                "skipped": 0,
                "projects": 0,
                "readiness_score": 0,
            },
        }

    skills_by_id, skills_by_name = _load_skills_map(is_demo_req)
    resolved_role = _get_target_role(student_id, target_role, profile, assessment)
    role_key = resolved_role.lower().strip()

    core_skill_ids = ROLE_REQUIREMENTS_MAP.get(role_key)
    if not core_skill_ids:
        for r_k, sids in ROLE_REQUIREMENTS_MAP.items():
            if r_k in role_key or role_key in r_k:
                core_skill_ids = sids
                break
    if not core_skill_ids:
        core_skill_ids = ["sk-001", "sk-002", "sk-003", "sk-004", "sk-005", "sk-006"]

    claimed_skills = _extract_student_skills(profile, assessment, skills_by_id, skills_by_name)
    ordered_skill_ids = _expand_and_topological_sort(core_skill_ids, skills_by_id)

    forecast_map = {}
    try:
        forecasts = supabase_repository.list_skill_forecasts() or []
        for f in forecasts:
            if f.get("skill_id") and f["skill_id"] not in forecast_map:
                forecast_map[f["skill_id"]] = f
    except Exception:
        if is_demo_req:
            for f in get_demo("skill_forecasts") or []:
                if f.get("skill_id") and f["skill_id"] not in forecast_map:
                    forecast_map[f["skill_id"]] = f

    courses_list = []
    try:
        courses_list = supabase_repository.list_courses() or []
    except Exception:
        if is_demo_req:
            courses_list = get_demo("courses") or []

    signals_list = []
    try:
        signals_list = supabase_repository.list_industry_signals() or []
    except Exception:
        if is_demo_req:
            signals_list = get_demo("industry_signals") or []

    steps: list[dict[str, Any]] = []
    total_estimated_hours = 0
    core_points = 0.0

    for idx, sid in enumerate(ordered_skill_ids, start=1):
        meta = skills_by_id.get(sid, {
            "id": sid,
            "name": sid,
            "category": "General",
            "nsqf_level": 5,
        })
        skill_name = meta.get("name", sid)
        category = meta.get("category", "General")
        nsqf_level = int(meta.get("nsqf_level") or 5)
        base_hours = NSQF_HOURS_MAP.get(nsqf_level, 40)

        prereq_names = [skills_by_id[p].get("name", p) for p in PREREQUISITES_MAP.get(sid, []) if p in skills_by_id]

        is_core = sid in core_skill_ids
        student_claim = claimed_skills.get(sid) or claimed_skills.get(skill_name.strip().lower())

        if student_claim:
            prof = (student_claim.get("proficiency") or "intermediate").lower()
            if prof in ("advanced", "expert"):
                step_status = "SKIP"
                hours = 0
                why = f"Competency verified at {prof.capitalize()} level. Foundational prerequisite fulfilled."
                action_item = f"Prerequisite satisfied ({prof}). Ready for advanced specialization."
                if is_core:
                    core_points += 1.0
            else:
                step_status = "REVIEW"
                hours = max(10, int(base_hours * 0.35))
                why = f"Working knowledge verified at {prof.capitalize()} level. Targeted refresher recommended."
                action_item = f"Complete advanced practice drills and bridge intermediate nuances in {skill_name}."
                if is_core:
                    core_points += 0.5
        else:
            step_status = "LEARN"
            hours = base_hours
            why = f"Core competency deficit for {resolved_role}. Required to build industry qualification."
            action_item = f"Master foundational and applied modules for {skill_name} aligned with NSQF Level {nsqf_level}."

        total_estimated_hours += hours

        norm_skill = _normalize_skill_token(skill_name)
        fc = forecast_map.get(sid, {})
        matched_courses = []
        for c in courses_list:
            c_skills = {_normalize_skill_token(str(s)) for s in (c.get("skills") or c.get("skills_taught") or []) if s}
            c_name_tokens = {_normalize_skill_token(w) for w in (c.get("name") or c.get("course_name") or "").split() if w}
            if norm_skill in c_skills or norm_skill in c_name_tokens or _normalize_skill_token(c.get("name") or c.get("course_name") or "") == norm_skill:
                matched_courses.append({
                    "course_id": c.get("id"),
                    "course_name": c.get("name") or c.get("course_name"),
                    "institute_name": c.get("institute") or c.get("institute_name"),
                    "district": c.get("district"),
                })
            if len(matched_courses) >= 2:
                break

        matched_signals = []
        for sig in signals_list:
            if not sig.get("is_active", True) or sig.get("validation_status", "APPROVED") != "APPROVED":
                continue
            sig_skills = {_normalize_skill_token(str(s)) for s in (sig.get("skills") or []) if s}
            sig_title_tokens = {_normalize_skill_token(w) for w in (sig.get("title") or "").split() if w}
            if norm_skill in sig_skills or norm_skill in sig_title_tokens or _normalize_skill_token(sig.get("title") or "") == norm_skill:
                matched_signals.append({
                    "id": sig.get("id"),
                    "title": sig.get("title"),
                    "source_name": sig.get("source_name") or sig.get("source"),
                })
            if len(matched_signals) >= 2:
                break

        difficulty = "Beginner" if nsqf_level <= 4 else ("Intermediate" if nsqf_level <= 6 else "Advanced")

        steps.append({
            "step": idx,
            "skill_id": sid,
            "skill_name": skill_name,
            "category": category,
            "nsqf_level": nsqf_level,
            "status": step_status,
            "is_core": is_core,
            "estimated_hours": hours,
            "difficulty": difficulty,
            "prerequisites": prereq_names,
            "future_demand": fc.get("future_demand", "high"),
            "trend": fc.get("trend", "rising"),
            "confidence": fc.get("confidence", 85),
            "timeframe": fc.get("timeframe", "2025-2027"),
            "why": why,
            "action_item": action_item,
            "matched_courses": matched_courses,
            "matched_signals": matched_signals,
        })

    capstone = ROLE_CAPSTONES.get(role_key, DEFAULT_CAPSTONE)
    capstone_hours = int(capstone.get("estimated_hours", 40))
    total_estimated_hours += capstone_hours

    steps.append({
        "step": len(steps) + 1,
        "skill_id": f"capstone-{_normalize_skill_token(resolved_role)}",
        "skill_name": capstone["title"],
        "category": "Practical Capstone",
        "nsqf_level": capstone.get("nsqf_level", 6),
        "status": "PROJECT",
        "is_core": True,
        "estimated_hours": capstone_hours,
        "difficulty": "Advanced",
        "prerequisites": [s["skill_name"] for s in steps if s.get("is_core")],
        "future_demand": "very high",
        "trend": "rising",
        "confidence": 95,
        "timeframe": "2025-2027",
        "why": capstone["description"],
        "action_item": "Deploy production solution and integrate with student verified portfolio.",
        "deliverables": capstone.get("deliverables", []),
        "matched_courses": [],
        "matched_signals": [],
    })

    total_cores = max(1, len(core_skill_ids))
    readiness_score = int(round((core_points / total_cores) * 100))
    readiness_score = max(0, min(100, readiness_score))

    summary = {
        "total_modules": len(steps),
        "to_learn": len([s for s in steps if s["status"] == "LEARN"]),
        "to_review": len([s for s in steps if s["status"] == "REVIEW"]),
        "skipped": len([s for s in steps if s["status"] == "SKIP"]),
        "projects": len([s for s in steps if s["status"] == "PROJECT"]),
        "readiness_score": readiness_score,
    }

    result = {
        "user_id": student_id,
        "target_role": resolved_role,
        "has_roadmap": True,
        "readiness_score": readiness_score,
        "total_estimated_hours": total_estimated_hours,
        "summary": summary,
        "roadmap": steps,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": "DEMO_SYNTHETIC" if is_demo_req else "SUPABASE_AUTHORITATIVE",
        "is_demo": is_demo_req,
    }

    if persist and is_demo_req:
        try:
            supabase_repository.upsert_student_roadmap(result)
        except Exception as e:
            logger.warning("Demo roadmap write suppressed: %s", e)
    elif persist:
        try:
            supabase_repository.upsert_student_roadmap(result)
        except Exception as e:
            logger.error("Failed persisting student roadmap for user '%s': %s", student_id, e)
            raise

    return result
