from collections import Counter
from datetime import datetime, timezone
from typing import Any
import uuid

from app.core.data_mode import is_explicit_demo_mode
from app.db import _cache, init_db, save_institution_accreditation_record
from app.repositories.supabase_repository import (
    list_courses,
    list_placement_outcomes,
    list_placement_employer_feedback,
    list_institution_accreditations,
    get_latest_institution_accreditation,
)
from app.services.curriculum_engine import audit_all_courses

DEFAULT_TRAINING_COST_PER_SEAT_INR = 35000


def get_evidence_confidence_tier(candidate_count: int) -> str:
    if candidate_count == 0:
        return "INSUFFICIENT_EVIDENCE"
    if candidate_count < 5:
        return "LOW"
    if candidate_count < 10:
        return "MODERATE"
    return "HIGH"


def determine_accreditation_tier(
    composite_score: float,
    placement_rate: float,
    sample_count: int,
) -> str:
    if sample_count > 0 and placement_rate < 45.0:
        return "TIER_4_PERFORMANCE_WATCH"

    if sample_count < 10:
        if composite_score < 55.0:
            return "TIER_4_PERFORMANCE_WATCH"
        return "TIER_3_PROVISIONAL"

    if composite_score >= 85.0 and placement_rate >= 75.0:
        return "TIER_1_EXCELLENCE"
    if composite_score >= 70.0:
        return "TIER_2_ACCREDITED"
    if composite_score >= 55.0:
        return "TIER_3_PROVISIONAL"
    return "TIER_4_PERFORMANCE_WATCH"


def calculate_training_roi(
    placed_count: int,
    average_salary_inr: int,
    total_students: int,
    unit_cost_override: int | None = None,
    capital_grants_inr: int = 0,
) -> dict[str, Any]:
    cost_per_seat = unit_cost_override if unit_cost_override and unit_cost_override > 0 else DEFAULT_TRAINING_COST_PER_SEAT_INR
    operational_investment = total_students * cost_per_seat
    public_training_investment = operational_investment + max(0, capital_grants_inr)
    annual_economic_output = placed_count * max(0, average_salary_inr)

    if public_training_investment > 0:
        roi_multiplier = round(annual_economic_output / public_training_investment, 2)
    else:
        roi_multiplier = 1.0 if annual_economic_output > 0 else 0.0

    net_economic_benefit = annual_economic_output - public_training_investment

    if annual_economic_output > 0:
        payback_period_months = round((public_training_investment / annual_economic_output) * 12.0, 1)
    else:
        payback_period_months = 0.0

    return {
        "annual_economic_output_inr": annual_economic_output,
        "public_training_investment_inr": public_training_investment,
        "operational_training_cost_inr": operational_investment,
        "capital_grants_inr": capital_grants_inr,
        "cost_per_seat_applied_inr": cost_per_seat,
        "cost_assumptions_source": "COURSE_SPECIFIC_OVERRIDE" if unit_cost_override else "STATE_STANDARD_BENCHMARK",
        "net_economic_benefit_inr": net_economic_benefit,
        "roi_multiplier": roi_multiplier,
        "payback_period_months": payback_period_months,
    }


