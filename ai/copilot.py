"""AI Copilot orchestrator — selects provider, fetches query-specific context, returns grounded answer."""
import os
import sys
import re
import logging
from typing import Any
from collections import Counter
from pathlib import Path
from fastapi import HTTPException

logger = logging.getLogger("skillsetu.ai.copilot")

# Ensure backend app is importable
_backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from ai.provider import LLMProvider
from ai.gemini_provider import GeminiProvider
from ai.demo_provider import DemoProvider
from app.core.data_mode import is_explicit_demo_mode
from app.core.security import is_demo_student_id

KNOWN_EXTERNAL_TECHS = {
    "go": "Go / Golang",
    "golang": "Go / Golang",
    "go lang": "Go / Golang",
    "rust": "Rust",
    "ruby": "Ruby",
    "ruby on rails": "Ruby on Rails",
    "rails": "Ruby on Rails",
    "c++": "C++",
    "cpp": "C++",
    "c#": "C#",
    "csharp": "C#",
    "swift": "Swift",
    "kotlin": "Kotlin",
    "php": "PHP",
    "scala": "Scala",
    "typescript": "TypeScript",
    "angular": "Angular",
    "angularjs": "Angular",
    "vue": "Vue.js",
    "vuejs": "Vue.js",
    "solidity": "Solidity",
    "elixir": "Elixir",
    "haskell": "Haskell",
    "perl": "Perl",
    "dart": "Dart",
    "zig": "Zig",
}


def _get_provider(is_demo: bool | None = None) -> LLMProvider | None:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        try:
            from app.config import settings
            api_key = settings.gemini_api_key or ""
        except Exception:
            pass

    if api_key and api_key.strip():
        try:
            prov = GeminiProvider()
            if prov.api_key:
                return prov
        except Exception as e:
            logger.error(f"[Copilot] GeminiProvider initialization failed: {e}")

    if is_demo is False:
        return None
    return DemoProvider()


def extract_queried_skill(question: str, skills_list: list[dict]) -> dict | None:
    """Detect if the user is asking about a specific technical skill or programming language."""
    if not question:
        return None
    q_lower = question.lower()

    # 1. Match against indexed skills (and synonyms) using word boundaries
    for s in skills_list:
        name = s.get("name", "")
        if not name:
            continue
        pattern = r"\b" + re.escape(name.lower()) + r"\b"
        if re.search(pattern, q_lower):
            return {"type": "indexed", "skill": s, "name": name}
        for syn in s.get("synonyms", []):
            if not syn:
                continue
            syn_pat = r"\b" + re.escape(syn.lower()) + r"\b"
            if re.search(syn_pat, q_lower):
                return {"type": "indexed", "skill": s, "name": name}

    # 2. Check specific Go/Golang patterns
    if (
        re.search(r"\b(golang|go\s*lang)\b", q_lower)
        or re.search(r"\bgo\s+(developer|engineer|programmer|language|jobs?|demand|requirement|role|stack|tech)\b", q_lower)
        or re.search(r"\b(?:requirement|demand|jobs?|role)\s+(?:of|for|in)?\s+go\b", q_lower)
        or re.search(r"\b(developer|engineer|programmer)\s+(?:in|for|of)?\s*go\b", q_lower)
    ):
        return {"type": "unindexed", "name": "Go / Golang"}

    # 3. Match against known unindexed languages/frameworks
    for term, label in KNOWN_EXTERNAL_TECHS.items():
        if term in ("go", "golang", "go lang"):
            continue
        pattern = r"\b" + re.escape(term) + r"\b"
        if re.search(pattern, q_lower):
            return {"type": "unindexed", "name": label}

    # 4. Generic skill/developer query extraction pattern
    m = re.search(r"\b(?:requirement|demand|jobs?|skills?|career)\s+(?:of|for|in)?\s+(?:a\s+|an\s+)?([a-zA-Z0-9#\+\.\-]+)\s+(?:developer|engineer|programmer|specialist|language|role)\b", q_lower)
    if m:
        word = m.group(1).strip()
        if word not in ("a", "an", "the", "good", "any", "lead", "senior", "junior"):
            return {"type": "unindexed", "name": word.capitalize()}

    m2 = re.search(r"\b([a-zA-Z0-9#\+\.\-]+)\s+(?:developer|engineer|programmer|language)\b", q_lower)
    if m2:
        word = m2.group(1).strip()
        if word not in ("a", "an", "the", "good", "software", "web", "cloud", "frontend", "backend", "fullstack", "mobile"):
            return {"type": "unindexed", "name": word.capitalize()}

    return None


