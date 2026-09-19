from collections import Counter
from datetime import datetime, timezone
from typing import Any

from app.db import _cache, init_db
from app.repositories.supabase_repository import (
    list_placement_outcomes,
    list_placement_employer_feedback,
)


VALID_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "TRAINING_COMPLETED": {"PLACEMENT_PENDING", "PLACED", "NOT_PLACED", "WITHDRAWN", "UNKNOWN"},
    "PLACEMENT_PENDING": {"PLACED", "NOT_PLACED", "WITHDRAWN", "UNKNOWN"},
    "PLACED": {"EMPLOYED", "EMPLOYER_FEEDBACK_PENDING", "FEEDBACK_RECEIVED", "WITHDRAWN", "UNKNOWN"},
    "EMPLOYED": {"EMPLOYER_FEEDBACK_PENDING", "FEEDBACK_RECEIVED", "WITHDRAWN", "UNKNOWN"},
    "EMPLOYER_FEEDBACK_PENDING": {"FEEDBACK_RECEIVED", "WITHDRAWN", "UNKNOWN"},
    "FEEDBACK_RECEIVED": {"FEEDBACK_RECEIVED"},
    "NOT_PLACED": {"PLACEMENT_PENDING", "PLACED", "WITHDRAWN", "UNKNOWN"},
    "WITHDRAWN": {"TRAINING_COMPLETED", "PLACEMENT_PENDING", "PLACED", "UNKNOWN"},
    "UNKNOWN": {"TRAINING_COMPLETED", "PLACEMENT_PENDING", "PLACED", "NOT_PLACED", "WITHDRAWN"},
}


def validate_placement_lifecycle_transition(current_status: str, new_status: str) -> bool:
    curr = current_status.strip().upper() if current_status else "TRAINING_COMPLETED"
    target = new_status.strip().upper() if new_status else ""
    if curr == target:
        return True
    allowed = VALID_STATUS_TRANSITIONS.get(curr, set())
    return target in allowed


def get_confidence_tier(candidate_count: int) -> str:
    if candidate_count == 0:
        return "INSUFFICIENT_EVIDENCE"
    if candidate_count < 5:
        return "LOW"
    if candidate_count < 15:
        return "MODERATE"
    return "HIGH"