def compute_institute_scorecard(
    institute_id: str,
    institute_name: str | None = None,
    district: str | None = None,
    is_demo: bool | None = None,
) -> dict[str, Any]:
    if not _cache:
        init_db()

    clean_id = institute_id.strip()
    resolved_is_demo: bool = is_explicit_demo_mode(is_demo)

    if resolved_is_demo:
        try:
            all_courses = list_courses(is_demo=True) or []
            if not all_courses:
                all_courses = [
                    c for c in _cache.get("courses", [])
                    if c.get("is_demo") is True or c.get("source") == "DEMO_SYNTHETIC" or not c.get("source") or c.get("source") == "SEED_DATA"
                ]
        except Exception:
            all_courses = [
                c for c in _cache.get("courses", [])
                if c.get("is_demo") is True or c.get("source") == "DEMO_SYNTHETIC" or not c.get("source") or c.get("source") == "SEED_DATA"
            ]
    else:
        try:
            all_courses = list_courses(is_demo=False) or []
            if not all_courses:
                all_courses = [
                    c for c in _cache.get("courses", [])
                    if c.get("is_demo") is False and c.get("source") != "DEMO_SYNTHETIC"
                ]
        except Exception:
            all_courses = [
                c for c in _cache.get("courses", [])
                if c.get("is_demo") is False and c.get("source") != "DEMO_SYNTHETIC"
            ]

    matched_courses = [
        c for c in all_courses
        if (c.get("institute_id") and c["institute_id"].lower() == clean_id.lower())
        or (institute_name and (c.get("institute") or c.get("institute_name") or "").strip().lower() == institute_name.strip().lower())
    ]

    resolved_name = institute_name
    resolved_district = district
    if matched_courses:
        if not resolved_name:
            resolved_name = matched_courses[0].get("institute") or matched_courses[0].get("institute_name") or clean_id
        if not resolved_district:
            resolved_district = matched_courses[0].get("district")

    if not resolved_name:
        resolved_name = clean_id.replace("inst-", "").replace("-", " ").title()
    if not resolved_district:
        resolved_district = "Maharashtra"

    course_ids = {c["id"] for c in matched_courses if c.get("id")}

    if resolved_is_demo:
        try:
            outcomes = list_placement_outcomes(institute_id=clean_id, is_demo=True, limit=10000) or []
            if not outcomes and course_ids:
                all_outcomes = list_placement_outcomes(is_demo=True, limit=10000) or []
                outcomes = [o for o in all_outcomes if o.get("course_id") in course_ids]
            if not outcomes:
                all_outcomes = [
                    o for o in _cache.get("placement_outcomes", [])
                    if o.get("is_demo") is True or o.get("source") == "DEMO_SYNTHETIC" or o.get("is_demo") is None
                ]
                outcomes = [
                    o for o in all_outcomes
                    if (o.get("institute_id") and o["institute_id"].lower() == clean_id.lower())
                    or (o.get("course_id") in course_ids)
                ]
        except Exception:
            all_outcomes = [
                o for o in _cache.get("placement_outcomes", [])
                if o.get("is_demo") is True or o.get("source") == "DEMO_SYNTHETIC" or o.get("is_demo") is None
            ]
            outcomes = [
                o for o in all_outcomes
                if (o.get("institute_id") and o["institute_id"].lower() == clean_id.lower())
                or (o.get("course_id") in course_ids)
            ]
    else:
        try:
            outcomes = list_placement_outcomes(institute_id=clean_id, is_demo=False, limit=10000) or []
            if not outcomes and course_ids:
                all_outcomes = list_placement_outcomes(is_demo=False, limit=10000) or []
                outcomes = [o for o in all_outcomes if o.get("course_id") in course_ids]
            if not outcomes:
                all_outcomes = [
                    o for o in _cache.get("placement_outcomes", [])
                    if o.get("is_demo") is False and o.get("source") != "DEMO_SYNTHETIC"
                ]
                outcomes = [
                    o for o in all_outcomes
                    if (o.get("institute_id") and o["institute_id"].lower() == clean_id.lower())
                    or (o.get("course_id") in course_ids)
                ]
        except Exception:
            all_outcomes = [
                o for o in _cache.get("placement_outcomes", [])
                if o.get("is_demo") is False and o.get("source") != "DEMO_SYNTHETIC"
            ]
            outcomes = [
                o for o in all_outcomes
                if (o.get("institute_id") and o["institute_id"].lower() == clean_id.lower())
                or (o.get("course_id") in course_ids)
            ]

    total_candidates = len(outcomes)
    placed_statuses = {"PLACED", "EMPLOYED", "EMPLOYER_FEEDBACK_PENDING", "FEEDBACK_RECEIVED"}
    employed_statuses = {"EMPLOYED", "FEEDBACK_RECEIVED"}

    placed_outcomes = [
        o for o in outcomes
        if o.get("status") in placed_statuses
        and (o.get("verification_status") or "").upper() == "VERIFIED"
    ]
    employed_outcomes = [
        o for o in outcomes
        if o.get("status") in employed_statuses
        and (o.get("verification_status") or "").upper() == "VERIFIED"
    ]

    placed_count = len(placed_outcomes)
    employed_count = len(employed_outcomes)

    placement_rate = round((placed_count / max(1, total_candidates)) * 100, 1) if total_candidates > 0 else 0.0
    employment_conversion = round((employed_count / max(1, placed_count)) * 100, 1) if placed_count > 0 else 0.0

    placement_subscore = round((placement_rate * 0.7) + (employment_conversion * 0.3), 2) if total_candidates > 0 else 0.0

    salaries = [
        o.get("salary_annual_inr") for o in placed_outcomes
        if o.get("salary_annual_inr") and o.get("salary_annual_inr") > 0
    ]
    avg_salary_inr = round(sum(salaries) / len(salaries)) if salaries else 0
    median_salary_inr = sorted(salaries)[len(salaries) // 2] if salaries else 0

    if avg_salary_inr > 0:
        wage_subscore = min(100.0, max(10.0, round((avg_salary_inr / 600000.0) * 100.0, 2)))
    else:
        wage_subscore = 0.0

    try:
        audited = audit_all_courses(is_demo=resolved_is_demo) or []
        inst_audited = [
            a for a in audited
            if a.get("course_id") in course_ids
            or (a.get("institute_id") and a["institute_id"].lower() == clean_id.lower())
            or (a.get("institute") and a["institute"].strip().lower() == resolved_name.strip().lower())
        ]
    except Exception:
        inst_audited = []

    if inst_audited:
        modernity_scores = [a.get("modernity_score", 50) for a in inst_audited]
        curriculum_subscore = round(sum(modernity_scores) / len(modernity_scores), 2)
        total_equipment_grants = sum(a.get("total_equipment_budget_inr", 0) for a in inst_audited)
    else:
        curriculum_subscore = 50.0
        total_equipment_grants = 0

    outcome_ids = {o["id"] for o in outcomes if o.get("id")}
    if resolved_is_demo:
        try:
            all_feedback = list_placement_employer_feedback(is_demo=True, limit=10000) or []
            inst_feedback = [f for f in all_feedback if f.get("placement_outcome_id") in outcome_ids]
            if not inst_feedback:
                inst_feedback = [
                    f for f in _cache.get("placement_employer_feedback", [])
                    if f.get("placement_outcome_id") in outcome_ids and (f.get("is_demo") is True or f.get("source") == "DEMO_SYNTHETIC" or f.get("is_demo") is None)
                ]
        except Exception:
            inst_feedback = [
                f for f in _cache.get("placement_employer_feedback", [])
                if f.get("placement_outcome_id") in outcome_ids and (f.get("is_demo") is True or f.get("source") == "DEMO_SYNTHETIC" or f.get("is_demo") is None)
            ]
    else:
        try:
            all_feedback = list_placement_employer_feedback(is_demo=False, limit=10000) or []
            inst_feedback = [f for f in all_feedback if f.get("placement_outcome_id") in outcome_ids]
            if not inst_feedback:
                inst_feedback = [
                    f for f in _cache.get("placement_employer_feedback", [])
                    if f.get("placement_outcome_id") in outcome_ids and f.get("is_demo") is False and f.get("source") != "DEMO_SYNTHETIC"
                ]
        except Exception:
            inst_feedback = [
                f for f in _cache.get("placement_employer_feedback", [])
                if f.get("placement_outcome_id") in outcome_ids and f.get("is_demo") is False and f.get("source") != "DEMO_SYNTHETIC"
            ]

    inst_feedback = [
        f for f in inst_feedback
        if f.get("is_verified_employer") is True
        or f.get("data_provenance") == "EMPLOYER_VERIFIED"
    ]

    readiness_map = {"PRODUCTION_READY": 100.0, "NEEDS_SUPERVISION": 65.0, "UNPREPARED": 30.0}
    if inst_feedback:
        scores = [f.get("skill_adequacy_score", 3) for f in inst_feedback if f.get("skill_adequacy_score")]
        avg_adequacy = sum(scores) / len(scores) if scores else 3.0
        adequacy_pct = (avg_adequacy / 5.0) * 100.0
        readiness_vals = [readiness_map.get(f.get("practical_readiness", "NEEDS_SUPERVISION"), 65.0) for f in inst_feedback]
        readiness_avg = sum(readiness_vals) / len(readiness_vals) if readiness_vals else 65.0
        employer_subscore = round((adequacy_pct * 0.6) + (readiness_avg * 0.4), 2)
    else:
        employer_subscore = 50.0

    composite_score = round(
        (placement_subscore * 0.35)
        + (curriculum_subscore * 0.25)
        + (employer_subscore * 0.20)
        + (wage_subscore * 0.20),
        2,
    )

    confidence_tier = get_evidence_confidence_tier(total_candidates)
    tier = determine_accreditation_tier(composite_score, placement_rate, total_candidates)

    total_enrolment = sum(c.get("enrolment_count") or c.get("enrolment_capacity", 60) for c in matched_courses)
    effective_students = max(total_candidates, total_enrolment)

    roi_metrics = calculate_training_roi(
        placed_count=placed_count,
        average_salary_inr=avg_salary_inr,
        total_students=effective_students,
        capital_grants_inr=total_equipment_grants,
    )

    retained_6m = sum(1 for o in placed_outcomes if o.get("retention_status") in ("6_MONTH_RETAINED", "12_MONTH_RETAINED"))
    retained_12m = sum(1 for o in placed_outcomes if o.get("retention_status") == "12_MONTH_RETAINED")
    attrited = sum(1 for o in placed_outcomes if o.get("retention_status") == "ATTRITED")
    retention_rate_6m = min(100.0, round((retained_6m / max(1, placed_count)) * 100, 1)) if placed_count > 0 else 0.0

    return {
        "institute_id": clean_id,
        "institute_name": resolved_name,
        "district": resolved_district,
        "composite_score": composite_score,
        "accreditation_tier": tier,
        "evidence_confidence": confidence_tier,
        "data_provenance": "STATE_DETERMINISTIC_ACCREDITATION",
        "dimension_breakdown": {
            "placement_employment_rate": {
                "score": placement_subscore,
                "weight": 0.35,
                "placement_rate_pct": placement_rate,
                "employment_conversion_rate_pct": employment_conversion,
                "total_candidates_tracked": total_candidates,
                "placed_candidates": placed_count,
                "employed_candidates": employed_count,
            },
            "curriculum_modernity": {
                "score": curriculum_subscore,
                "weight": 0.25,
                "active_courses_audited": len(inst_audited),
            },
            "employer_readiness_feedback": {
                "score": employer_subscore,
                "weight": 0.20,
                "feedback_responses_count": len(inst_feedback),
            },
            "wage_premium": {
                "score": wage_subscore,
                "weight": 0.20,
                "average_salary_inr": avg_salary_inr,
                "median_salary_inr": median_salary_inr,
            },
        },
        "roi_metrics": roi_metrics,
        "retention_metrics": {
            "retention_rate_6m_pct": retention_rate_6m,
            "retained_6m_count": retained_6m,
            "retained_12m_count": retained_12m,
            "attrited_count": attrited,
        },
        "total_courses_count": len(matched_courses),
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


def evaluate_and_persist_institute_accreditation(
    institute_id: str,
    evaluator_user_id: str | None = None,
    is_demo: bool | None = None,
) -> dict[str, Any]:
    resolved_is_demo: bool = is_explicit_demo_mode(is_demo)
    scorecard = compute_institute_scorecard(institute_id=institute_id, is_demo=resolved_is_demo)

    now_iso = datetime.now(timezone.utc).isoformat()
    record_id = f"acc-{uuid.uuid4().hex[:12]}"
    valid_until = f"{int(now_iso[:4]) + 1}-09-30"

    record_data = {
        "id": record_id,
        "institute_id": scorecard["institute_id"],
        "institute_name": scorecard["institute_name"],
        "district": scorecard["district"],
        "composite_score": scorecard["composite_score"],
        "accreditation_tier": scorecard["accreditation_tier"],
        "placement_score": scorecard["dimension_breakdown"]["placement_employment_rate"]["score"],
        "curriculum_score": scorecard["dimension_breakdown"]["curriculum_modernity"]["score"],
        "employer_satisfaction_score": scorecard["dimension_breakdown"]["employer_readiness_feedback"]["score"],
        "wage_premium_score": scorecard["dimension_breakdown"]["wage_premium"]["score"],
        "evidence_confidence": scorecard["evidence_confidence"],
        "total_candidates_evaluated": scorecard["dimension_breakdown"]["placement_employment_rate"]["total_candidates_tracked"],
        "placed_candidates": scorecard["dimension_breakdown"]["placement_employment_rate"]["placed_candidates"],
        "average_salary_inr": scorecard["dimension_breakdown"]["wage_premium"]["average_salary_inr"],
        "roi_multiplier": scorecard["roi_metrics"]["roi_multiplier"],
        "valid_until": valid_until,
        "evaluator_user_id": evaluator_user_id,
        "is_demo": resolved_is_demo,
        "data_provenance": "STATE_DETERMINISTIC_ACCREDITATION",
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    saved = save_institution_accreditation_record(record_data)

    return {
        **scorecard,
        "accreditation_record": saved,
        "data_provenance": "STATE_DETERMINISTIC_ACCREDITATION",
    }


def compute_district_roi_analytics(
    district_filter: str | None = None,
    is_demo: bool | None = None,
) -> dict[str, Any]:
    if not _cache:
        init_db()

    resolved_is_demo: bool = is_explicit_demo_mode(is_demo)

    if resolved_is_demo:
        try:
            outcomes = list_placement_outcomes(is_demo=True, limit=10000) or []
        except Exception:
            outcomes = []
        cached_outcomes = [
            o for o in _cache.get("placement_outcomes", [])
            if o.get("is_demo") is True or o.get("source") == "DEMO_SYNTHETIC" or o.get("is_demo") is None
        ]
        seen_outcome_ids = {o["id"] for o in outcomes if o.get("id")}
        for co in cached_outcomes:
            if co.get("id") not in seen_outcome_ids:
                outcomes.append(co)

        try:
            courses = list_courses(is_demo=True) or []
        except Exception:
            courses = []
        cached_courses = [
            c for c in _cache.get("courses", [])
            if c.get("is_demo") is True or c.get("source") == "DEMO_SYNTHETIC" or not c.get("source") or c.get("source") == "SEED_DATA"
        ]
        seen_course_ids = {c["id"] for c in courses if c.get("id")}
        for cc in cached_courses:
            if cc.get("id") not in seen_course_ids:
                courses.append(cc)
    else:
        try:
            outcomes = list_placement_outcomes(is_demo=False, limit=10000) or []
        except Exception:
            outcomes = []
        cached_outcomes = [
            o for o in _cache.get("placement_outcomes", [])
            if o.get("is_demo") is False and o.get("source") != "DEMO_SYNTHETIC"
        ]
        seen_outcome_ids = {o["id"] for o in outcomes if o.get("id")}
        for co in cached_outcomes:
            if co.get("id") not in seen_outcome_ids:
                outcomes.append(co)

        try:
            courses = list_courses(is_demo=False) or []
        except Exception:
            courses = []
        cached_courses = [
            c for c in _cache.get("courses", [])
            if c.get("is_demo") is False and c.get("source") != "DEMO_SYNTHETIC"
        ]
        seen_course_ids = {c["id"] for c in courses if c.get("id")}
        for cc in cached_courses:
            if cc.get("id") not in seen_course_ids:
                courses.append(cc)

    try:
        audited = audit_all_courses(is_demo=resolved_is_demo) or []
    except Exception:
        audited = []

    all_districts = sorted(list({
        (c.get("district") or "").strip()
        for c in courses
        if c.get("district") and c["district"].strip()
    } | {
        (o.get("district") or "").strip()
        for o in outcomes
        if o.get("district") and o["district"].strip()
    }))

    placed_statuses = {"PLACED", "EMPLOYED", "EMPLOYER_FEEDBACK_PENDING", "FEEDBACK_RECEIVED"}

    district_results = []
    for d in all_districts:
        d_clean = d.strip().lower()
        if district_filter and district_filter.lower() != "all" and d_clean != district_filter.strip().lower():
            continue

        d_courses = [c for c in courses if (c.get("district") or "").strip().lower() == d_clean]
        d_outcomes = [o for o in outcomes if (o.get("district") or "").strip().lower() == d_clean]
        d_audited = [a for a in audited if (a.get("district") or "").strip().lower() == d_clean]

        total_students = sum(c.get("enrolment_count") or c.get("enrolment_capacity", 60) for c in d_courses)
        if len(d_outcomes) > total_students:
            total_students = len(d_outcomes)

        placed_candidates = sum(
            1 for o in d_outcomes
            if o.get("status") in placed_statuses
            and (o.get("verification_status") or "").upper() == "VERIFIED"
        )
        salaries = [
            o.get("salary_annual_inr") for o in d_outcomes
            if o.get("status") in placed_statuses
            and (o.get("verification_status") or "").upper() == "VERIFIED"
            and o.get("salary_annual_inr") and o.get("salary_annual_inr") > 0
        ]
        avg_salary = round(sum(salaries) / len(salaries)) if salaries else 360000

        equipment_grants = sum(a.get("total_equipment_budget_inr", 0) for a in d_audited)

        roi_data = calculate_training_roi(
            placed_count=placed_candidates,
            average_salary_inr=avg_salary,
            total_students=max(1, total_students),
            capital_grants_inr=equipment_grants,
        )

        placement_rate = round((placed_candidates / max(1, total_students)) * 100, 1)

        district_results.append({
            "district": d,
            "total_courses": len(d_courses),
            "total_students_enrolled": total_students,
            "placed_candidates": placed_candidates,
            "placement_rate_pct": placement_rate,
            "average_salary_inr": avg_salary,
            **roi_data,
        })

    district_results.sort(key=lambda x: x["roi_multiplier"], reverse=True)

    state_total_students = sum(r["total_students_enrolled"] for r in district_results)
    state_total_placed = sum(r["placed_candidates"] for r in district_results)
    state_total_output = sum(r["annual_economic_output_inr"] for r in district_results)
    state_total_investment = sum(r["public_training_investment_inr"] for r in district_results)
    state_net_benefit = state_total_output - state_total_investment
    state_roi_multiplier = round(state_total_output / max(1, state_total_investment), 2)
    state_payback_months = round((state_total_investment / max(1, state_total_output)) * 12.0, 1) if state_total_output > 0 else 0.0

    return {
        "district_filter": district_filter or "ALL",
        "districts_analyzed": len(district_results),
        "statewide_summary": {
            "total_students_enrolled": state_total_students,
            "placed_candidates": state_total_placed,
            "overall_placement_rate_pct": round((state_total_placed / max(1, state_total_students)) * 100, 1) if state_total_students > 0 else 0.0,
            "annual_economic_output_inr": state_total_output,
            "public_training_investment_inr": state_total_investment,
            "net_economic_benefit_inr": state_net_benefit,
            "statewide_roi_multiplier": state_roi_multiplier,
            "statewide_payback_period_months": state_payback_months,
        },
        "district_leaderboard": district_results,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