def _build_context(
    role: str,
    question: str = "",
    district: str | None = None,
    student_id: str | None = None,
    context_data: dict | None = None,
    current_user: dict | None = None,
    is_demo: bool = False,
) -> dict[str, Any]:
    """Fetch relevant structured data to ground the response accurately without polluting query context."""
    try:
        from app.services.gap_engine import compute_gaps
        from app.services.district_service import get_all_districts, get_district_plan

        if is_demo:
            from app.db import get_demo
            skills = get_demo("skills")
            jobs = get_demo("jobs")
            job_skills = get_demo("job_skills")
            courses = get_demo("courses")
            course_skills = get_demo("course_skills")
            skills_ok = True
            jobs_ok = True
            job_skills_ok = True
            courses_ok = True
            course_skills_ok = True
        else:
            from app.repositories import supabase_repository
            skills_ok = False
            jobs_ok = False
            job_skills_ok = False
            courses_ok = False
            course_skills_ok = False
            try:
                skills = supabase_repository.list_skills() or []
                skills_ok = True
            except Exception as e:
                logger.warning(f"[Copilot] Failed to fetch skills: {e}")
                skills = []
            try:
                jobs = supabase_repository.list_jobs(limit=500) or []
                jobs_ok = True
            except Exception as e:
                logger.warning(f"[Copilot] Failed to fetch jobs: {e}")
                jobs = []
            job_ids = [j.get("id") for j in jobs if j.get("id")]
            try:
                job_skills = supabase_repository.list_job_skills(job_ids=job_ids) if job_ids else []
                job_skills_ok = True
            except Exception as e:
                logger.warning(f"[Copilot] Failed to fetch job_skills: {e}")
                job_skills = []
            try:
                courses = supabase_repository.list_courses(limit=500) or []
                courses_ok = True
            except Exception as e:
                logger.warning(f"[Copilot] Failed to fetch courses: {e}")
                courses = []
            course_ids = [c.get("id") for c in courses if c.get("id")]
            try:
                course_skills = supabase_repository.list_course_skills(course_ids=course_ids) if course_ids else []
                course_skills_ok = True
            except Exception as e:
                logger.warning(f"[Copilot] Failed to fetch course_skills: {e}")
                course_skills = []

        # Check for district mentions or explicit district parameter
        q_lower = question.lower() if question else ""
        focused_district = None
        target_district_name = None

        if district and district.strip():
            target_district_name = district.strip()
        elif question:
            for d in get_all_districts(is_demo=is_demo):
                dname = d.get("name", "")
                if dname and dname.lower() in q_lower:
                    target_district_name = dname
                    break

        if target_district_name:
            plan = get_district_plan(target_district_name, is_demo=is_demo)
            focused_district = {
                "district": target_district_name,
                "total_jobs": plan.get("total_jobs", 0),
                "total_courses": plan.get("total_courses", 0),
                "total_enrolment": plan.get("total_enrolment", 0),
                "top_roles": plan.get("top_roles", [])[:5],
                "top_skills": plan.get("top_skills", [])[:5],
                "skill_gaps": plan.get("skill_gaps", [])[:5],
                "local_courses": plan.get("local_courses", [])[:5],
                "industry_demand": plan.get("industry_demand", [])[:4],
            }

        # Check if query targets a specific skill (from question or context_data)
        queried_skill_info = extract_queried_skill(question, skills)
        if not queried_skill_info and context_data and context_data.get("topic"):
            queried_skill_info = extract_queried_skill(str(context_data["topic"]), skills)

        context: dict[str, Any] = {
            "query_type": "general_overview",
            "top_skill_gaps": compute_gaps(is_demo=is_demo)[:10],
            "total_skills_tracked": len(skills),
            "total_jobs": len(jobs),
        }

        authoritative_ready = is_demo or (
            skills_ok and jobs_ok and job_skills_ok and course_skills_ok and bool(skills) and bool(jobs)
        )
        if not is_demo and not authoritative_ready:
            context["authoritative_data_status"] = "empty_or_unindexed"

        if queried_skill_info:
            if queried_skill_info["type"] == "indexed" and (is_demo or (skills_ok and jobs_ok and job_skills_ok and course_skills_ok)):
                skill_obj = queried_skill_info.get("skill", {})
                sid = skill_obj.get("id", "")
                sname = skill_obj.get("name", "")

                matching_js = [js for js in job_skills if js["skill_id"] == sid]
                matching_job_ids = {js["job_id"] for js in matching_js}
                matching_jobs = [j for j in jobs if j["id"] in matching_job_ids]

                total_jobs_count = len(jobs)
                demand_count = len(matching_jobs)
                demand_pct = round((demand_count / total_jobs_count) * 100) if total_jobs_count else 0

                district_counts = dict(Counter(j.get("district", "Unknown") for j in matching_jobs).most_common(5))

                all_gaps = compute_gaps(focused_district.get("district") if focused_district else None, is_demo=is_demo)
                gap_entry = next((g for g in all_gaps if g["skill_id"] == sid), None)

                teaching_course_ids = {cs["course_id"] for cs in course_skills if cs["skill_id"] == sid}
                teaching_courses = [
                    {
                        "id": c["id"],
                        "name": c.get("name", ""),
                        "institute": c.get("institute", ""),
                        "district": c.get("district", ""),
                    }
                    for c in courses if c["id"] in teaching_course_ids
                ][:5]

                context["query_type"] = "skill_specific"
                context["data_available_for_skill"] = True
                context["queried_skill"] = {
                    "id": sid,
                    "name": sname,
                    "category": skill_obj.get("category", "General"),
                    "nsqf_level": skill_obj.get("nsqf_level"),
                    "found_in_dataset": True,
                    "demand_count": demand_count,
                    "total_jobs_tracked": total_jobs_count,
                    "demand_pct": demand_pct,
                    "coverage_pct": gap_entry["coverage_pct"] if gap_entry else 0,
                    "gap_pct": gap_entry["gap_pct"] if gap_entry else 0,
                    "priority": gap_entry["priority"] if gap_entry else "LOW",
                    "district_distribution": district_counts,
                    "sample_courses": teaching_courses,
                }
            else:
                tech_name = queried_skill_info.get("skill", {}).get("name", "") if queried_skill_info.get("skill") else queried_skill_info.get("name", "")
                context["query_type"] = "skill_specific"
                context["data_available_for_skill"] = False
                dataset_label = "Maharashtra 10-district demo dataset" if is_demo else "authoritative database"
                if queried_skill_info.get("type") == "indexed" and not (skills_ok and jobs_ok and job_skills_ok and course_skills_ok):
                    msg = f"Authoritative metrics for '{tech_name}' are currently unavailable due to an upstream query failure."
                else:
                    msg = f"No verified job postings or accredited state courses for '{tech_name}' exist in the {dataset_label}."
                context["queried_skill"] = {
                    "name": tech_name,
                    "found_in_dataset": False,
                    "verified_job_count": 0,
                    "verified_course_count": 0,
                    "message": msg,
                }

        # Attach Recommendation Handoff data if supplied from frontend modal
        if context_data and isinstance(context_data, dict):
            context["recommendation_handoff"] = {
                "topic": context_data.get("topic"),
                "recommendation_title": context_data.get("recommendation_title"),
                "target_role": context_data.get("target_role"),
                "student_name": context_data.get("student_name"),
                "student_id": context_data.get("student_id") or student_id,
                "missing_prerequisites": context_data.get("missing_prerequisites", []),
                "demand_signals": context_data.get("demand_signals"),
                "future_forecast": context_data.get("future_forecast"),
                "employer_consensus": context_data.get("employer_consensus"),
                "relevant_courses": context_data.get("relevant_courses", []),
                "source": context_data.get("source", "SkillSetu Grounded Labour Intelligence"),
            }
            if context.get("queried_skill"):
                context["query_type"] = "skill_recommendation"

        # Phase 17 & 18: Grounded Student Recommendation Context
        effective_student_id = student_id or (context_data.get("student_id") if context_data and isinstance(context_data, dict) else None)
        if effective_student_id and role == "student":
            # SECURITY CRITICAL: Authorize effective student ID before compute_career_recommendations()
            from app.routers.student import _verify_student_recommendations_access
            _verify_student_recommendations_access(effective_student_id, current_user)
            try:
                from app.services.career_recommendation_engine import compute_career_recommendations
                student_rec = compute_career_recommendations(effective_student_id, is_demo=is_demo)
                top_role = student_rec.get("top_recommendation", {}).get("role_name", "")
                missing_skills = student_rec.get("top_recommendation", {}).get("missing_skills", [])
                matching_skills = student_rec.get("top_recommendation", {}).get("matching_skills", [])

                queried_name = context.get("queried_skill", {}).get("name", "")
                is_missing = False
                is_acquired = False
                if queried_name:
                    is_missing = any(m.lower() == queried_name.lower() for m in missing_skills)
                    is_acquired = any(m.lower() == queried_name.lower() for m in matching_skills)
                    if not is_acquired and not is_missing:
                        # Check if required in roadmap or target role benchmark
                        roadmap_skills = [
                            st.get("skill_name", "").lower()
                            for st in student_rec.get("personalized_roadmap", [])
                            if st.get("skill_name")
                        ]
                        role_missing = []
                        target_goal = student_rec.get("target_career_goal") or top_role
                        for r_def in student_rec.get("recommended_careers", []):
                            if r_def.get("role_name", "").lower() in (top_role.lower(), target_goal.lower()):
                                role_missing.extend([s.lower() for s in r_def.get("missing_skills", [])])
                        is_missing = any(queried_name.lower() == r for r in roadmap_skills) or any(
                            queried_name.lower() == rm for rm in role_missing
                        )

                context["student_recommendation_context"] = {
                    "student_id": effective_student_id,
                    "candidate_name": student_rec.get("candidate_name"),
                    "district": student_rec.get("district"),
                    "target_career_goal": student_rec.get("target_career_goal") or top_role,
                    "readiness_score": student_rec.get("overall_readiness", {}).get("score"),
                    "readiness_level": student_rec.get("overall_readiness", {}).get("level"),
                    "readiness_headline": student_rec.get("overall_readiness", {}).get("headline"),
                    "current_skills": [s.get("skill_name") for s in student_rec.get("current_skill_profile", [])],
                    "top_recommended_role": top_role,
                    "top_role_match_pct": student_rec.get("top_recommendation", {}).get("match_pct"),
                    "matching_skills": matching_skills,
                    "missing_skills": missing_skills,
                    "is_queried_skill_missing": is_missing,
                    "is_queried_skill_acquired": is_acquired,
                    "validated_openings_count": student_rec.get("top_recommendation", {}).get("validated_openings_count", 0),
                    "validated_employer_signals": student_rec.get("top_recommendation", {}).get("validated_employer_signals", [])[:3],
                    "matched_government_opportunities": student_rec.get("top_recommendation", {}).get("matched_government_opportunities", [])[:3],
                    "explanation_reasons": student_rec.get("top_recommendation", {}).get("explanation_reasons", []),
                    "personalized_roadmap": [
                        {"step": st.get("step"), "skill": st.get("skill_name"), "why": st.get("why_learn")}
                        for st in student_rec.get("personalized_roadmap", [])[:4]
                    ],
                }
                if context.get("queried_skill"):
                    context["query_type"] = "skill_recommendation"
            except Exception as rec_err:
                logger.warning(f"[Copilot] Failed to attach student recommendation context: {rec_err}")

        if role == "student":
            if is_demo:
                from app.db import get_demo
                context["student_profiles"] = [
                    {
                        "name": p.get("name") or p.get("full_name", ""),
                        "target_role": p.get("target_role", ""),
                        "match": p.get("skill_match_pct", 0),
                    }
                    for p in get_demo("student_profiles")
                    if isinstance(p, dict)
                ]
            else:
                caller_id = (current_user and current_user.get("id")) or student_id
                if caller_id:
                    from app.repositories import supabase_repository
                    try:
                        p = supabase_repository.get_student_profile(caller_id)
                        if p:
                            context["student_profiles"] = [
                                {"name": p.get("name", ""), "target_role": p.get("target_role", ""), "match": p.get("skill_match_pct", 0)}
                            ]
                        else:
                            context["student_profiles"] = []
                    except Exception:
                        context["student_profiles"] = []
                else:
                    context["student_profiles"] = []
        elif role == "employee":
            caller_id = (current_user and current_user.get("id")) or student_id
            if caller_id:
                from app.repositories import supabase_repository
                try:
                    ep = supabase_repository.get_employee_profile(caller_id)
                    if ep:
                        context["employee_profile"] = {
                            "name": ep.get("full_name") or ep.get("name", ""),
                            "current_role": ep.get("current_role", ""),
                            "years_of_experience": ep.get("years_of_experience", 0),
                            "industry": ep.get("industry", ""),
                            "target_role": ep.get("target_role", ""),
                            "preferred_location": ep.get("preferred_location", ""),
                            "skills": [
                                (s.get("skill_name") or s.get("name", ""))
                                for s in ep.get("skills", [])
                                if isinstance(s, dict)
                            ],
                            "certifications": [
                                (c.get("name") or "")
                                for c in ep.get("certifications", [])
                                if isinstance(c, dict)
                            ],
                        }
                    else:
                        context["employee_profile"] = None
                except Exception:
                    context["employee_profile"] = None
            else:
                context["employee_profile"] = None
        elif role == "government":
            from app.services.district_service import get_all_districts
            context["districts"] = get_all_districts(is_demo=is_demo)
        elif role == "institute":
            context["institutes_summary"] = {
                "total_courses": len(courses),
                "sample_institutes": sorted(list(set(c.get("institute", "") for c in courses if c.get("institute"))))[:6],
            }
        elif role == "employer":
            if is_demo:
                from app.db import get_demo
                feedback = get_demo("employer_feedback")
                context["pending_validations"] = len([f for f in feedback if f.get("status") == "pending"])
                context["confirmed"] = len([f for f in feedback if f.get("status") == "confirmed"])
            else:
                from app.repositories import supabase_repository
                try:
                    feedback = supabase_repository.list_employer_feedback() or []
                    context["pending_validations"] = len([f for f in feedback if f.get("status") == "pending"])
                    context["confirmed"] = len([f for f in feedback if f.get("status") == "confirmed"])
                except Exception:
                    context["pending_validations"] = 0
                    context["confirmed"] = 0

        if focused_district:
            context["focused_district"] = focused_district

        if question:
            student_profiles_list = get_demo("student_profiles") if is_demo else []
            for p in student_profiles_list:
                target = p.get("target_role", "")
                if target and target.lower() in q_lower:
                    skills_map = {s.get("id"): s.get("name", "") for s in skills if isinstance(s, dict) and s.get("id")}
                    context["focused_career_role"] = {
                        "role": target,
                        "required_skills": [skills_map.get(sid, sid) for sid in p.get("required_skills", [])],
                        "roadmap": [skills_map.get(sid, sid) for sid in p.get("roadmap", [])],
                    }
                    break

        return context
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"[Copilot] Failed to build context: {e}")
        return {}


