from __future__ import annotations

from typing import Any
from app.routers.gov_opportunities import _is_expired
from app.services.career_recommendation_engine import _match_skills


def match_student_to_jobs(
    profile: dict[str, Any],
    jobs: list[dict[str, Any]],
    job_skills_map: dict[str, list[str]] | None = None,
) -> list[dict[str, Any]]:
    current_skills_raw = profile.get("skills", []) or profile.get("current_skills", [])
    student_skills_normalized = []
    for s in current_skills_raw:
        if isinstance(s, dict):
            name = s.get("skill_name") or s.get("name") or s.get("skill_id") or ""
            prof = s.get("proficiency") or "intermediate"
            student_skills_normalized.append({
                "skill_name": str(name),
                "proficiency": str(prof),
            })
        elif s:
            student_skills_normalized.append({
                "skill_name": str(s),
                "proficiency": "intermediate",
            })

    results = []
    js_map = job_skills_map or {}

    for job in jobs:
        if job.get("is_active") is False or str(job.get("status", "active")).lower() != "active":
            continue
        if str(job.get("verification_status", "")).upper() in ("REJECTED", "UNVERIFIED"):
            continue
        if _is_expired(job.get("deadline")):
            continue

        jid = job.get("id") or ""
        req_skills: list[str] = []
        if jid in js_map and js_map[jid]:
            req_skills = [str(sk) for sk in js_map[jid] if sk]
        elif job.get("skills"):
            req_skills = [str(sk) for sk in job["skills"] if sk]
        elif job.get("required_skills"):
            req_skills = [str(sk) for sk in job["required_skills"] if sk]

        matched_skills, missing_skills, match_pct = _match_skills(
            student_skills_normalized,
            req_skills,
        )

        results.append({
            "job": job,
            "job_id": jid,
            "title": job.get("title", ""),
            "company": job.get("company", ""),
            "district": job.get("district", ""),
            "industry": job.get("industry", ""),
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "skill_gap": missing_skills,
            "match_score": match_pct,
            "match_percentage": match_pct,
            "eligibility": "ELIGIBLE" if match_pct >= 40 else "SKILL_GAP",
        })

    results.sort(key=lambda x: (x["match_score"], str(x["job_id"])), reverse=True)
    return results