def compute_course_placement_performance(course_id: str, is_demo: bool | None = None) -> dict[str, Any]:
    if not _cache:
        init_db()

    try:
        outcomes = list_placement_outcomes(course_id=course_id, is_demo=is_demo, limit=5000)
    except Exception:
        all_cached = _cache.get("placement_outcomes", [])
        outcomes = [
            o for o in all_cached
            if o.get("course_id") == course_id and (is_demo is None or o.get("is_demo") == is_demo)
        ]

    total_candidates = len(outcomes)
    confidence_tier = get_confidence_tier(total_candidates)

    placed_statuses = {"PLACED", "EMPLOYED", "EMPLOYER_FEEDBACK_PENDING", "FEEDBACK_RECEIVED"}
    employed_statuses = {"EMPLOYED", "FEEDBACK_RECEIVED"}

    placed_outcomes = [o for o in outcomes if o.get("status") in placed_statuses]
    employed_outcomes = [o for o in outcomes if o.get("status") in employed_statuses]

    placed_count = len(placed_outcomes)
    employed_count = len(employed_outcomes)

    placement_rate = round((placed_count / max(1, total_candidates)) * 100, 1) if total_candidates > 0 else 0.0
    employment_conversion_rate = round((employed_count / max(1, placed_count)) * 100, 1) if placed_count > 0 else 0.0

    salaries = [o.get("salary_annual_inr") for o in placed_outcomes if o.get("salary_annual_inr") and o.get("salary_annual_inr") > 0]
    avg_salary_inr = round(sum(salaries) / len(salaries)) if salaries else 0
    median_salary_inr = sorted(salaries)[len(salaries) // 2] if salaries else 0

    employer_counts = Counter(o.get("employer_name") for o in placed_outcomes if o.get("employer_name"))
    top_employers = [{"employer_name": name, "count": count} for name, count in employer_counts.most_common(5)]

    role_counts = Counter(o.get("role_title") for o in placed_outcomes if o.get("role_title"))
    top_roles = [{"role_title": role, "count": count} for role, count in role_counts.most_common(5)]

    skills_counter = Counter()
    for o in placed_outcomes:
        skills = o.get("skills_utilized", [])
        if isinstance(skills, list):
            for s in skills:
                if isinstance(s, str) and s.strip():
                    skills_counter[s.strip()] += 1
    top_skills_utilized = [{"skill": s, "count": c} for s, c in skills_counter.most_common(6)]

    outcome_ids = {o.get("id") for o in outcomes if o.get("id")}
    try:
        feedback_records = list_placement_employer_feedback(is_demo=is_demo, limit=5000)
        course_feedback = [f for f in feedback_records if f.get("placement_outcome_id") in outcome_ids]
    except Exception:
        all_fb = _cache.get("placement_employer_feedback", [])
        course_feedback = [
            f for f in all_fb
            if f.get("placement_outcome_id") in outcome_ids and (is_demo is None or f.get("is_demo") == is_demo)
        ]

    feedback_count = len(course_feedback)
    if feedback_count > 0:
        scores = [f.get("skill_adequacy_score") for f in course_feedback if f.get("skill_adequacy_score")]
        avg_adequacy_score = round(sum(scores) / len(scores), 2) if scores else 0.0

        readiness_counts = Counter(f.get("practical_readiness") for f in course_feedback if f.get("practical_readiness"))
        missing_skills_counter = Counter()
        for f in course_feedback:
            missing = f.get("missing_skills", [])
            if isinstance(missing, list):
                for ms in missing:
                    if isinstance(ms, str) and ms.strip():
                        missing_skills_counter[ms.strip()] += 1

        top_missing_skills = [
            {"skill_name": s, "report_count": c}
            for s, c in missing_skills_counter.most_common(5)
        ]
        relevance_counts = Counter(f.get("training_relevance") for f in course_feedback if f.get("training_relevance"))
    else:
        avg_adequacy_score = 0.0
        readiness_counts = Counter()
        top_missing_skills = []
        relevance_counts = Counter()

    provenance_counts = Counter(o.get("data_provenance", "DEMO_SYNTHETIC") for o in outcomes)

    return {
        "course_id": course_id,
        "total_candidates_tracked": total_candidates,
        "placed_count": placed_count,
        "employed_count": employed_count,
        "placement_rate_pct": placement_rate,
        "employment_conversion_rate_pct": employment_conversion_rate,
        "average_salary_annual_inr": avg_salary_inr,
        "median_salary_annual_inr": median_salary_inr,
        "confidence_tier": confidence_tier,
        "has_statistically_significant_data": confidence_tier in ("MODERATE", "HIGH"),
        "top_hiring_employers": top_employers,
        "top_hiring_roles": top_roles,
        "top_skills_utilized": top_skills_utilized,
        "feedback_summary": {
            "total_feedback_received": feedback_count,
            "average_skill_adequacy_score": avg_adequacy_score,
            "practical_readiness_breakdown": dict(readiness_counts),
            "training_relevance_breakdown": dict(relevance_counts),
            "employer_reported_missing_skills": top_missing_skills,
        },
        "provenance_breakdown": dict(provenance_counts),
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


def compute_skill_placement_signals(is_demo: bool | None = None) -> dict[str, Any]:
    if not _cache:
        init_db()

    try:
        outcomes = list_placement_outcomes(is_demo=is_demo, limit=10000)
    except Exception:
        outcomes = [
            o for o in _cache.get("placement_outcomes", [])
            if is_demo is None or o.get("is_demo") == is_demo
        ]

    try:
        feedback = list_placement_employer_feedback(is_demo=is_demo, limit=10000)
    except Exception:
        feedback = [
            f for f in _cache.get("placement_employer_feedback", [])
            if is_demo is None or f.get("is_demo") == is_demo
        ]

    high_value_skills_counter = Counter()
    missing_skills_counter = Counter()

    for o in outcomes:
        if o.get("status") in {"PLACED", "EMPLOYED", "FEEDBACK_RECEIVED"}:
            skills = o.get("skills_utilized", [])
            if isinstance(skills, list):
                for s in skills:
                    if isinstance(s, str) and s.strip():
                        high_value_skills_counter[s.strip()] += 1

    for f in feedback:
        missing = f.get("missing_skills", [])
        if isinstance(missing, list):
            for ms in missing:
                if isinstance(ms, str) and ms.strip():
                    missing_skills_counter[ms.strip()] += 1

    return {
        "most_placed_skills": [
            {"skill": s, "placement_frequency": c}
            for s, c in high_value_skills_counter.most_common(10)
        ],
        "employer_reported_deficits": [
            {"skill": s, "deficit_reports": c}
            for s, c in missing_skills_counter.most_common(10)
        ],
        "total_outcomes_analyzed": len(outcomes),
        "total_feedback_analyzed": len(feedback),
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


def compute_statewide_placement_analytics(
    district: str | None = None,
    is_demo: bool | None = None,
) -> dict[str, Any]:
    if not _cache:
        init_db()

    try:
        outcomes = list_placement_outcomes(district=district, is_demo=is_demo, limit=10000)
    except Exception:
        outcomes = [
            o for o in _cache.get("placement_outcomes", [])
            if (not district or o.get("district", "").lower() == district.lower())
            and (is_demo is None or o.get("is_demo") == is_demo)
        ]

    total_tracked = len(outcomes)
    placed_statuses = {"PLACED", "EMPLOYED", "EMPLOYER_FEEDBACK_PENDING", "FEEDBACK_RECEIVED"}
    placed_count = sum(1 for o in outcomes if o.get("status") in placed_statuses)
    overall_rate = round((placed_count / max(1, total_tracked)) * 100, 1) if total_tracked > 0 else 0.0

    salaries = [o.get("salary_annual_inr") for o in outcomes if o.get("salary_annual_inr") and o.get("salary_annual_inr") > 0]
    avg_salary = round(sum(salaries) / len(salaries)) if salaries else 0

    district_counts = Counter(o.get("district") for o in outcomes if o.get("district"))
    district_breakdown = []
    for d, total in district_counts.items():
        d_outcomes = [o for o in outcomes if o.get("district") == d]
        d_placed = sum(1 for o in d_outcomes if o.get("status") in placed_statuses)
        d_salaries = [o.get("salary_annual_inr") for o in d_outcomes if o.get("salary_annual_inr") and o.get("salary_annual_inr") > 0]
        district_breakdown.append({
            "district": d,
            "total_candidates": total,
            "placed_candidates": d_placed,
            "placement_rate_pct": round((d_placed / max(1, total)) * 100, 1),
            "average_salary_annual_inr": round(sum(d_salaries) / len(d_salaries)) if d_salaries else 0,
        })

    industry_counts = Counter(o.get("industry") for o in outcomes if o.get("industry"))
    industry_breakdown = []
    for ind, total in industry_counts.items():
        ind_outcomes = [o for o in outcomes if o.get("industry") == ind]
        ind_placed = sum(1 for o in ind_outcomes if o.get("status") in placed_statuses)
        industry_breakdown.append({
            "industry": ind,
            "total_candidates": total,
            "placed_candidates": ind_placed,
            "placement_rate_pct": round((ind_placed / max(1, total)) * 100, 1),
        })

    course_groups: dict[str, list[dict[str, Any]]] = {}
    for o in outcomes:
        cid = o.get("course_id")
        if cid:
            course_groups.setdefault(cid, []).append(o)

    course_performance_list = []
    for cid, c_outcomes in course_groups.items():
        c_placed = sum(1 for o in c_outcomes if o.get("status") in placed_statuses)
        course_performance_list.append({
            "course_id": cid,
            "course_name": c_outcomes[0].get("course_name") or cid,
            "institute_name": c_outcomes[0].get("institute_name") or "Unknown",
            "total_candidates": len(c_outcomes),
            "placed_candidates": c_placed,
            "placement_rate_pct": round((c_placed / max(1, len(c_outcomes))) * 100, 1),
            "confidence_tier": get_confidence_tier(len(c_outcomes)),
        })

    course_performance_list.sort(key=lambda x: x["placement_rate_pct"], reverse=True)

    return {
        "district_filter": district or "ALL",
        "total_candidates_tracked": total_tracked,
        "placed_candidates": placed_count,
        "overall_placement_rate_pct": overall_rate,
        "average_salary_annual_inr": avg_salary,
        "district_breakdown": district_breakdown,
        "industry_breakdown": industry_breakdown,
        "top_performing_courses": course_performance_list[:5],
        "underperforming_courses": [c for c in reversed(course_performance_list) if c["placement_rate_pct"] < 60][:5],
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