async def handle_question(
    question: str,
    role: str = "student",
    district: str | None = None,
    student_id: str | None = None,
    context_data: dict | None = None,
    current_user: dict | None = None,
    is_demo: bool | None = None,
) -> dict[str, Any]:
    if is_demo is False:
        is_demo_mode = False
    elif is_demo is True or is_explicit_demo_mode(is_demo):
        is_demo_mode = True
    else:
        is_demo_mode = student_id is not None and is_demo_student_id(student_id)
    provider = _get_provider(is_demo=is_demo_mode)
    context = _build_context(role, question, district, student_id, context_data, current_user, is_demo=is_demo_mode)
    is_live_ai = isinstance(provider, GeminiProvider)

    logger.info(f"[Copilot] Request role={role}, district={district}, provider={provider.__class__.__name__ if provider else 'None'}, is_live={is_live_ai}, is_demo={is_demo_mode}")

    if not is_demo_mode:
        is_empty_or_unindexed = context.get("authoritative_data_status") == "empty_or_unindexed"
        has_profile_context = bool(
            context.get("student_recommendation_context")
            or context.get("employee_profile")
        )
        is_market_intelligence_claim = bool(
            context.get("queried_skill")
            or context.get("focused_district")
            or not has_profile_context
        )

        if is_empty_or_unindexed and is_market_intelligence_claim:
            return {
                "answer": "Authoritative labour market intelligence is currently unavailable or unindexed in Real Data mode. Live AI generation without verified data is restricted to prevent inaccurate guidance.",
                "role": role,
                "student_id": student_id,
                "demo_mode": False,
                "data_grounded": False,
                "model": "Real Data Service (No Data)",
                "provenance_label": "⚠️ No Authoritative Data",
            }
        if not is_live_ai or provider is None:
            return {
                "answer": "AI Copilot live inference is temporarily unavailable because the Gemini AI service is not configured or reachable. In Real Data mode, synthetic factual fallbacks are disabled to prevent inaccurate labour market intelligence.",
                "role": role,
                "student_id": student_id,
                "demo_mode": False,
                "data_grounded": bool(context),
                "model": "Real Data Service (Offline)",
                "provenance_label": "⚠️ Service Offline",
            }
        try:
            answer = await provider.generate(question, context)
            if is_empty_or_unindexed:
                prov_label = "✨ Generated by Gemini AI (Profile-Only Guidance)"
                is_grounded = False
            else:
                prov_label = "✨ Generated by Gemini AI (Grounded in Authoritative Data)"
                is_grounded = bool(context)
            return {
                "answer": answer,
                "role": role,
                "student_id": student_id,
                "demo_mode": False,
                "data_grounded": is_grounded,
                "model": getattr(provider, "model", "gemini-3.6-flash"),
                "provenance_label": prov_label,
            }
        except Exception as e:
            err_msg = str(e)
            logger.error(f"[Copilot] Live generation error in real mode: {err_msg}")
            return {
                "answer": "AI Copilot live inference encountered an error. In Real Data mode, synthetic factual fallbacks are disabled.",
                "role": role,
                "student_id": student_id,
                "demo_mode": False,
                "data_grounded": bool(context),
                "model": "Real Data Service (Error)",
                "provenance_label": "⚠️ Service Error",
            }

    # EXPLICIT DEMO MODE
    if is_live_ai and provider is not None:
        try:
            answer = await provider.generate(question, context)
            return {
                "answer": answer,
                "role": role,
                "student_id": student_id,
                "demo_mode": False,
                "data_grounded": bool(context),
                "model": getattr(provider, "model", "gemini-3.6-flash"),
                "provenance_label": "✨ Generated by Gemini AI",
            }
        except Exception as e:
            logger.warning(f"[Copilot] Live generation failed in demo mode, falling back to DemoProvider: {e}")

    demo_prov = DemoProvider()
    answer = await demo_prov.generate(question, context)
    return {
        "answer": answer,
        "role": role,
        "student_id": student_id,
        "demo_mode": True,
        "data_grounded": bool(context),
        "model": "Rule-Based Offline Intelligence",
        "provenance_label": "🛡️ Grounded Deterministic Intelligence (Offline Demo Mode)",
    }

